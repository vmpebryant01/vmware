"""Live Site Recovery and vSphere Replication inventory. Author: Paul Bryant."""

import base64
import hashlib
import json
import os
import re
from urllib.parse import quote, unquote

from ..http_client import ApiError


BASE_PATHS = {
    "live_site_recovery": "/api/rest/srm/v2",
    "vsphere_replication": "/api/rest/vr/v2",
}
RESOURCE_PATHS = {
    "live_site_recovery": {
        "pairings": BASE_PATHS["live_site_recovery"] + "/pairings",
        "protection_groups": BASE_PATHS["live_site_recovery"] + "/pairings/{pairing_id}/protection-management/groups",
        "recovery_plans": BASE_PATHS["live_site_recovery"] + "/pairings/{pairing_id}/recovery-management/plans",
    },
    "vsphere_replication": {
        "pairings": BASE_PATHS["vsphere_replication"] + "/pairings",
        "replications": BASE_PATHS["vsphere_replication"] + "/pairings/{pairing_id}/replications",
    },
}
DEFAULT_RESOURCES = {component: list(paths) for component, paths in RESOURCE_PATHS.items()}
ALLOWED_OPERATIONS = {
    (component, method, base + "/session")
    for component, base in BASE_PATHS.items() for method in ("POST", "DELETE")
}
_PAIR_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")


def validate_target(target):
    """Validate local and explicitly scoped remote authentication settings."""
    component = target["component"]
    source = target.get("auth_source", "credentials")
    if source not in ("credentials", "session_token"):
        raise ValueError("Recovery auth_source must be credentials or session_token.")
    if target.get("api_version", "v2") != "v2":
        raise ValueError("These recovery collectors implement only the documented v2 API gateways.")
    fields = ("username_env", "password_env") if source == "credentials" else ("token_env",)
    for field in fields:
        value = target.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"Recovery {field} must name an environment variable.")
    pairing = target.get("pairing_id")
    if pairing is not None and (not isinstance(pairing, str) or not _PAIR_ID.fullmatch(pairing)):
        raise ValueError("pairing_id must be a nonempty pairing identifier without path separators.")
    remote = (target.get("remote_username_env"), target.get("remote_password_env"))
    if any(value is not None for value in remote):
        if not pairing or not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) for value in remote):
            raise ValueError("Remote recovery login requires pairing_id and both remote credential environment variable names.")
    selected = target.get("resources", DEFAULT_RESOURCES[component])
    if source == "credentials" and any(resource != "pairings" for resource in selected) and not all(remote):
        raise ValueError("Pair-scoped recovery inventory requires pairing_id and remote credentials, or an existing session_token authenticated to both sites. Select only pairings for local discovery.")
    if "source_vc_guid" in target:
        guid = target["source_vc_guid"]
        if component != "vsphere_replication" or not isinstance(guid, str) or not guid or len(guid) > 200:
            raise ValueError("source_vc_guid is an optional nonempty vSphere Replication filter.")


def allow_request(component, method, path):
    """Allow only the documented remote-login route with one bounded identifier."""
    if component not in BASE_PATHS or method != "POST":
        return False
    prefix, suffix = BASE_PATHS[component] + "/pairings/", "/remote-session"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return False
    segment = path[len(prefix):-len(suffix)]
    pairing = unquote(segment)
    # Accept exactly the encoding produced from a validated identifier. Encoded
    # separators and double encoding cannot widen this authentication allowlist.
    return _PAIR_ID.fullmatch(pairing) is not None and quote(pairing, safe="") == segment


def _env(target, field):
    name = target.get(field)
    value = os.environ.get(name, "") if isinstance(name, str) else ""
    if not value:
        raise ApiError("Required recovery credential environment variables are missing or empty.")
    return value


def _basic(target, username_field, password_field):
    username, password = _env(target, username_field), _env(target, password_field)
    if ":" in username:
        raise ApiError("Basic authentication usernames cannot contain a colon.")
    return "Basic " + base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")


def _token(value):
    if not isinstance(value, str) or not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ApiError("Recovery API did not provide a usable session ID.")
    return value


def authenticate(client):
    """Authenticate to the explicitly configured local recovery gateway."""
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    client.headers.pop("Authorization", None)
    client.headers.pop("x-dr-session", None)
    source = client.target.get("auth_source", "credentials")
    if source == "credentials":
        result = client.request(
            "POST", BASE_PATHS[client.target["component"]] + "/session",
            headers={"Authorization": _basic(client.target, "username_env", "password_env")},
        )
        if not isinstance(result, dict):
            raise ApiError("Unexpected recovery session response.")
        session_id = _token(result.get("session_id"))
    else:
        session_id = _token(_env(client.target, "token_env"))
    client.headers["x-dr-session"] = session_id
    client._product_state = {"owns_session": source == "credentials", "remote_session_id": None}


def _integer(value, label):
    if type(value) is not int or value < 0:
        raise ApiError(f"Recovery API returned invalid {label} pagination metadata.")
    return value


def _paginate(client, path, page_size, max_pages, params=None):
    """Use numeric offset/limit; never follow a server-supplied URL."""
    combined, seen = [], set()
    offset, expected_total = 0, None
    for _ in range(max_pages):
        query = dict(params or {})
        query.update(limit=page_size, offset=offset)
        payload = client.get(path, params=query)
        if not isinstance(payload, dict):
            raise ApiError("Unexpected recovery inventory response; expected an object.")
        rows = payload.get("list")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ApiError("Unexpected recovery inventory response; expected a list of objects.")
        meta = payload.get("_meta")
        if meta is None:
            meta = {}
        if not isinstance(meta, dict):
            raise ApiError("Invalid recovery inventory metadata.")
        if meta.get("errors"):
            raise ApiError("Recovery API reported partial inventory errors; this resource was not exported.")
        if "offset" in meta and _integer(meta["offset"], "offset") != offset:
            raise ApiError("Recovery API repeated or changed the requested offset.")
        if meta.get("total") is not None:
            total = _integer(meta["total"], "total")
            if expected_total is not None and total != expected_total:
                raise ApiError("Recovery inventory changed during pagination; rerun collection.")
            expected_total = total
        if rows:
            fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
            if fingerprint in seen:
                raise ApiError("Recovery API repeated an inventory page.")
            seen.add(fingerprint)
        combined.extend(rows)
        links = meta.get("links") or {}
        if not isinstance(links, dict):
            raise ApiError("Invalid recovery pagination links.")
        next_link = links.get("next")
        has_next = bool(next_link.get("href")) if isinstance(next_link, dict) else bool(next_link)
        if expected_total is not None:
            if len(combined) > expected_total:
                raise ApiError("Recovery API returned more records than its advertised total.")
            if len(combined) == expected_total:
                if has_next:
                    raise ApiError("Recovery pagination metadata contradicts its advertised total.")
                return combined
        if not rows:
            if has_next or (expected_total is not None and len(combined) != expected_total):
                raise ApiError("Recovery pagination ended before its inventory was complete.")
            return combined
        # Continue even after a short page. Offset counts objects, not page numbers.
        offset += len(rows)
    raise ApiError("Recovery pagination exceeded max_pages; incomplete inventory was not exported.")


def _pairings(client, page_size, max_pages):
    component = client.target["component"]
    rows = _paginate(client, RESOURCE_PATHS[component]["pairings"], page_size, max_pages)
    pairing = client.target.get("pairing_id")
    if pairing:
        rows = [row for row in rows if row.get("pairing_id") == pairing]
        if not rows:
            raise ApiError("Configured recovery pairing_id was not visible to this account.")
    return rows


def _ensure_remote(client, pairing):
    target = client.target
    if not target.get("remote_username_env"):
        return  # An externally supplied session must already cover the remote site.
    if target.get("pairing_id") != pairing:
        raise ApiError("Remote credentials are restricted to the explicitly configured pairing_id.")
    state = getattr(client, "_product_state", {})
    current_session = client.headers.get("x-dr-session")
    if state.get("remote_session_id") == current_session and current_session:
        return
    path = BASE_PATHS[target["component"]] + "/pairings/" + quote(pairing, safe="") + "/remote-session"
    client.request("POST", path, headers={
        "Authorization": _basic(target, "remote_username_env", "remote_password_env")
    })
    state["remote_session_id"] = current_session
    client._product_state = state


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Return pairings or complete pair-scoped protection and replication records."""
    component = client.target["component"]
    if resource not in RESOURCE_PATHS[component]:
        raise ApiError("Unknown recovery inventory resource.")
    pairings = _pairings(client, page_size, max_pages)
    if resource == "pairings":
        return pairings
    result = []
    for item in pairings:
        pairing = item.get("pairing_id")
        if not isinstance(pairing, str) or not _PAIR_ID.fullmatch(pairing):
            raise ApiError("Recovery API returned an unusable pairing identifier.")
        _ensure_remote(client, pairing)
        path = RESOURCE_PATHS[component][resource].format(pairing_id=quote(pairing, safe=""))
        params = {}
        if component == "vsphere_replication":
            # Ask explicitly for status/configuration fields otherwise defaulted
            # or omitted by the documented replication list operation.
            params["extended_info"] = "true"
            if client.target.get("source_vc_guid"):
                params["source_vc_guid"] = client.target["source_vc_guid"]
        rows = _paginate(client, path, page_size, max_pages, params=params)
        for row in rows:
            if "pairing_id" in row and row["pairing_id"] != pairing:
                raise ApiError("Recovery record unexpectedly refers to a different pairing.")
            result.append(dict(row, pairing_id=pairing))
    return result


def close(client):
    """Log out only sessions created by this collector."""
    state = getattr(client, "_product_state", {})
    try:
        if state.get("owns_session"):
            client.request("DELETE", BASE_PATHS[client.target["component"]] + "/session")
    finally:
        client.headers.pop("x-dr-session", None)
        client._product_state = {}
