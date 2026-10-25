"""Explicitly scoped protected VM membership. Author: Paul Bryant."""

import re
from urllib.parse import quote

from .http_client import ApiError
from .products import protection_recovery

RESOURCE_PATHS = {"live_site_recovery": {
    "group_vms": "/api/rest/srm/v2/pairings/{pairing_id}/protection-management/groups/{group_id}/vms"
}}


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def validate_target(target):
    if "group_ids" not in target and "group_vms" not in target.get("resources", []):
        return
    ids = target.get("group_ids")
    if (target.get("component") != "live_site_recovery" or not isinstance(ids, list) or not ids
            or len(ids) > 1000 or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", value) for value in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("group_ids must contain 1-1000 unique simple Live Site Recovery group identifiers.")
    if not target.get("pairing_id"):
        raise ValueError("Protected VM membership requires an explicit pairing_id.")


def collect_resource(client, resource, page_size=100, max_pages=1000):
    if not supports(client.target["component"], resource):
        raise ApiError("Unknown protected VM evidence resource.")
    try:
        validate_target(dict(client.target, resources=[resource]))
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    details = {"coverage": "incomplete", "queried_pairing_ids": [], "queried_group_ids": []}
    if not isinstance(getattr(client, "collection_metadata", None), dict):
        client.collection_metadata = {}
    client.collection_metadata[resource] = details
    protection_recovery._pairings(client, page_size, max_pages)
    pairing = client.target["pairing_id"]
    protection_recovery._ensure_remote(client, pairing)
    details["queried_pairing_ids"].append(pairing)
    result = []
    for group in client.target["group_ids"]:
        path = RESOURCE_PATHS["live_site_recovery"][resource].format(pairing_id=quote(pairing, safe=""), group_id=quote(group, safe=""))
        rows = protection_recovery._paginate(client, path, page_size, max_pages)
        seen = set()
        for row in rows:
            if any(field in row and row[field] != value for field, value in (("pairing_id", pairing), ("group_id", group))):
                raise ApiError("Protected VM evidence refers to a different configured scope.")
            identity = row.get("id")
            if not isinstance(identity, str) or not identity or identity in seen:
                raise ApiError("Protected VM membership has missing or duplicate identifiers.")
            seen.add(identity)
            state = row.get("protection_status_details")
            if state is not None and not isinstance(state, dict):
                raise ApiError("Protected VM status has an unexpected structure.")
            errors = state.get("errors") if state else None
            if errors is not None and not isinstance(errors, list):
                raise ApiError("Protected VM error metadata has an unexpected structure.")
            result.append({"id": identity, "name": row.get("name") if isinstance(row.get("name"), str) else None,
                           "pairing_id": pairing, "group_id": group,
                           "protection_status": state.get("status") if state and isinstance(state.get("status"), str) else None,
                           "protection_error_count": len(errors) if errors is not None else None})
        details["queried_group_ids"].append(group)
    details.update(coverage="complete", record_count=len(result))
    return result


def probe_request(target, resource):
    if not target.get("pairing_id") or not target.get("group_ids"):
        return None
    path = RESOURCE_PATHS[target["component"]][resource].format(
        pairing_id=quote(target["pairing_id"], safe=""), group_id=quote(target["group_ids"][0], safe=""))
    return "GET", path, {"offset": 0, "limit": 1}, None, "Only the first configured protection group is probed."
