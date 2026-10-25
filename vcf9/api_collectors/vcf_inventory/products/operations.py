"""Read-only VCF Operations inventory. Author: Paul Bryant."""

import hashlib
import json
import math
import os
import re
from urllib.parse import quote

from ..http_client import ApiError


COMPONENT = "vcf_operations"
BASE_PATH = "/suite-api/api"
RESOURCE_PATHS = {COMPONENT: {
    "resources": BASE_PATH + "/resources",
    "adapters": BASE_PATH + "/adapters",
    "alerts": BASE_PATH + "/alerts",
    "policies": BASE_PATH + "/policies",
    "latest_metrics": BASE_PATH + "/resources/stats/latest",
    "relationships": BASE_PATH + "/resources/{resource_id}/relationships",
}}
DEFAULT_RESOURCES = {COMPONENT: ["resources", "adapters", "alerts", "policies"]}
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
    selected = target.get("resources", DEFAULT_RESOURCES[COMPONENT])
    for field, maximum in (("resource_ids", 1000), ("stat_keys", 1000)):
        values = target.get(field)
        if values is not None and (
            not isinstance(values, list) or not values or len(values) > maximum
            or any(not isinstance(value, str) or not value or len(value) > 1000
                   or any(ord(char) < 32 or ord(char) == 127 for char in value) for value in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError(f"VCF Operations {field} must be a nonempty unique string array with at most {maximum} entries.")
    if any(resource in selected for resource in ("latest_metrics", "relationships")) and not target.get("resource_ids"):
        raise ValueError("VCF Operations latest_metrics and relationships require explicit resource_ids.")
    if "latest_metrics" in selected and not target.get("stat_keys"):
        raise ValueError("VCF Operations latest_metrics requires explicit stat_keys.")
    if target.get("resource_ids") and any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", value) for value in target["resource_ids"]):
        raise ValueError("VCF Operations resource_ids must be identifiers without path separators.")


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
    if resource in ("latest_metrics", "relationships"):
        try:
            validate_target(dict(client.target, resources=[resource]))
        except ValueError as exc:
            raise ApiError(str(exc)) from None
        return _latest_metrics(client) if resource == "latest_metrics" else _relationships(client, page_size, max_pages)
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


def _unit_metadata(client, resource_id, stat_keys, cache):
    """Return only exact metric-key metadata supplied by Operations."""
    detail = client.get(BASE_PATH + "/resources/" + quote(resource_id, safe=""))
    if not isinstance(detail, dict) or not isinstance(detail.get("resourceKey"), dict):
        raise ApiError("VCF Operations returned invalid resource metadata for metrics.")
    if detail.get("identifier", resource_id) != resource_id:
        raise ApiError("VCF Operations metric metadata refers to a different resource.")
    resource_key = detail["resourceKey"]
    adapter, kind = resource_key.get("adapterKindKey"), resource_key.get("resourceKindKey")
    if not all(isinstance(value, str) and value for value in (adapter, kind)):
        return resource_key, {}
    cache_key = (adapter, kind)
    if cache_key not in cache:
        path = BASE_PATH + "/adapterkinds/" + quote(adapter, safe="") + "/resourcekinds/" + quote(kind, safe="") + "/statkeys"
        payload = client.get(path, params={"attributeKeys": stat_keys, "retrieveAttributeKeys": "true"})
        attributes = payload.get("resourceTypeAttributes", []) if isinstance(payload, dict) else None
        if not isinstance(attributes, list) or any(not isinstance(item, dict) for item in attributes):
            raise ApiError("VCF Operations returned invalid measurement-unit metadata.")
        metadata = {}
        for item in attributes:
            key = item.get("key")
            if isinstance(key, str) and key in stat_keys:
                if key in metadata:
                    raise ApiError("VCF Operations repeated a measurement-unit metadata key.")
                if item.get("unit") is not None and not isinstance(item["unit"], str):
                    raise ApiError("VCF Operations returned an invalid measurement unit.")
                metadata[key] = item
        cache[cache_key] = metadata
    return resource_key, cache[cache_key]


def _latest_metrics(client):
    """Preserve native timestamps/data and add units only from exact API metadata."""
    selected = client.target["stat_keys"]
    result, cache = [], {}
    for identity in client.target["resource_ids"]:
        resource_key, units = _unit_metadata(client, identity, selected, cache)
        payload = client.get(RESOURCE_PATHS[COMPONENT]["latest_metrics"], params={
            "resourceId": [identity], "statKey": selected, "maxSamples": 1,
        })
        values = payload.get("values", []) if isinstance(payload, dict) else None
        if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
            raise ApiError("VCF Operations returned invalid latest-metrics inventory.")
        stats, seen = [], set()
        for value in values:
            if value.get("resourceId") != identity:
                raise ApiError("VCF Operations returned metrics outside the requested resource scope.")
            stat_list = value.get("stat-list", {})
            series = stat_list.get("stat", []) if isinstance(stat_list, dict) else None
            if not isinstance(series, list) or any(not isinstance(stat, dict) for stat in series):
                raise ApiError("VCF Operations returned an invalid metric-series array.")
            stats.extend(series)
        for stat in stats:
            key = stat.get("statKey", {}).get("key") if isinstance(stat.get("statKey"), dict) else None
            if key not in selected or key in seen:
                raise ApiError("VCF Operations returned an unexpected or repeated metric key.")
            seen.add(key)
            timestamps, data = stat.get("timestamps"), stat.get("data")
            if (not isinstance(timestamps, list) or not isinstance(data, list) or len(timestamps) != len(data)
                    or any(type(stamp) is not int or stamp < 0 for stamp in timestamps)
                    or any(type(number) not in (int, float) or not math.isfinite(number) for number in data)):
                raise ApiError("VCF Operations returned mismatched or invalid metric samples.")
            reported_unit = stat.get("unit")
            if reported_unit is not None and not isinstance(reported_unit, str):
                raise ApiError("VCF Operations returned an invalid measurement unit.")
            unit = units.get(key, {}).get("unit")
            if reported_unit and unit is not None and reported_unit != unit:
                raise ApiError("VCF Operations returned conflicting series and attribute-metadata units.")
            record = dict(stat, resource_id=identity, resource_name=resource_key.get("name"), stat_key=key, unit=unit)
            if "unit" in stat:
                record["reported_series_unit"] = reported_unit
            if not timestamps:
                record["availability"] = "no_samples_returned"
            result.append(record)
        for key in selected:
            if key not in seen:
                result.append({"resource_id": identity, "resource_name": resource_key.get("name"), "stat_key": key,
                               "timestamps": [], "data": [], "unit": units.get(key, {}).get("unit"),
                               "availability": "no_samples_returned"})
    return result


def _relationships(client, page_size, max_pages):
    """Keep parent and child direction explicit for each requested source resource."""
    result = []
    for identity in client.target["resource_ids"]:
        path = RESOURCE_PATHS[COMPONENT]["relationships"].format(resource_id=quote(identity, safe=""))
        for relation in ("PARENT", "CHILD"):
            expected_total, seen = None, set()
            count = 0
            for page in range(max_pages):
                payload = client.get(path, params={"relationshipType": relation, "page": page, "pageSize": page_size})
                rows = _rows(payload, "resources")
                if payload.get("relationshipType", relation) != relation:
                    raise ApiError("VCF Operations returned a different relationship direction.")
                info = payload.get("pageInfo") or {}
                if not isinstance(info, dict):
                    raise ApiError("VCF Operations returned invalid relationship pageInfo.")
                if "page" in info and _integer(info["page"], "relationship page") != page:
                    raise ApiError("VCF Operations returned an unexpected relationship page.")
                if info.get("totalCount") is not None:
                    total = _integer(info["totalCount"], "relationship total")
                    if expected_total is not None and total != expected_total:
                        raise ApiError("VCF Operations relationships changed during pagination.")
                    expected_total = total
                for row in rows:
                    related = row.get("identifier")
                    if not isinstance(related, str) or not related or related in seen:
                        raise ApiError("VCF Operations returned a missing or repeated relationship identifier.")
                    seen.add(related)
                    result.append({"resource_id": identity, "relationship_type": relation,
                                   "related_resource_id": related, "related_resource": row})
                count += len(rows)
                if expected_total is not None and count > expected_total:
                    raise ApiError("VCF Operations returned more relationships than totalCount.")
                if expected_total is not None and count == expected_total:
                    break
                if not rows:
                    if expected_total is not None:
                        raise ApiError("VCF Operations relationship pagination ended early.")
                    break
            else:
                raise ApiError("VCF Operations relationships exceeded max_pages; incomplete inventory was not exported.")
    return result
