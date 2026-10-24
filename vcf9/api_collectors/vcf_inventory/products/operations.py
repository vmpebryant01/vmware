"""Read-only VCF Operations inventory. Author: Paul Bryant."""

import hashlib
import json
import os

from ..http_client import ApiError


COMPONENT = "vcf_operations"
BASE_PATH = "/suite-api/api"
RESOURCE_PATHS = {COMPONENT: {
    "resources": BASE_PATH + "/resources",
    "adapters": BASE_PATH + "/adapters",
    "alerts": BASE_PATH + "/alerts",
    "policies": BASE_PATH + "/policies",
}}
DEFAULT_RESOURCES = {COMPONENT: list(RESOURCE_PATHS[COMPONENT])}
ALLOWED_OPERATIONS = {
    (COMPONENT, "POST", BASE_PATH + "/auth/token/acquire"),
    (COMPONENT, "POST", BASE_PATH + "/auth/token/release"),
}
ARRAY_KEYS = {"resources": "resourceList", "adapters": "adapterInstancesInfoDto",
              "alerts": "alerts", "policies": "policySummaries"}
FILTER_KEYS = {
    "resources": {"name", "regex", "adapterKind", "resourceKind", "collectorName", "collectorId",
                  "adapterInstanceId", "recentlyAdded", "resourceState", "resourceStatus",
                  "resourceHealth", "parentId", "resourceId", "propertyName", "propertyValue",
                  "statKey", "statKeyLowerBound", "statKeyUpperBound", "statKeyInclusive", "includeRelated"},
    "adapters": {"adapterKindKey"},
    "alerts": {"id", "resourceId"},
    "policies": {"activesOnly"},
}


def validate_target(target):
    """Validate product options before any credentials are read or APIs called."""
    if target.get("token_scheme", "OpsToken") not in ("OpsToken", "Bearer"):
        raise ValueError("VCF Operations token_scheme must be OpsToken or Bearer.")
    if "token_scheme" in target and not target.get("token_env"):
        raise ValueError("VCF Operations token_scheme applies only to token_env authentication.")
    filters = target.get("filters", {})
    if not isinstance(filters, dict):
        raise ValueError("VCF Operations filters must be an object.")
    for resource, values in filters.items():
        if resource not in FILTER_KEYS or not isinstance(values, dict) or set(values) - FILTER_KEYS[resource]:
            raise ValueError("An unsupported VCF Operations inventory filter was configured.")


def _state(client):
    state = getattr(client, "_product_state", None)
    if not isinstance(state, dict):
        state = {}
        client._product_state = state
    return state


def _usable_token(value):
    return isinstance(value, str) and bool(value) and not any(char.isspace() for char in value)


def authenticate(client):
    """Acquire a local/auth-source OpsToken, or use a caller-supplied token."""
    state = _state(client)
    state["operations_owned_token"] = False
    client.headers.pop("Authorization", None)
    target = client.target
    if target.get("token_env"):
        token = os.environ.get(target["token_env"])
        scheme = target.get("token_scheme", "OpsToken")
        if scheme not in ("OpsToken", "Bearer"):
            raise ApiError("VCF Operations token_scheme must be OpsToken or Bearer.")
        if not _usable_token(token):
            raise ApiError("The VCF Operations token environment variable is missing, empty, or invalid.")
        client.headers["Authorization"] = scheme + " " + token
        return
    username = os.environ.get(target.get("username_env", ""))
    password = os.environ.get(target.get("password_env", ""))
    if not username or not password:
        raise ApiError("Required VCF Operations username/password environment variables are missing or empty.")
    body = {"username": username, "password": password}
    if target.get("auth_source"):
        body["authSource"] = target["auth_source"]
    response = client.request("POST", BASE_PATH + "/auth/token/acquire", body=body)
    if not isinstance(response, dict) or not _usable_token(response.get("token")):
        raise ApiError("VCF Operations did not return a usable OpsToken.")
    client.headers["Authorization"] = "OpsToken " + response["token"]
    state["operations_owned_token"] = True


def close(client):
    """Release only a token acquired by this client; never revoke supplied tokens."""
    state = _state(client)
    try:
        if state.get("operations_owned_token"):
            client.request("POST", BASE_PATH + "/auth/token/release")
    finally:
        state["operations_owned_token"] = False
        client.headers.pop("Authorization", None)


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ApiError(f"Invalid VCF Operations {label}.")
    return value


def _filter_value(value):
    if isinstance(value, list):
        return [_filter_value(item) for item in value]
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _filters(client, resource):
    all_filters = client.target.get("filters", {})
    if not isinstance(all_filters, dict):
        raise ApiError("VCF Operations filters must be an object.")
    values = all_filters.get(resource, {})
    if not isinstance(values, dict) or set(values) - FILTER_KEYS[resource]:
        raise ApiError("An unsupported VCF Operations inventory filter was configured.")
    return {key: _filter_value(value) for key, value in values.items()}


def _rows(payload, resource):
    if not isinstance(payload, dict):
        raise ApiError("VCF Operations returned an unexpected collection envelope.")
    values = payload.get(ARRAY_KEYS[resource])
    # The schema permits omitted arrays. A zero total explicitly establishes emptiness.
    if values is None and isinstance(payload.get("pageInfo"), dict) and payload["pageInfo"].get("totalCount") == 0:
        values = []
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise ApiError("VCF Operations returned an unexpected inventory array.")
    return values


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Collect documented inventory GETs and detect incomplete or repeated pages."""
    if resource not in RESOURCE_PATHS[COMPONENT]:
        raise ApiError("Unknown VCF Operations inventory resource.")
    _integer(page_size, "page size", minimum=1)
    _integer(max_pages, "maximum page count", minimum=1)
    params = _filters(client, resource)
    path = RESOURCE_PATHS[COMPONENT][resource]
    if resource in ("adapters", "policies"):
        return _rows(client.get(path, params=params), resource)
    combined = []
    fingerprints = set()
    identifiers = set()
    expected_total = None
    id_key = "identifier" if resource == "resources" else "alertId"
    for page in range(max_pages):
        query = dict(params, page=page, pageSize=page_size)
        payload = client.get(path, params=query)
        rows = _rows(payload, resource)
        page_info = payload.get("pageInfo")
        if page_info is not None:
            if not isinstance(page_info, dict):
                raise ApiError("VCF Operations returned invalid pageInfo.")
            if "page" in page_info and _integer(page_info["page"], "page number") != page:
                raise ApiError("VCF Operations returned an unexpected page number.")
            if "pageSize" in page_info:
                _integer(page_info["pageSize"], "response page size", minimum=1)
            if "totalCount" in page_info:
                total = _integer(page_info["totalCount"], "total count")
                if expected_total is not None and total != expected_total:
                    raise ApiError("VCF Operations inventory changed during pagination; rerun the collection.")
                expected_total = total
        fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
        if rows and fingerprint in fingerprints:
            raise ApiError("VCF Operations repeated an inventory page.")
        fingerprints.add(fingerprint)
        for row in rows:
            identifier = row.get(id_key)
            if isinstance(identifier, str) and identifier:
                if identifier in identifiers:
                    raise ApiError("VCF Operations repeated an inventory identifier; rerun the collection.")
                identifiers.add(identifier)
        combined.extend(rows)
        if expected_total is not None:
            if len(combined) > expected_total:
                raise ApiError("VCF Operations returned more records than totalCount.")
            if len(combined) == expected_total:
                return combined
        if not rows:
            if expected_total is not None:
                raise ApiError("VCF Operations pagination ended before totalCount was reached.")
            return combined
        # Without totalCount, request another page even after a short page. This
        # accommodates a server that returns fewer rows than the requested size.
    raise ApiError("VCF Operations pagination exceeded max_pages without establishing completion.")
