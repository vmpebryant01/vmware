"""Optional backup and authorization inventory. Author: Paul Bryant."""

from .http_client import ApiError


RESOURCE_PATHS = {
    "vcenter": {
        "backup_jobs": "/api/appliance/recovery/backup/job/details",
        "backup_schedules": "/api/appliance/recovery/backup/schedules",
        "authorization_roles": "/api/vcenter/authorization/roles",
        "authorization_permissions": "/api/vcenter/authorization/permissions",
    },
    "nsx": {"backup_history": "/api/v1/cluster/backups/history"},
}
DEFAULT_RESOURCES = {}
# A bare permissions POST creates permissions. The read query needs allow_query.
ALLOWED_OPERATIONS = set()
_PERMISSIONS_PATH = RESOURCE_PATHS["vcenter"]["authorization_permissions"]


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def validate_target(target):
    """The supplemental resources accept no implicit or silently ignored filters."""
    selected = target.get("resources", [])
    if not isinstance(selected, list):
        raise ValueError("resources must be an array.")
    filters = target.get("filters", {})
    if isinstance(filters, dict) and any(supports(target.get("component"), name) for name in filters):
        raise ValueError("Backup and authorization resources do not support configured filters.")


def allow_query(component, method, path, params, body):
    """Allow only the documented read-only permissions list request shape."""
    if (component != "vcenter" or method != "POST" or path != _PERMISSIONS_PATH
            or params != {"action": "list"} or not isinstance(body, dict)
            or set(body) != {"iterate"} or not isinstance(body["iterate"], dict)):
        return False
    iterate = body["iterate"]
    if set(iterate) not in ({"page_size"}, {"page_size", "marker"}):
        return False
    if type(iterate.get("page_size")) is not int or not 1 <= iterate["page_size"] <= 1000:
        return False
    if "marker" in iterate and not _marker_valid(iterate["marker"]):
        return False
    return True


def probe_request(target, resource):
    """Return a single protected read; a successful probe does not establish coverage."""
    component = target.get("component")
    if not supports(component, resource):
        return None
    path = RESOURCE_PATHS[component][resource]
    if resource == "authorization_permissions":
        return ("POST", path, {"action": "list"}, {"iterate": {"page_size": 1}},
                "One page of account-visible authorization assignments only.")
    return ("GET", path, None, None, "Account-visible endpoint response only; no coverage or restore validation.")


def _marker_valid(value):
    return isinstance(value, str) and 0 < len(value) <= 16384 and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def _text(value, field):
    if not isinstance(value, str) or not value:
        raise ApiError(f"The assurance response has an invalid {field}.")
    return value


def _project(value, fields):
    return {key: value[key] for key in fields if key in value and (value[key] is None or type(value[key]) in (str, int, float, bool))}


def _metadata(client, resource):
    if not isinstance(getattr(client, "collection_metadata", None), dict):
        client.collection_metadata = {}
    metadata = {"coverage": "incomplete", "scope": "account_visible_endpoint"}
    client.collection_metadata[resource] = metadata
    return metadata


def _map_response(document, resource):
    if not isinstance(document, dict) or any(not isinstance(value, dict) for value in document.values()):
        raise ApiError(f"The {resource} response is not an identifier-to-information map.")
    for identifier, info in document.items():
        _text(identifier, "identifier")
        yield identifier, info


def _backup_jobs(client, path):
    fields = ("status", "start_time", "end_time", "duration", "size", "progress", "type", "fast_backup")
    return [{"id": identifier, **_project(info, fields)}
            for identifier, info in _map_response(client.get(path), "backup jobs")]


def _backup_schedules(client, path):
    rows = []
    for identifier, info in _map_response(client.get(path), "backup schedules"):
        row = {"id": identifier, **_project(info, ("enable", "fast_backup"))}
        if "enable" in row and type(row["enable"]) is not bool:
            raise ApiError("The backup schedule enable field is not a boolean.")
        recurrence = info.get("recurrence_info")
        if isinstance(recurrence, dict):
            row["recurrence_info"] = _project(recurrence, ("minute", "hour"))
            days = recurrence.get("days")
            if isinstance(days, list) and all(isinstance(day, str) for day in days):
                row["recurrence_info"]["days"] = days
        retention = info.get("retention_info")
        if isinstance(retention, dict):
            row["retention_info"] = _project(retention, ("max_count",))
        rows.append(row)
    return rows


def _role(item):
    if not isinstance(item, dict) or not isinstance(item.get("info"), dict):
        raise ApiError("The authorization role response has invalid items.")
    identifier, info = _text(item.get("role"), "role identifier"), item["info"]
    privileges = info.get("privileges")
    if not isinstance(privileges, list) or any(not isinstance(value, str) or not value for value in privileges):
        raise ApiError("The authorization role response has invalid privileges.")
    if type(info.get("system")) is not bool:
        raise ApiError("The authorization role system field is not a boolean.")
    return {"id": identifier, "role_id": identifier, "name": _text(info.get("name"), "role name"),
            "privileges": privileges, "system": info["system"], **_project(info, ("description",))}


def _permission(item):
    if not isinstance(item, dict) or not isinstance(item.get("info"), dict):
        raise ApiError("The authorization permission response has invalid items.")
    identifier, info = _text(item.get("permission"), "permission identifier"), item["info"]
    principal, scope = info.get("principal"), info.get("object")
    if not isinstance(principal, dict) or not isinstance(scope, dict) or type(info.get("propagating")) is not bool:
        raise ApiError("The authorization permission response has invalid scope or propagation.")
    row = {"id": identifier, "permission_id": identifier, "role_id": _text(info.get("role"), "role identifier"),
           "principal_type": _text(principal.get("type"), "principal type"),
           "principal_name": _text(principal.get("name"), "principal name"),
           "object_type": _text(scope.get("type"), "object type"),
           "object_id": _text(scope.get("id"), "object identifier"), "propagating": info["propagating"]}
    if "domain" in principal:
        if principal["domain"] is not None and not isinstance(principal["domain"], str):
            raise ApiError("The authorization principal domain is invalid.")
        row["principal_domain"] = principal["domain"]
    return row


def _page(document):
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ApiError("The authorization response is not a documented list result.")
    marker = document.get("marker")
    if marker is not None and not _marker_valid(marker):
        raise ApiError("The authorization response contains an invalid pagination marker.")
    return document["items"], marker


def _roles(client, path):
    # The public schema documents the iteration struct but not its query encoding.
    # Never publish a truncated role catalog or invent a continuation request.
    items, marker = _page(client.get(path))
    if marker is not None:
        raise ApiError("Role results require continuation; iteration query encoding has not been verified, so coverage is incomplete.")
    rows = [_role(item) for item in items]
    if len({row["id"] for row in rows}) != len(rows):
        raise ApiError("The authorization role response repeats identifiers.")
    return rows


def _permissions(client, path, page_size, max_pages):
    rows, seen_ids, seen_markers, marker = [], set(), set(), None
    for _ in range(max_pages):
        iterate = {"page_size": page_size}
        if marker is not None:
            iterate["marker"] = marker
        document = client.request("POST", path, params={"action": "list"}, body={"iterate": iterate})
        items, marker = _page(document)
        for item in items:
            row = _permission(item)
            if row["id"] in seen_ids:
                raise ApiError("The authorization permissions response repeats identifiers; rerun after changes settle.")
            seen_ids.add(row["id"])
            rows.append(row)
        if marker is None:
            return rows
        if marker in seen_markers:
            raise ApiError("The authorization permissions response repeats a pagination marker.")
        seen_markers.add(marker)
    raise ApiError("Authorization permissions exceeded max_pages; coverage is incomplete.")


def _nsx_history(client, path, metadata):
    document = client.get(path)
    kinds = {"cluster": "cluster_backup_statuses", "node": "node_backup_statuses", "inventory": "inventory_backup_statuses"}
    if not isinstance(document, dict) or not any(key in document for key in (*kinds.values(), "overall_backup_status")):
        raise ApiError("The NSX backup history response has no documented history fields.")
    rows, seen = [], set()
    for kind, key in kinds.items():
        values = document.get(key, [])
        if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
            raise ApiError("The NSX backup history contains an invalid status array.")
        for value in values:
            identifier = _text(value.get("backup_id"), "backup identifier")
            stable_id = kind + ":" + identifier
            if stable_id in seen:
                raise ApiError("The NSX backup history repeats a backup identifier within its kind.")
            seen.add(stable_id)
            if "success" in value and type(value["success"]) is not bool:
                raise ApiError("The NSX backup success field is not a boolean.")
            rows.append({"id": stable_id, "backup_id": identifier, "backup_kind": kind,
                         **_project(value, ("start_time", "end_time", "success", "error_code"))})
    overall = document.get("overall_backup_status")
    if isinstance(overall, str):
        metadata["overall_backup_status"] = overall
    metadata["backup_kinds"] = list(kinds)
    metadata["timestamp_unit"] = None
    metadata["timestamp_unit_basis"] = "not_verified"
    return rows


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Collect selected metadata, excluding backup destinations and error payloads."""
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    component = client.target.get("component")
    if not supports(component, resource):
        raise ApiError("The component does not support this assurance resource.")
    if type(page_size) is not int or not 1 <= page_size <= 1000 or type(max_pages) is not int or max_pages < 1:
        raise ApiError("Assurance pagination requires page_size 1-1000 and positive max_pages.")
    metadata = _metadata(client, resource)
    path = RESOURCE_PATHS[component][resource]
    if resource == "backup_jobs":
        rows = _backup_jobs(client, path)
    elif resource == "backup_schedules":
        rows = _backup_schedules(client, path)
    elif resource == "authorization_roles":
        rows = _roles(client, path)
    elif resource == "authorization_permissions":
        rows = _permissions(client, path, page_size, max_pages)
    else:
        rows = _nsx_history(client, path, metadata)
    metadata["coverage"] = "complete"
    return rows
