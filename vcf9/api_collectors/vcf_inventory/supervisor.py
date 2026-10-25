"""Collect explicitly selected Supervisors and namespaces. Author: Paul Bryant."""

import math
import re
from urllib.parse import quote

from .http_client import ApiError

RESOURCE_PATHS = {"vcenter": {
    "supervisor_summaries": "/api/vcenter/namespace-management/supervisors/{supervisor}/summary",
    "supervisor_conditions": "/api/vcenter/namespace-management/supervisors/{supervisor}/conditions",
    "namespaces": "/api/vcenter/namespaces/instances/{namespace}",
}}
DEFAULT_RESOURCES = {}
ALLOWED_OPERATIONS = set()
SELECTORS = {"supervisor_summaries": "supervisor_ids", "supervisor_conditions": "supervisor_ids", "namespaces": "namespace_ids"}


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def validate_target(target):
    for selector in ("supervisor_ids", "namespace_ids"):
        needed = selector in target or any(SELECTORS.get(resource) == selector for resource in target.get("resources", []))
        if not needed:
            continue
        values = target.get(selector)
        if (target.get("component") != "vcenter" or not isinstance(values, list) or not 1 <= len(values) <= 1000
                or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", value)
                       or value in (".", "..") for value in values) or len(set(values)) != len(values)):
            raise ValueError(f"{selector} requires 1-1000 unique simple identifiers on a vCenter target.")
    filters = target.get("filters", {})
    if isinstance(filters, dict) and any(supports(target.get("component"), resource) for resource in filters):
        raise ValueError("Supervisor and namespace resources require explicit identifiers and do not accept filters.")


def _text(value):
    return isinstance(value, str) and bool(value) and len(value) <= 1024 and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def _fields(row, fields):
    return {key: row[key] for key in fields if key in row and (row[key] is None or _text(row[key]))}


def _stats(value, capacity=False):
    if not isinstance(value, dict):
        raise ApiError("Supervisor or namespace statistics are not an object.")
    fields = [f"{kind}_{suffix}" for kind in ("cpu", "memory", "storage")
              for suffix in (("used", "capacity") if capacity else ("used",))]
    result = {}
    for field in fields:
        if type(value.get(field)) is not int or not 0 <= value[field] <= 2**63 - 1:
            raise ApiError("Supervisor or namespace statistics omit a required nonnegative int64 value.")
        result[field] = value[field]
    return result


def _messages(value):
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ApiError("Supervisor or namespace messages are not an array of objects.")
    # Message text can contain response arguments or arbitrary endpoint strings.
    # Keep severity and stable message IDs only.
    result = []
    for row in value:
        item = _fields(row, ("id", "severity"))
        details = row.get("details")
        if isinstance(details, dict) and _text(details.get("id")):
            item["message_id"] = details["id"]
        result.append(item)
    return result


def _summary(document, identifier):
    if (not isinstance(document, dict) or any(not _text(document.get(field))
                                            for field in ("name", "config_status", "kubernetes_status"))):
        raise ApiError("Supervisor summary is not a documented information object.")
    return {"id": identifier, "supervisor_id": identifier,
            **_fields(document, ("name", "config_status", "kubernetes_status")),
            "stats": _stats(document.get("stats"), capacity=True), "messages": _messages(document.get("messages"))}


def _conditions(document, identifier):
    if not isinstance(document, list):
        raise ApiError("Supervisor conditions are not an array.")
    conditions, seen = [], set()
    for row in document:
        if not isinstance(row, dict) or not _text(row.get("type")) or not _text(row.get("status")):
            raise ApiError("Supervisor condition has no valid type or status.")
        if row["type"] in seen:
            raise ApiError("Supervisor conditions repeat a condition type.")
        seen.add(row["type"])
        conditions.append({**_fields(row, ("type", "status", "last_transition_time", "reason", "severity")),
                           "messages": _messages(row.get("messages"))})
    return {"id": identifier, "supervisor_id": identifier, "conditions": conditions}


def _namespace(document, identifier):
    if (not isinstance(document, dict) or not _text(document.get("cluster")) or not _text(document.get("config_status"))
            or not isinstance(document.get("messages"), list)):
        raise ApiError("Namespace information omits required cluster, configuration status or messages fields.")
    quota = document.get("resource_spec")
    if quota is not None and (not isinstance(quota, dict) or len(quota) > 1000 or any(
            not _text(key) or not (value is None or type(value) in (str, int, bool)
                                   or type(value) is float and math.isfinite(value)) for key, value in quota.items())):
        raise ApiError("Namespace resource quotas have an unsupported structure.")
    storage = document.get("storage_specs")
    if not isinstance(storage, list):
        raise ApiError("Namespace storage specifications are not an array.")
    specifications, seen = [], set()
    for row in storage:
        if (not isinstance(row, dict) or not _text(row.get("policy")) or row["policy"] in seen
                or row.get("limit") is not None and (type(row["limit"]) is not int or row["limit"] < 0)):
            raise ApiError("Namespace storage specification has invalid or duplicate policy or limit fields.")
        seen.add(row["policy"])
        specifications.append({"policy": row["policy"], "limit": row.get("limit")})
    return {"id": identifier, "namespace_id": identifier, **_fields(document, ("cluster", "config_status")),
            "stats": _stats(document.get("stats")), "resource_spec": quota, "storage_specs": specifications,
            "messages": _messages(document.get("messages"))}


def collect_resource(client, resource, page_size=100, max_pages=1000):
    if not supports(client.target.get("component"), resource):
        raise ApiError("Unknown Supervisor or namespace resource.")
    try:
        validate_target(dict(client.target, resources=[resource]))
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    selector = SELECTORS[resource]
    identifiers = client.target[selector]
    if not isinstance(getattr(client, "collection_metadata", None), dict):
        client.collection_metadata = {}
    metadata = {"coverage": "incomplete", "scope": "explicit_identifiers", selector: list(identifiers), "queried_ids": []}
    client.collection_metadata[resource] = metadata
    rows = []
    for identifier in identifiers:
        field = "namespace" if resource == "namespaces" else "supervisor"
        path = RESOURCE_PATHS["vcenter"][resource].format(**{field: quote(identifier, safe="")})
        document = client.get(path)
        normalizer = _namespace if resource == "namespaces" else _conditions if resource == "supervisor_conditions" else _summary
        rows.append(normalizer(document, identifier))
        metadata["queried_ids"].append(identifier)
    metadata.update(coverage="complete", record_count=len(rows))
    return rows


def probe_request(target, resource):
    if not supports(target.get("component"), resource):
        return None
    ids = target.get(SELECTORS[resource])
    if not isinstance(ids, list) or not ids:
        return None
    field = "namespace" if resource == "namespaces" else "supervisor"
    path = RESOURCE_PATHS["vcenter"][resource].format(**{field: quote(ids[0], safe="")})
    return "GET", path, None, None, "Only the first explicitly configured identifier is probed; no cluster, namespace or Supervisor discovery."
