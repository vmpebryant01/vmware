"""VCF Automation organization and provider inventory. Author: Paul Bryant."""

import hashlib
import json
import os
import re

from ..http_client import ApiError


RESOURCE_PATHS = {
    "vcf_automation": {
        "projects": "/project-service/api/projects",
        "blueprints": "/blueprint/api/blueprints",
        "deployments": "/deployment/api/deployments",
        "cloud_accounts": "/iaas/api/cloud-accounts",
        "cloud_zones": "/iaas/api/zones",
        "fabric_networks": "/iaas/api/fabric-networks",
        "organizations": "/cloudapi/1.0.0/orgs",
        "regions": "/cloudapi/v1/regions",
        "provider_zones": "/cloudapi/v1/zones",
        "supervisor_namespaces": "/cloudapi/v1/namespaceSummaries",
        "virtual_private_clouds": "/cloudapi/v1/vpcs",
    }
}
FAMILY_RESOURCES = {
    "all_apps": ("projects", "blueprints", "deployments"),
    "vm_apps": ("projects", "blueprints", "deployments", "cloud_accounts", "cloud_zones", "fabric_networks"),
    "provider": ("organizations", "regions", "provider_zones", "supervisor_namespaces", "virtual_private_clouds"),
}
DEFAULT_RESOURCES = {"vcf_automation": list(FAMILY_RESOURCES["all_apps"])}
ALLOWED_OPERATIONS = set()
IAAS_RESOURCES = {"cloud_accounts", "cloud_zones", "fabric_networks"}


def validate_target(target):
    """Validate configuration only, without reading secrets or making requests."""
    family = target.get("api_family")
    if not isinstance(family, str) or family not in FAMILY_RESOURCES:
        raise ValueError("VCF Automation requires api_family: all_apps, vm_apps, or provider.")
    variable = target.get("token_env")
    if not isinstance(variable, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable):
        raise ValueError("VCF Automation requires token_env naming a bearer access token environment variable.")
    resources = target.get("resources")
    allowed_resources = set(FAMILY_RESOURCES[family])
    if family in ("all_apps", "vm_apps"):
        allowed_resources.add("catalog_items")
        allowed_resources.add("deployment_requests")
    if resources is not None and (
        not isinstance(resources, list) or not resources
        or any(not isinstance(resource, str) or resource not in allowed_resources for resource in resources)
        or len(set(resources)) != len(resources)
    ):
        raise ValueError("VCF Automation resources must belong to the selected api_family.")
    api_version = target.get("api_version")
    if family == "provider":
        if not isinstance(api_version, str) or not re.fullmatch(r"9\.[0-9]+\.[0-9]+(?:\.[0-9]+)?", api_version):
            raise ValueError("VCF Automation provider requires a supported 9.x api_version, such as 9.1.1.")
    elif api_version is not None:
        raise ValueError("api_version is provider-only; organization services have independent API version schemes.")
    org_id = target.get("org_id")
    if org_id is not None and (
        family != "provider" or not isinstance(org_id, str) or not org_id
        or any(ord(character) < 32 or ord(character) == 127 for character in org_id)
    ):
        raise ValueError("org_id is an optional provider-only organization context identifier.")


def default_resources(target):
    """Return resources from one explicitly selected API family."""
    validate_target(target)
    return list(FAMILY_RESOURCES[target["api_family"]])


family_defaults = default_resources


def authenticate(client):
    """Use a caller-provided access token; do not exchange API refresh tokens."""
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    token = os.environ.get(client.target["token_env"], "")
    if not token or any(character.isspace() for character in token) or any(ord(character) < 32 for character in token):
        raise ApiError("The VCF Automation bearer access token is missing or invalid; supply the raw access token.")
    client.headers["Authorization"] = "Bearer " + token
    if client.target["api_family"] == "provider":
        client.headers["Accept"] = "application/json;version=" + client.target["api_version"]
        if client.target.get("org_id"):
            client.headers["X-VMWARE-VCLOUD-TENANT-CONTEXT"] = client.target["org_id"]
    else:
        client.headers["Accept"] = "application/json"
    client._product_state["automation_authenticated"] = True


def close(client):
    """Discard local references without revoking a caller-owned token."""
    client.headers.pop("Authorization", None)
    client.headers.pop("X-VMWARE-VCLOUD-TENANT-CONTEXT", None)
    client._product_state.pop("automation_authenticated", None)


def _integer(payload, key):
    value = payload.get(key)
    if value is not None and (type(value) is not int or value < 0):
        raise ApiError("VCF Automation returned invalid pagination metadata.")
    return value


def _rows(payload, key):
    if not isinstance(payload, dict):
        raise ApiError("VCF Automation inventory must be a JSON object containing a records array.")
    rows = payload.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ApiError("VCF Automation returned an unexpected inventory records array.")
    return rows


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Collect one documented API family; fail if pagination cannot complete."""
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    family = client.target["api_family"]
    if resource not in FAMILY_RESOURCES[family]:
        raise ApiError("Resource is not supported by the selected VCF Automation API family.")
    if type(page_size) is not int or page_size < 1 or type(max_pages) is not int or max_pages < 1:
        raise ApiError("VCF Automation pagination limits must be positive integers.")
    path = RESOURCE_PATHS["vcf_automation"][resource]
    provider = family == "provider"
    iaas = resource in IAAS_RESOURCES
    effective_size = min(page_size, 128) if provider else page_size
    combined = []
    fingerprints = set()
    identities = set()
    expected_total = None
    expected_pages = None
    for index in range(max_pages):
        if provider:
            page = index + 1
            params = {"page": page, "pageSize": effective_size}
        elif iaas:
            page = None
            params = {"$top": effective_size, "$skip": len(combined)}
            if resource in {"cloud_accounts", "fabric_networks"}:
                params["$count"] = "true"
        else:
            page = index
            params = {"page": page, "size": effective_size}
            if resource == "projects":
                # Include projects visible only through the documented Supervisor role.
                params["excludeSupervisor"] = "false"
                params["excludeViewer"] = "false"
        payload = client.get(path, params=params)
        rows = _rows(payload, "values" if provider else "content")
        count = _integer(payload, "numberOfElements")
        if count is not None and count != len(rows):
            raise ApiError("VCF Automation page record count does not match its metadata.")
        returned_page = _integer(payload, "page" if provider else "number")
        if page is not None and returned_page is not None and returned_page != page:
            raise ApiError("VCF Automation returned an unexpected page number.")
        total = _integer(payload, "resultTotal" if provider else "totalElements")
        pages = _integer(payload, "pageCount" if provider else "totalPages")
        if total is not None:
            if expected_total is not None and total != expected_total:
                raise ApiError("VCF Automation inventory changed during pagination; rerun collection.")
            expected_total = total
        if pages is not None:
            if expected_pages is not None and pages != expected_pages:
                raise ApiError("VCF Automation page count changed during pagination; rerun collection.")
            expected_pages = pages
        if rows:
            digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
            if digest in fingerprints:
                raise ApiError("VCF Automation repeated a page; pagination did not advance.")
            fingerprints.add(digest)
            for row in rows:
                identity = row.get("id")
                if isinstance(identity, (str, int)) and not isinstance(identity, bool):
                    if identity in identities:
                        raise ApiError("VCF Automation repeated a resource identifier; rerun collection.")
                    identities.add(identity)
        combined.extend(rows)
        if expected_total is not None and len(combined) > expected_total:
            raise ApiError("VCF Automation returned more records than its total count.")
        last = payload.get("last") if not (provider or iaas) else None
        if last is not None and type(last) is not bool:
            raise ApiError("VCF Automation returned an invalid last-page marker.")
        exhausted = (
            (expected_total is not None and len(combined) == expected_total)
            or (expected_pages is not None and index + 1 >= expected_pages)
            or last is True
            or not rows
        )
        if exhausted:
            if expected_total is not None and len(combined) != expected_total:
                raise ApiError("VCF Automation pagination ended before its total count was reached.")
            if expected_pages is not None and expected_pages > index + 1:
                raise ApiError("VCF Automation pagination ended before its declared page count.")
            if expected_pages is not None and rows and index + 1 > expected_pages:
                raise ApiError("VCF Automation returned records beyond its declared page count.")
            if last is False:
                raise ApiError("VCF Automation returned conflicting end-of-pagination metadata.")
            return combined
    raise ApiError("VCF Automation exceeded max_pages; no incomplete resource will be exported.")
