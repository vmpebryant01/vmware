"""HCX workload inventory through documented APIs. Author: Paul Bryant."""

import os
import re

from ..http_client import ApiError


RESOURCE_PATHS = {
    "hcx": {
        "site_pairings": "/hybridity/api/cloudConfigs",
        "compute_profiles": "/hybridity/api/interconnect/computeProfiles",
        "service_meshes": "/hybridity/api/interconnect/serviceMesh",
        "appliances": "/hybridity/api/interconnect/appliances",
        "network_extensions": "/hybridity/api/l2NetworkExtensions",
    }
}
DEFAULT_RESOURCES = {"hcx": list(RESOURCE_PATHS["hcx"])}
ALLOWED_OPERATIONS = {("hcx", "POST", "/hybridity/api/sessions")}


def validate_target(target):
    """Check the authentication configuration without reading credentials."""
    source = target.get("auth_source", "credentials")
    if source not in ("credentials", "session_token", "vcf_sso"):
        raise ValueError("HCX auth_source must be credentials, session_token, or vcf_sso.")
    fields = ("username_env", "password_env") if source == "credentials" else ("token_env",)
    for field in fields:
        if not isinstance(target.get(field), str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", target[field]):
            raise ValueError(f"HCX {field} must name an environment variable.")


def _env(target, field):
    name = target.get(field)
    value = os.environ.get(name, "") if isinstance(name, str) else ""
    if not value:
        raise ApiError("Required HCX credential environment variables are missing or empty.")
    return value


def _header_token(value):
    if not isinstance(value, str) or not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ApiError("HCX did not provide a usable authentication token.")
    return value


def authenticate(client):
    """Use a workload session or an explicitly supplied session/VCF SSO token."""
    target = client.target
    try:
        validate_target(target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    client.headers.pop("Authorization", None)
    client.headers.pop("x-hm-authorization", None)
    source = target.get("auth_source", "credentials")
    if source == "credentials":
        # The workload API returns its session token in the response header.
        payload, headers = client.request(
            "POST", "/hybridity/api/sessions",
            body={"username": _env(target, "username_env"), "password": _env(target, "password_env")},
            include_headers=True,
        )
        if isinstance(payload, dict) and payload.get("success") is False:
            raise ApiError("HCX rejected session creation.")
        token = _header_token(headers.get("x-hm-authorization"))
        client.headers["x-hm-authorization"] = token
    elif source == "session_token":
        client.headers["x-hm-authorization"] = _header_token(_env(target, "token_env"))
    else:
        client.headers["Authorization"] = "Bearer " + _header_token(_env(target, "token_env"))
    client._product_state = {"component": "hcx", "auth_source": source}


def _items(payload, nested=False):
    if not isinstance(payload, dict):
        raise ApiError("Unexpected HCX inventory response; expected an object.")
    if payload.get("success") is False or payload.get("completed") is False or payload.get("errors"):
        raise ApiError("HCX reported a failed or incomplete inventory response.")
    container = payload.get("data") if nested else payload
    if not isinstance(container, dict):
        raise ApiError("Unexpected HCX inventory response; missing data object.")
    rows = container.get("items")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ApiError("Unexpected HCX inventory response; expected an items array of objects.")
    # These documented GET collections have no pagination parameters. A changed
    # response contract must be handled explicitly before exporting a partial list.
    for envelope in (payload, container):
        if envelope.get("paging") or envelope.get("cursor") or envelope.get("next"):
            raise ApiError("HCX returned unsupported pagination for this inventory endpoint.")
    return rows


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Collect one all-items GET collection without undocumented query parameters."""
    try:
        path = RESOURCE_PATHS["hcx"][resource]
    except KeyError:
        raise ApiError("Unknown HCX inventory resource.") from None
    return _items(client.get(path), nested=resource == "site_pairings")


def close(client):
    """Discard local credentials; the workload reference documents no logout API."""
    client.headers.pop("x-hm-authorization", None)
    client.headers.pop("Authorization", None)
    client._product_state = {}
