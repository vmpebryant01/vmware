"""Bounded read-only connectivity and capability probes. Author: Paul Bryant."""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from .http_client import ApiError, HttpClient
from .version_probes import VERSION_PROBES, probe_version


_ERRORS = {"access_denied", "endpoint_not_found", "tls_error", "network_error", "query_failure"}


def _failure(exc):
    category = getattr(exc, "category", None)
    status = getattr(exc, "status", None)
    if status in (401, 403):
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
    if type(status) is int:
        result["http_status"] = status
    return result


def _transport(result, observation):
    status = observation["status"]
    if status == "tls_error":
        result["tls"] = "error"
    elif status == "network_error":
        if result["connectivity"] == "unknown":
            result["connectivity"] = "error"
    elif status in ("accessible", "reported") or "http_status" in observation:
        result["connectivity"] = "reachable"
        if result["tls"] != "error":
            result["tls"] = "verified"


def _session_login(target):
    component = target["component"]
    if component in ("sddc_manager", "vcenter"):
        return True
    if component in ("hcx", "live_site_recovery", "vsphere_replication"):
        return target.get("auth_source", "credentials") == "credentials"
    return component == "vcf_operations" and not target.get("token_env")


def _probe_plan(target, resource, path):
    """Return one documented request and scope note, without scope discovery."""
    component = target["component"]
    fields = {"site": target.get("site_id", "default"), "ep": target.get("enforcement_point_id", "default"),
              "domain": target.get("domain_id", "default"), "domain_id": target.get("domain_id", "default")}
    notes = []
    for placeholder, option in (("policy_id", "policy_ids"), ("srm_id", "srm_ids"), ("resource_id", "resource_ids")):
        if "{" + placeholder + "}" in path:
            values = target.get(option)
            if not isinstance(values, list) or not values:
                return None, None, f"An explicit {option} scope is required for a representative probe."
            fields[placeholder] = values[0]
            notes.append(f"Only the first configured {option} identifier is probed.")
    if resource == "certificates":
        values = target.get("domain_ids")
        if not isinstance(values, list) or not values:
            return None, None, "Certificate preflight requires an explicit domain_ids scope; domains are not discovered."
        fields["domain_id"] = values[0]
        notes.append("Only the first configured domain_ids identifier is probed.")
    if "{pairing_id}" in path:
        if not target.get("pairing_id"):
            return None, None, "An explicit pairing_id is required; pairings are not discovered."
        fields["pairing_id"] = target["pairing_id"]
    try:
        path = path.format(**{key: quote(str(value), safe="") for key, value in fields.items()})
    except KeyError:
        return None, None, "This dynamic resource does not have a verified representative probe."
    if component == "sddc_manager":
        params = {} if resource in ("appliance_info", "network_pools") else {"pageNumber": 0, "pageSize": 1}
        if resource == "failed_tasks":
            params["completedAfter"] = int((datetime.now(timezone.utc) - timedelta(days=target.get("task_days", 30))).timestamp() * 1000)
    elif component == "nsx":
        params = {"page_size": 1}
    elif component == "vcenter":
        params = dict(target.get("filters", {}).get(resource, {}))
        notes.append("This list API has no documented page-size selector; one request can return multiple records.")
    elif component == "hcx":
        params = {}
        notes.append("This list API has no documented page-size selector; one request can return multiple records.")
    elif component == "vcf_fleet":
        if resource != "components":
            return None, None, "Fleet component identifiers are not discovered during preflight."
        params = {"pageNumber": 1, "pageSize": 1, "includeConsumptionVsp": "true", "includeVcdMigrator": "true"}
    elif component == "vcf_automation":
        if target.get("api_family") == "provider":
            params = {"page": 1, "pageSize": 1}
        elif resource in ("cloud_accounts", "cloud_zones", "fabric_networks"):
            params = {"$top": 1, "$skip": 0}
        else:
            params = {"page": 0, "size": 1}
    elif component == "vcf_operations":
        params = dict(target.get("filters", {}).get(resource, {}))
        if resource == "latest_metrics":
            ids, keys = target.get("resource_ids"), target.get("stat_keys")
            if not ids or not keys:
                return None, None, "Explicit resource_ids and stat_keys are required for a metrics probe."
            params.update(resourceId=[ids[0]], statKey=[keys[0]], maxSamples=1)
            notes.append("Only the first configured resource and metric key are probed; units are not queried.")
        elif resource == "relationships":
            params.update(relationshipType="PARENT", page=0, pageSize=1)
            notes.append("Only the PARENT relationship direction is probed.")
        elif resource in ("resources", "alerts"):
            params.update(page=0, pageSize=1)
    elif component in ("live_site_recovery", "vsphere_replication"):
        params = {"offset": 0, "limit": 1}
        if component == "vsphere_replication" and resource == "replications":
            params["extended_info"] = "true"
            if target.get("source_vc_guid"):
                params["source_vc_guid"] = target["source_vc_guid"]
    else:
        return None, None, "No verified lightweight probe is defined for this component."
    return path, params, " ".join(notes)


def run_preflight(targets, config, client_factory=HttpClient):
    """Probe selected resources without collecting or exporting inventory bodies."""
    from .collectors import RESOURCE_PATHS, SUPPLEMENTAL_MODULES, resources_for
    from .operational import RESOURCE_PATHS as OPERATIONAL_PATHS
    from .products import protection_recovery

    report = {"author": "Paul Bryant", "schema_version": "1.0", "targets": [], "status": "success",
              "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
              "scope_limits": ["A successful probe covers one request in its stated scope, not every object, permission, or API version."]}
    for target in targets:
        component = target["component"]
        result = {"name": target["name"], "component": component, "connectivity": "unknown", "tls": "unknown",
                  "authentication": {"status": "not_verified"}, "version": {"status": "not_probed"},
                  "capabilities": [], "scope_limits": [], "status": "success"}
        report["targets"].append(result)
        if target.get("version"):
            result["configured_version"] = target["version"]
        client = None
        authenticated = False
        try:
            try:
                client = client_factory(target, timeout=config.get("timeout_seconds", 30), retries=config.get("retries", 2))
                client.authenticate()
                authenticated = True
                result["authentication"]["status"] = "session_established" if _session_login(target) else "configured"
                if _session_login(target):
                    _transport(result, {"status": "accessible"})
            except ApiError as exc:
                result["authentication"] = _failure(exc)
                _transport(result, result["authentication"])
            if client is not None:
                result["version"] = probe_version(client, target)
                _transport(result, result["version"])
            else:
                result["version"]["reason"] = "Client setup did not complete."
            paths = dict(RESOURCE_PATHS.get(component, {}))
            paths.update(OPERATIONAL_PATHS.get(component, {}))
            for resource in resources_for(target):
                capability = {"resource": resource, "status": "not_probed"}
                result["capabilities"].append(capability)
                if not authenticated:
                    capability["reason"] = "Authentication or client setup failed."
                    continue
                path = paths.get(resource)
                if not path:
                    capability["reason"] = "No verified resource route is available."
                    continue
                method, body = "GET", None
                probe_module = next((module for module in SUPPLEMENTAL_MODULES
                                     if module.supports(component, resource) and hasattr(module, "probe_request")), None)
                if probe_module is None:
                    from .products import module_for
                    product = module_for(component)
                    if product is not None and hasattr(product, "probe_request"):
                        probe_module = product
                if probe_module is not None:
                    plan = probe_module.probe_request(target, resource)
                    if plan is None:
                        path, params, note = None, None, "No verified representative probe is available for the configured scope."
                    else:
                        method, path, params, body, note = plan
                else:
                    path, params, note = _probe_plan(target, resource, path)
                if note:
                    capability["scope_limit"] = note
                if path is None:
                    capability["reason"] = note
                    continue
                try:
                    if component in ("live_site_recovery", "vsphere_replication") and resource != "pairings":
                        protection_recovery._ensure_remote(client, target["pairing_id"])
                    if body is None:
                        client.request(method, path, params=params)
                    else:
                        client.request(method, path, params=params, body=body)
                    capability["status"] = "accessible"
                    result["authentication"]["status"] = "verified"
                except ApiError as exc:
                    capability.update(_failure(exc))
                _transport(result, capability)
        finally:
            if client is not None:
                try:
                    client.close()
                    result["session_cleanup"] = {"status": "success"}
                except ApiError as exc:
                    result["session_cleanup"] = _failure(exc)
        checks = [result["authentication"], result["version"], result.get("session_cleanup", {})] + result["capabilities"]
        if any(check.get("status") in _ERRORS for check in checks):
            result["status"] = "incomplete"
            report["status"] = "incomplete"
        elif any(capability["status"] == "not_probed" for capability in result["capabilities"]):
            result["status"] = "partial"
            if report["status"] == "success":
                report["status"] = "partial"
        if component == "nsx":
            result["scope_limits"].append("The node version endpoint requires no permissions and does not verify the supplied authentication.")
        for capability in result["capabilities"]:
            if capability["status"] == "not_probed":
                result["scope_limits"].append(capability["resource"] + ": " + capability.get("reason", "Not probed."))
    report["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return report
