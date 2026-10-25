"""Read existing vLCM desired images and compliance. Author: Paul Bryant."""

import re

from .http_client import ApiError


RESOURCE_PATHS = {"vcenter": {
    "lifecycle_desired_image": "/api/esx/settings/clusters/{cluster}/software",
    "lifecycle_compliance": "/api/esx/settings/clusters/{cluster}/software/compliance",
}}
DEFAULT_RESOURCES = {}
ALLOWED_OPERATIONS = set()
_CLUSTER = re.compile(r"domain-c[0-9]{1,18}\Z")
_HOST = re.compile(r"host-[0-9]{1,18}\Z")


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def valid_cluster_ids(value):
    return (isinstance(value, list) and 1 <= len(value) <= 1000
            and all(isinstance(item, str) and _CLUSTER.fullmatch(item) for item in value)
            and len(set(value)) == len(value))


def validate_target(target):
    selected = target.get("resources", [])
    if "lifecycle_cluster_ids" not in target and not any(supports(target.get("component"), item) for item in selected):
        return
    if target.get("component") != "vcenter" or not valid_cluster_ids(target.get("lifecycle_cluster_ids")):
        raise ValueError("lifecycle_cluster_ids must contain 1-1000 unique vCenter domain-c cluster identifiers.")
    if any(supports("vcenter", item) for item in target.get("filters", {})):
        raise ValueError("Lifecycle resources use explicit lifecycle_cluster_ids and do not accept filters.")


def _text(value, label):
    if not isinstance(value, str) or not value or len(value) > 16384 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ApiError(f"The lifecycle response has an invalid {label}.")
    return value


def _mapping(value, label):
    if not isinstance(value, dict):
        raise ApiError(f"The lifecycle response has an invalid {label}.")
    return value


def _optional_text(source, fields):
    return {field: _text(source[field], field) for field in fields if source.get(field) is not None}


def _version(value):
    value = _mapping(value, "software version")
    return {"version": _text(value.get("version"), "software version")}


def _versions(value, label):
    return {_text(key, label): _version(info) for key, info in _mapping(value, label).items()}


def _image(document, alternatives=True):
    document = _mapping(document, "desired image")
    result = {"base_image": _version(document.get("base_image")),
              "components": _versions(document.get("components"), "components")}
    if document.get("add_on") is not None:
        add_on = _mapping(document["add_on"], "add-on")
        result["add_on"] = {"name": _text(add_on.get("name"), "add-on name"), **_version(add_on)}
    for field in ("solutions", "removed_components"):
        if document.get(field) is not None:
            result[field] = _versions(document[field], field)
    if document.get("hardware_support") is not None:
        hardware = _mapping(document["hardware_support"], "hardware support")
        packages = _mapping(hardware.get("packages"), "hardware support packages")
        result["hardware_support"] = {"packages": {
            _text(key, "hardware support manager"): {"pkg": _text(_mapping(value, "hardware support package").get("pkg"), "package"), **_version(value)}
            for key, value in packages.items()}}
    if alternatives and document.get("alternative_images") is not None:
        result["alternative_images"] = {
            _text(key, "alternative image"): _image(value, alternatives=False)
            for key, value in _mapping(document["alternative_images"], "alternative images").items()}
    return result


def _notifications(value):
    if value is None:
        return None
    value = _mapping(value, "notification counts")
    result = {}
    for key in ("info", "warnings", "errors"):
        rows = value.get(key, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ApiError("The lifecycle response has an invalid notification array.")
        result[key] = len(rows)
    return result


def _item_compliance(value):
    value = _mapping(value, "software compliance")
    result = {"status": _text(value.get("status"), "software compliance status"),
              **_optional_text(value, ("stage_status",))}
    for field in ("current", "target"):
        if value.get(field) is not None:
            result[field] = _version(value[field])
    return result


def _host(value):
    value = _mapping(value, "host compliance")
    result = {"status": _text(value.get("status"), "host status"),
              **_optional_text(value, ("scan_time", "commit", "impact", "stage_status")),
              "notification_counts": _notifications(value.get("notifications"))}
    if value.get("base_image") is not None:
        result["base_image"] = _item_compliance(value["base_image"])
    if value.get("add_on") is not None:
        add_on = _mapping(value["add_on"], "add-on compliance")
        result["add_on"] = _item_compliance(add_on)
        for field in ("current", "target"):
            if isinstance(add_on.get(field), dict) and add_on[field].get("name") is not None:
                result["add_on"][field]["name"] = _text(add_on[field]["name"], "add-on name")
    for field in ("components", "removed_components", "solutions"):
        if value.get(field) is not None:
            result[field] = {_text(key, field): _item_compliance(info)
                             for key, info in _mapping(value[field], field).items()}
    return result


def _compliance(document):
    document = _mapping(document, "cluster compliance")
    result = {"status": _text(document.get("status"), "cluster status"),
              "scan_time": _text(document.get("scan_time"), "scan completion time"),
              **_optional_text(document, ("commit", "impact", "stage_status")),
              "notification_counts": _notifications(document.get("notifications"))}
    for field in ("compliant_hosts", "non_compliant_hosts", "incompatible_hosts", "unavailable_hosts"):
        values = document.get(field)
        if (not isinstance(values, list) or any(not isinstance(item, str) or not _HOST.fullmatch(item) for item in values)
                or len(set(values)) != len(values)):
            raise ApiError("The lifecycle response has an invalid host classification list.")
        result[field] = list(values)
    hosts = _mapping(document.get("hosts"), "host compliance map")
    result["hosts"] = {}
    for identity, value in hosts.items():
        if not isinstance(identity, str) or not _HOST.fullmatch(identity):
            raise ApiError("The lifecycle response has an invalid host identifier.")
        result["hosts"][identity] = _host(value)
    # Counts and versions are sufficient for this report. Native messages,
    # remediation instructions, and hardware inventory are not exported.
    return result


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Read each configured cluster once, without refreshing its compliance scan."""
    if not supports(client.target.get("component"), resource):
        raise ApiError("Unknown lifecycle inventory resource.")
    try:
        validate_target(dict(client.target, resources=[resource]))
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    if not isinstance(getattr(client, "collection_metadata", None), dict):
        client.collection_metadata = {}
    configured = list(client.target["lifecycle_cluster_ids"])
    details = {"coverage": "incomplete", "scope": "explicit_cluster_ids", "configured_cluster_ids": configured,
               "queried_cluster_ids": [], "request_count": 0, "refresh_requested": False}
    client.collection_metadata[resource] = details
    records = []
    for cluster in configured:
        details["request_count"] += 1
        document = client.get(RESOURCE_PATHS["vcenter"][resource].format(cluster=cluster))
        value = _image(document) if resource == "lifecycle_desired_image" else _compliance(document)
        records.append({"id": cluster, "cluster_id": cluster, **value})
        details["queried_cluster_ids"].append(cluster)
    details.update(coverage="complete", record_count=len(records))
    return records


def probe_request(target, resource):
    if not supports(target.get("component"), resource) or not valid_cluster_ids(target.get("lifecycle_cluster_ids")):
        return None
    path = RESOURCE_PATHS["vcenter"][resource].format(cluster=target["lifecycle_cluster_ids"][0])
    return "GET", path, None, None, "Only the first explicitly configured cluster is probed; no scan or remediation is started."
