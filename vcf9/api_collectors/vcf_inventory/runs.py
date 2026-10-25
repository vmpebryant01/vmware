"""Read completed inventory runs and identify records. Author: Paul Bryant."""

import json
from pathlib import Path


class RunError(ValueError):
    """A run cannot be read safely or has not finished."""


def _json(path):
    def reject_constant(value):
        raise ValueError("Nonfinite JSON number")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object key")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant,
                           object_pairs_hook=unique_object)
    except (OSError, UnicodeError, ValueError):
        raise RunError("Cannot read a required run file as UTF-8 JSON.") from None
    if not isinstance(value, dict):
        raise RunError("Run files must contain JSON objects.")
    return value


def load_run(path):
    """Read successful resources; reject path escapes and inconsistent documents."""
    root = Path(path).resolve()
    summary = _json(root / "summary.json")
    if (summary.get("status") not in ("success", "incomplete")
            or not isinstance(summary.get("completed_at"), str) or not summary["completed_at"].strip()):
        raise RunError("The run has not finished; its inventories cannot establish completeness.")
    targets = summary.get("targets")
    if not isinstance(targets, list):
        raise RunError("Invalid run target list.")
    resources, unavailable, seen = {}, {}, set()
    for target in targets:
        if not isinstance(target, dict) or not all(isinstance(target.get(k), str) for k in ("name", "component", "endpoint")):
            raise RunError("Invalid target metadata in summary.")
        rows = target.get("resources")
        if not isinstance(rows, list):
            raise RunError("Invalid resource list in summary.")
        for result in rows:
            if not isinstance(result, dict) or not isinstance(result.get("resource"), str):
                raise RunError("Invalid resource metadata in summary.")
            key = (target["name"], target["component"], result["resource"])
            if key in seen:
                raise RunError("Duplicate target/resource in summary.")
            seen.add(key)
            if result.get("status") != "success":
                unavailable[key] = "Resource did not complete successfully."
                continue
            relative = result.get("file")
            if not isinstance(relative, str) or not relative:
                raise RunError("Successful resource is missing its file reference.")
            document_path = (root / relative).resolve()
            if not document_path.is_relative_to(root) or document_path == root:
                raise RunError("A resource file reference escapes its run directory.")
            document = _json(document_path)
            expected = {"target": key[0], "component": key[1], "resource": key[2], "endpoint": target["endpoint"]}
            if any(document.get(k) != v for k, v in expected.items()):
                raise RunError("Resource identity or endpoint differs from its summary.")
            records = document.get("records")
            count = document.get("record_count")
            if (not isinstance(records, list) or any(not isinstance(row, dict) for row in records)
                    or type(count) is not int or count != len(records)
                    or type(result.get("record_count")) is not int or result["record_count"] != count):
                raise RunError("Resource record count or structure differs from its summary.")
            coverage = document.get("collection", {}).get("coverage") if isinstance(document.get("collection", {}), dict) else "incomplete"
            if coverage not in (None, "complete"):
                unavailable[key] = "Resource reports incomplete coverage."
            else:
                resources[key] = document
    return {"summary": summary, "resources": resources, "unavailable": unavailable}


def _value(row, field):
    value = row
    for key in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def identity_for(component, resource, row):
    """Return documented identifiers, never a display name or content hash fallback."""
    if resource == "appliance_info":
        return ("singleton",)
    if component == "vsan":
        return (row["cluster_id"],) if isinstance(row.get("cluster_id"), str) and row["cluster_id"] else None
    if component == "vcenter":
        fields = {"vms": "vm", "hosts": "host", "clusters": "cluster", "datacenters": "datacenter",
                  "datastores": "datastore", "networks": "network"}
        candidates = [fields.get(resource, "id")]
    elif resource == "latest_metrics":
        candidates = ["resource_id", "stat_key"]
    elif resource == "relationships":
        candidates = ["resource_id", "relationship_type", "related_resource_id"]
    elif resource == "rule_statistics":
        required = [row.get(field) for field in ("domain_id", "policy_id", "rule_id", "enforcement_point")]
        context = [row.get(field) for field in ("container_cluster_path", "internal_rule_id", "lr_path", "segment_path", "rule")]
        if any(not isinstance(value, str) or not value for value in required) or any(value is not None and not isinstance(value, str) for value in context):
            return None
        return tuple(required) + (json.dumps(context, ensure_ascii=True, separators=(",", ":")),)
    elif resource == "certificates":
        candidates = ["domain_id", "resourceType", "resourceName", "issuedTo"]
    elif resource == "component_statuses":
        candidates = ["component_id"]
    else:
        candidates = []
        for field in ("id", "identifier", "uuid", "applianceId", "serviceMeshId", "computeProfileId", "sitePairingId", "replication_id"):
            if _value(row, field) is not None:
                candidates = [field]
                break
    if not candidates:
        return None
    values = [_value(row, field) for field in candidates]
    if any(type(value) not in (str, int) or value == "" for value in values):
        return None
    # Local IDs from fan-out calls are meaningful only within their parent scope.
    parents = [] if resource == "certificates" else [row[field] for field in
        ("pairing_id", "srm_id", "domain_id", "policy_id", "component_id", "group_id", "deployment_id") if field in row]
    if any(type(value) not in (str, int) or value == "" for value in parents):
        return None
    return tuple(str(value) for value in parents + values)
