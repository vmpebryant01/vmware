"""VCF Fleet LCM component, node, and status inventory. Author: Paul Bryant."""

import hashlib
import json
import os
import re
from urllib.parse import quote

from ..http_client import ApiError


COMPONENT = "vcf_fleet"
BASE_PATH = "/fleet-lcm/v1"
RESOURCE_PATHS = {COMPONENT: {
    "components": BASE_PATH + "/components",
    "component_nodes": BASE_PATH + "/components/{component_id}/nodes",
    "component_statuses": BASE_PATH + "/components/{component_id}/status",
}}
DEFAULT_RESOURCES = {COMPONENT: list(RESOURCE_PATHS[COMPONENT])}
ALLOWED_OPERATIONS = set()


def validate_target(target):
    """Require an explicitly provided JWT without reading it during validation."""
    variable = target.get("token_env")
    if not isinstance(variable, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable):
        raise ValueError("VCF Fleet requires token_env naming a bearer JWT environment variable.")


def authenticate(client):
    """Use the documented bearer scheme; no session is created or revoked."""
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    token = os.environ.get(client.target["token_env"], "")
    if not token or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise ApiError("VCF Fleet bearer JWT is missing or invalid.")
    client.headers["Authorization"] = "Bearer " + token


def close(client):
    """Drop the local token reference without revoking a supplied token."""
    client.headers.pop("Authorization", None)


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ApiError(f"VCF Fleet returned invalid {label} pagination metadata.")
    return value


def _paginate(client, path, key, page_size, max_pages, components=False):
    rows, fingerprints, identities = [], set(), set()
    expected_pages = expected_total = None
    for page in range(1, max_pages + 1):
        params = {"pageNumber": page, "pageSize": min(page_size, 100)}
        if components:
            params.update(includeConsumptionVsp="true", includeVcdMigrator="true")
        payload = client.get(path, params=params)
        if not isinstance(payload, dict):
            raise ApiError("Unexpected VCF Fleet inventory envelope.")
        meta = payload.get("pageMetadata")
        if meta is not None and not isinstance(meta, dict):
            raise ApiError("VCF Fleet returned invalid pageMetadata.")
        meta = meta or {}
        page_rows = payload.get(key)
        if page_rows is None and meta.get("totalElements") == 0 and meta.get("totalPages") in (0, 1):
            page_rows = []
        if not isinstance(page_rows, list) or any(not isinstance(row, dict) for row in page_rows):
            raise ApiError(f"VCF Fleet returned an unexpected {key} array.")
        if "pageNumber" in meta and _integer(meta["pageNumber"], "page number", 1) != page:
            raise ApiError("VCF Fleet returned an unexpected page number.")
        if meta.get("totalPages") is not None:
            pages = _integer(meta["totalPages"], "total page count")
            if expected_pages is not None and pages != expected_pages:
                raise ApiError("VCF Fleet page count changed during collection; rerun inventory.")
            expected_pages = pages
        if meta.get("totalElements") is not None:
            total = _integer(meta["totalElements"], "total element count")
            if expected_total is not None and total != expected_total:
                raise ApiError("VCF Fleet total changed during collection; rerun inventory.")
            expected_total = total
        if page_rows:
            fingerprint = hashlib.sha256(json.dumps(page_rows, sort_keys=True).encode("utf-8")).hexdigest()
            if fingerprint in fingerprints:
                raise ApiError("VCF Fleet repeated an inventory page.")
            fingerprints.add(fingerprint)
        for row in page_rows:
            identity = row.get("id")
            if isinstance(identity, str) and identity:
                if identity in identities:
                    raise ApiError("VCF Fleet repeated an inventory identifier; rerun collection.")
                identities.add(identity)
        rows.extend(page_rows)
        # Component lists paginate SDDC LCMs, so component count is not a safe
        # interpretation of totalElements or requested pageSize.
        if not components and expected_total is not None and len(rows) > expected_total:
            raise ApiError("VCF Fleet returned more nodes than its advertised total.")
        if expected_pages is not None and page >= expected_pages:
            if page_rows and expected_pages == 0:
                raise ApiError("VCF Fleet returned data with zero declared pages.")
            if not components and expected_total is not None and len(rows) != expected_total:
                raise ApiError("VCF Fleet node pagination ended before its advertised total.")
            return rows
        if not page_rows and expected_pages is None:
            if not components and expected_total is not None and len(rows) != expected_total:
                raise ApiError("VCF Fleet node pagination ended early.")
            return rows
    raise ApiError("VCF Fleet pagination exceeded max_pages; incomplete inventory was not exported.")


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Read Fleet LCM directly and fan out only from its component inventory."""
    if resource not in RESOURCE_PATHS[COMPONENT]:
        raise ApiError("Unknown VCF Fleet inventory resource.")
    _integer(page_size, "requested page size", 1)
    _integer(max_pages, "maximum page count", 1)
    components = _paginate(client, RESOURCE_PATHS[COMPONENT]["components"], "components", page_size, max_pages, components=True)
    if resource == "components":
        return components
    result = []
    for component in components:
        identity = component.get("id")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", identity):
            raise ApiError("VCF Fleet returned an unusable component identifier.")
        path = RESOURCE_PATHS[COMPONENT][resource].format(component_id=quote(identity, safe=""))
        if resource == "component_nodes":
            nodes = _paginate(client, path, "nodes", page_size, max_pages)
            for node in nodes:
                if "component_id" in node and node["component_id"] != identity:
                    raise ApiError("Fleet node refers to a different component.")
                result.append(dict(node, component_id=identity))
        else:
            status = client.get(path)
            if not isinstance(status, dict) or not isinstance(status.get("status"), str):
                raise ApiError("VCF Fleet returned an unexpected component status.")
            if status.get("id", identity) != identity:
                raise ApiError("VCF Fleet status refers to a different component.")
            result.append(dict(status, component_id=identity))
    return result
