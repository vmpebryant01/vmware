"""Bounded product and server version evidence. Author: Paul Bryant."""

import re

from .http_client import ApiError


# Static GET contracts only. HCX and the configured vSAN schema have distinct
# plans below. The service scope is part of every observation, including errors.
VERSION_PROBES = {
    "sddc_manager": ("/v1/system/appliance-info", ("version",)),
    "vcenter": ("/api/appliance/system/version", ("version", "build")),
    "nsx": ("/api/v1/node", ("node_version", "product_version")),
    "vcf_operations": ("/suite-api/api/versions/current", ("major", "minor", "minorMinor", "patch", "buildNumber")),
    "vcf_fleet": ("/fleet-lcm/v1/system", ("currentVersion",)),
    "live_site_recovery": ("/api/rest/srm/v2/server/info", ("version", "build_number")),
    "vsphere_replication": ("/api/rest/vr/v2/info", ("version", "build_number")),
}
VERSION_SCOPES = {
    "sddc_manager": "sddc_manager_appliance",
    "vcenter": "vcenter_appliance",
    "nsx": "nsx_local_node",
    "vcf_operations": "operations_service",
    "vcf_fleet": "fleet_lcm_system",
    "live_site_recovery": "local_site_recovery_server",
    "vsphere_replication": "local_replication_management_server",
    "hcx": "local_hcx_manager",
    "vsan": "vcenter_server_for_vsan",
    "vcf_automation": "automation_product_build",
}
HCX_VERSION_PATH = "/hybridity/api/hcspAppliances"
_NUMERIC_VERSION = re.compile(r"[0-9]+(?:[.][0-9]+){0,9}\Z")
_NUMBERED_BUILD = re.compile(r"[0-9]+(?:[.-][0-9]+){0,9}\Z")
_OPERATIONS_INTEGER_FIELDS = frozenset(("major", "minor", "minorMinor", "patch", "buildNumber"))


def allow_query(component, method, path, params, body):
    """Permit exactly the published local HCX appliance read query."""
    return (component == "hcx" and method == "POST" and path == HCX_VERSION_PATH
            and params in (None, {}) and isinstance(body, dict)
            and set(body) == {"action", "filter"} and body["action"] == "query"
            and isinstance(body["filter"], dict) and set(body["filter"]) == {"local"}
            and type(body["filter"]["local"]) is str and body["filter"]["local"] == "true")


def _failure(exc):
    """Exclude remote messages and endpoint details from failure evidence."""
    status, category = getattr(exc, "status", None), getattr(exc, "category", None)
    if category == "request_budget":
        name = "request_budget_exhausted"
    elif status in (401, 403):
        name = "access_denied"
    elif status == 404:
        name = "endpoint_not_found"
    elif category == "tls":
        name = "tls_error"
    elif category == "network":
        name = "network_error"
    else:
        name = "query_failure"
    result = {"status": name}
    if type(status) is int and 100 <= status <= 599:
        result["http_status"] = status
    return result


def _fields(payload, approved, numeric_only, integer_fields=()):
    result = {}
    pattern = _NUMERIC_VERSION if numeric_only else _NUMBERED_BUILD
    for key in approved:
        value = payload.get(key)
        if key in integer_fields:
            if type(value) is int and 0 <= value <= 2 ** 63 - 1:
                result[key] = value
        elif isinstance(value, str) and len(value) <= 128 and pattern.fullmatch(value):
            result[key] = value
    return result


def _unknown(reason, scope):
    return {"status": "unknown", "scope": scope, "reason": reason}


def probe_version(client, target, numeric_only=False):
    """Perform at most one version request through the existing authenticated client.

    The caller owns authentication, cleanup, retries and request budgets. No
    configured product version is promoted to observed evidence. Release names,
    addresses, identifiers, certificates and unrecognized version strings are
    excluded. Numeric-only mode also excludes build strings containing hyphens.
    """
    component = target.get("component")
    scope = VERSION_SCOPES.get(component, "unverified_component")
    if component == "vcf_automation":
        return _unknown("The selected Automation API family has no verified product-build probe; a requested or supported API version is not the installed product build.", scope)
    if component not in VERSION_PROBES and component not in ("hcx", "vsan"):
        return _unknown("No verified version probe is implemented for this component.", scope)
    if component == "hcx" and target.get("auth_source", "credentials") == "vcf_sso":
        return _unknown("The documented local HCX manager version query requires an HCX session token; its VCF SSO token contract is not verified.", scope)
    if component in ("live_site_recovery", "vsphere_replication") and target.get("api_version", "v2") != "v2":
        return _unknown("The version probe implements the v2 recovery gateway only.", scope)
    if component == "vsan":
        from .products.vsan import API_VERSIONS, DEFAULT_API_VERSION
        schema = target.get("api_version", DEFAULT_API_VERSION)
        if schema not in API_VERSIONS:
            return _unknown("The configured vSAN JSON schema is not supported by this probe.", scope)
    try:
        if component == "hcx":
            payload = client.request("POST", HCX_VERSION_PATH,
                                     body={"action": "query", "filter": {"local": "true"}})
            if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
                raise ApiError("Unexpected local HCX manager version response.")
            if len(payload) != 1:
                return _unknown("The local HCX manager query did not identify exactly one manager; no manager was selected by name or position.", scope)
            fields = _fields(payload[0], ("version",), numeric_only)
        elif component == "vsan":
            payload = client.request("GET", "/sdk/vim25/" + schema + "/ServiceInstance/ServiceInstance/content")
            about = payload.get("about") if isinstance(payload, dict) else None
            if not isinstance(about, dict) or about.get("apiType") != "VirtualCenter":
                raise ApiError("Expected vCenter ServiceContent about information.")
            fields = _fields(about, ("version", "build"), numeric_only)
            if not fields:
                return _unknown("No recognized vCenter product version or build fields were returned; API schema versions alone do not identify the installed product build.", scope)
            api_fields = _fields(about, ("apiVersion",), True)
            result = {"status": "reported", "scope": scope, "fields": fields,
                      "limitations": ["This evidence identifies the vCenter server, not ESX hosts or individual vSAN software components."]}
            if api_fields:
                result["server_api_version"] = api_fields["apiVersion"]
            return result
        else:
            path, approved = VERSION_PROBES[component]
            payload = client.request("GET", path)
            if not isinstance(payload, dict):
                raise ApiError("Unexpected version response structure.")
            if component in ("live_site_recovery", "vsphere_replication"):
                metadata = payload.get("_meta")
                if metadata is not None and (not isinstance(metadata, dict) or metadata.get("errors")):
                    raise ApiError("Recovery API returned incomplete server information.")
            fields = _fields(payload, approved, numeric_only,
                             _OPERATIONS_INTEGER_FIELDS if component == "vcf_operations" else ())
        if fields:
            return {"status": "reported", "scope": scope, "fields": fields}
        return _unknown("No recognized release or build fields were returned.", scope)
    except ApiError as exc:
        return dict(_failure(exc), scope=scope)
