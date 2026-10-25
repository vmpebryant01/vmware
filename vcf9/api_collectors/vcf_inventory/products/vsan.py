"""Cached vSAN health and capacity queries. Author: Paul Bryant."""

import os
import re

from ..http_client import ApiError


COMPONENT = "vsan"
DEFAULT_API_VERSION = "9.0.0.0"
API_VERSIONS = ("9.0.0.0", "9.1.0.0", "9.1.1.0")
BASE_PATH = "/sdk/vim25/{api_version}"
RESOURCE_PATHS = {COMPONENT: {
    "health_summary": BASE_PATH + "/vsan/VsanVcClusterHealthSystem/vsan-cluster-health-system/VsanQueryVcClusterHealthSummary",
    "space_usage": BASE_PATH + "/vsan/VsanSpaceReportSystem/vsan-cluster-space-report-system/VsanQuerySpaceUsage",
}}
DEFAULT_RESOURCES = {COMPONENT: ["health_summary", "space_usage"]}
# Authentication paths contain the SessionManager ID discovered from content.
ALLOWED_OPERATIONS = set()
HEALTH_FIELDS = ("cluster", "timestamp", "overallHealth", "overallHealthDescription", "healthScore",
                 "objectHealth", "physicalDisksHealth", "diskBalance", "networkHealth", "limitHealth")
_CLUSTER_ID = re.compile(r"domain-c[0-9]{1,18}")
_MANAGED_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}")
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def validate_target(target):
    """Require explicit cluster managed-object IDs and a known schema release."""
    clusters = target.get("cluster_ids")
    if (not isinstance(clusters, list) or not 1 <= len(clusters) <= 1000
            or any(not isinstance(value, str) or not _CLUSTER_ID.fullmatch(value) for value in clusters)
            or len(set(clusters)) != len(clusters)):
        raise ValueError("vSAN cluster_ids must contain 1 to 1000 unique vCenter cluster IDs such as domain-c123.")
    if target.get("api_version", DEFAULT_API_VERSION) not in API_VERSIONS:
        raise ValueError("vSAN api_version must be 9.0.0.0, 9.1.0.0, or 9.1.1.0.")
    has_token = bool(target.get("token_env"))
    has_username, has_password = bool(target.get("username_env")), bool(target.get("password_env"))
    if (has_token and (has_username or has_password)) or (not has_token and not (has_username and has_password)):
        raise ValueError("vSAN requires either token_env or username_env and password_env.")
    for field in ("token_env", "username_env", "password_env"):
        if field in target and (not isinstance(target[field], str) or not _ENVIRONMENT_NAME.fullmatch(target[field])):
            raise ValueError("vSAN authentication fields must name environment variables.")


def _path(resource, version):
    return RESOURCE_PATHS[COMPONENT][resource].format(api_version=version)


def _state(client):
    if not isinstance(getattr(client, "_product_state", None), dict):
        client._product_state = {}
    return client._product_state


def _usable_token(value):
    return isinstance(value, str) and bool(value) and all(33 <= ord(character) <= 126 for character in value)


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,4}", value):
        raise ApiError("vSAN endpoint did not provide a recognized API version.")
    return tuple(int(part) for part in value.split("."))


def allow_request(component, method, path):
    """Permit only the documented dynamic SessionManager login/logout paths."""
    if component != COMPONENT or method != "POST":
        return False
    return any(re.fullmatch(r"/sdk/vim25/" + re.escape(version)
                           + r"/SessionManager/[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}/(?:Login|Logout)", path)
               for version in API_VERSIONS)


def allow_query(component, method, path, params, body):
    """Allow the two exact read-only query contracts; health must use the cache."""
    if component != COMPONENT or method != "POST" or params not in (None, {}) or not isinstance(body, dict):
        return False
    cluster = body.get("cluster")
    if (not isinstance(cluster, dict) or set(cluster) != {"type", "value"}
            or cluster["type"] != "ClusterComputeResource" or not isinstance(cluster["value"], str)
            or not _CLUSTER_ID.fullmatch(cluster["value"])):
        return False
    for version in API_VERSIONS:
        if path == _path("health_summary", version):
            return (set(body) == {"cluster", "fetchFromCache", "includeObjUuids", "fields"}
                    and body["fetchFromCache"] is True and body["includeObjUuids"] is False
                    and body["fields"] == list(HEALTH_FIELDS))
        if path == _path("space_usage", version):
            return set(body) == {"cluster", "whatifCapacityOnly"} and body["whatifCapacityOnly"] is False
    return False


def authenticate(client):
    """Validate the configured vCenter, then use a JSON API session header."""
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    state = _state(client)
    state["vsan_owned_session"] = False
    client.headers.pop("vmware-api-session-id", None)
    version = client.target.get("api_version", DEFAULT_API_VERSION)
    content = client.get(BASE_PATH.format(api_version=version) + "/ServiceInstance/ServiceInstance/content")
    about = content.get("about") if isinstance(content, dict) else None
    if not isinstance(about, dict) or about.get("apiType") != "VirtualCenter":
        raise ApiError("vSAN collector requires a vCenter VirtualCenter endpoint.")
    server_version = _version(about.get("apiVersion"))
    if server_version[0] != 9 or server_version < _version(version):
        raise ApiError("vSAN collector requires a vCenter 9.x API supporting the configured schema release.")
    manager = content.get("sessionManager")
    if (not isinstance(manager, dict) or manager.get("type") != "SessionManager"
            or not isinstance(manager.get("value"), str) or not _MANAGED_ID.fullmatch(manager["value"])):
        raise ApiError("vSAN endpoint returned an unusable SessionManager reference.")
    state.update(vsan_api_version=version, vsan_server_api_version=about["apiVersion"], vsan_session_manager=manager["value"])
    if client.target.get("token_env"):
        token = os.environ.get(client.target["token_env"])
        if not _usable_token(token):
            raise ApiError("The vSAN JSON session environment variable is missing, empty, or invalid.")
    else:
        username = os.environ.get(client.target["username_env"])
        password = os.environ.get(client.target["password_env"])
        if not username or not password:
            raise ApiError("The vSAN username/password environment variables are missing or empty.")
        path = BASE_PATH.format(api_version=version) + "/SessionManager/" + manager["value"] + "/Login"
        response, headers = client.request("POST", path, body={"userName": username, "password": password}, include_headers=True)
        token = headers.get("vmware-api-session-id") if isinstance(headers, dict) else None
        if not isinstance(response, dict) or not _usable_token(token):
            raise ApiError("vSAN JSON login did not return a usable session response header.")
        state["vsan_owned_session"] = True
    client.headers["vmware-api-session-id"] = token


def close(client):
    """Log out only a session created by this collector, then clear its header."""
    state = _state(client)
    try:
        if state.get("vsan_owned_session"):
            path = BASE_PATH.format(api_version=state["vsan_api_version"]) + "/SessionManager/" + state["vsan_session_manager"] + "/Logout"
            client.request("POST", path)
    finally:
        state["vsan_owned_session"] = False
        client.headers.pop("vmware-api-session-id", None)


def _validate_health(payload, cluster_id):
    if (not isinstance(payload.get("overallHealth"), str) or not payload["overallHealth"]
            or not isinstance(payload.get("overallHealthDescription"), str)):
        raise ApiError("vSAN returned an invalid health-summary response.")
    if "timestamp" in payload and not isinstance(payload["timestamp"], str):
        raise ApiError("vSAN returned an invalid cached-health timestamp.")
    if "healthScore" in payload and (type(payload["healthScore"]) is not int or not 0 <= payload["healthScore"] <= 100):
        raise ApiError("vSAN returned an invalid health score.")
    reference = payload.get("cluster")
    if reference is not None and (not isinstance(reference, dict) or reference.get("type") != "ClusterComputeResource" or reference.get("value") != cluster_id):
        raise ApiError("vSAN health response refers to a different cluster.")
    for field in ("objectHealth", "diskBalance", "networkHealth", "limitHealth"):
        if field in payload and not isinstance(payload[field], dict):
            raise ApiError("vSAN returned an invalid optional health section.")
    if "physicalDisksHealth" in payload and (not isinstance(payload["physicalDisksHealth"], list)
                                           or any(not isinstance(row, dict) for row in payload["physicalDisksHealth"])):
        raise ApiError("vSAN returned an invalid physical-disk health array.")


def _validate_space(payload):
    total = payload.get("totalCapacityB")
    if type(total) is not int or total < 0:
        raise ApiError("vSAN returned an invalid total capacity in bytes.")
    if "freeCapacityB" in payload and (type(payload["freeCapacityB"]) is not int or not 0 <= payload["freeCapacityB"] <= total):
        raise ApiError("vSAN returned invalid free capacity in bytes.")


def _query_body(resource, identity):
    body = {"cluster": {"type": "ClusterComputeResource", "value": identity}}
    if resource == "health_summary":
        body.update(fetchFromCache=True, includeObjUuids=False, fields=list(HEALTH_FIELDS))
    else:
        body["whatifCapacityOnly"] = False
    return body


def probe_request(target, resource):
    """Probe only the first explicitly configured cluster with the same safe query."""
    validate_target(target)
    if resource not in RESOURCE_PATHS[COMPONENT]:
        return None
    version = target.get("api_version", DEFAULT_API_VERSION)
    note = "Read-only query for the first explicitly configured cluster; remaining clusters are not probed."
    if resource == "health_summary":
        note += " Health is read from the existing cache."
    return "POST", _path(resource, version), None, _query_body(resource, target["cluster_ids"][0]), note


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Issue one documented query per explicitly selected cluster, without tasks."""
    if resource not in RESOURCE_PATHS[COMPONENT]:
        raise ApiError("Unknown vSAN inventory resource.")
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    version = client.target.get("api_version", DEFAULT_API_VERSION)
    state = _state(client)
    if not _usable_token(client.headers.get("vmware-api-session-id")) or state.get("vsan_api_version") != version:
        raise ApiError("Authenticate the vSAN JSON session before collection.")
    result = []
    for identity in client.target["cluster_ids"]:
        body = _query_body(resource, identity)
        path = _path(resource, version)
        if not allow_query(COMPONENT, "POST", path, None, body):
            raise ApiError("The vSAN query does not match the read-only contract.")
        payload = client.request("POST", path, body=body)
        if not isinstance(payload, dict):
            raise ApiError("vSAN returned an unexpected query response envelope.")
        if "cluster_id" in payload and payload["cluster_id"] != identity:
            raise ApiError("vSAN response contains a conflicting cluster identifier.")
        _validate_health(payload, identity) if resource == "health_summary" else _validate_space(payload)
        result.append(dict(payload, cluster_id=identity, api_version=version, server_api_version=state["vsan_server_api_version"],
                           **({"fetch_from_cache": True} if resource == "health_summary" else {})))
    return result
