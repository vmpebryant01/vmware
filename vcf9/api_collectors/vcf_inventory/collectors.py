"""Documented inventory endpoints and pagination. Author: Paul Bryant."""

import hashlib
import json

from .http_client import ApiError
from .products import module_for, modules
from . import operational, assurance, activity, protection_evidence
from . import lifecycle, management_services, supervisor, metric_history
from .vcenter_inventory import VCENTER_LIMITS, collect_vcenter

RESOURCE_PATHS = {
    "sddc_manager": {
        "appliance_info": "/v1/system/appliance-info",
        "domains": "/v1/domains", "clusters": "/v1/clusters", "hosts": "/v1/hosts",
        "vcenters": "/v1/vcenters", "nsx_clusters": "/v1/nsxt-clusters",
        "network_pools": "/v1/network-pools",
    },
    "vcenter": {
        "datacenters": "/api/vcenter/datacenter", "clusters": "/api/vcenter/cluster",
        "hosts": "/api/vcenter/host", "datastores": "/api/vcenter/datastore",
        "networks": "/api/vcenter/network", "vms": "/api/vcenter/vm",
    },
    "nsx": {
        "segments": "/policy/api/v1/infra/segments",
        "tier0_gateways": "/policy/api/v1/infra/tier-0s",
        "tier1_gateways": "/policy/api/v1/infra/tier-1s",
        "host_transport_nodes": "/policy/api/v1/infra/sites/{site}/enforcement-points/{ep}/host-transport-nodes",
        "edge_transport_nodes": "/policy/api/v1/infra/sites/{site}/enforcement-points/{ep}/edge-transport-nodes",
        "transport_zones": "/policy/api/v1/infra/sites/{site}/enforcement-points/{ep}/transport-zones",
        "groups": "/policy/api/v1/infra/domains/{domain}/groups",
        "security_policies": "/policy/api/v1/infra/domains/{domain}/security-policies",
        "ip_pools": "/policy/api/v1/infra/ip-pools",
        "sites": "/policy/api/v1/infra/sites",
        "legacy_transport_nodes": "/api/v1/transport-nodes",
        "legacy_transport_zones": "/api/v1/transport-zones",
    },
}
DEFAULT_RESOURCES = {component: list(paths) for component, paths in RESOURCE_PATHS.items()}
DEFAULT_RESOURCES["nsx"] = [resource for resource in RESOURCE_PATHS["nsx"]
                            if resource not in ("sites", "legacy_transport_nodes", "legacy_transport_zones")]
for product in modules():
    RESOURCE_PATHS.update(product.RESOURCE_PATHS)
    DEFAULT_RESOURCES.update(product.DEFAULT_RESOURCES)
SUPPLEMENTAL_MODULES = (operational, assurance, activity, protection_evidence,
                        lifecycle, management_services, supervisor, metric_history)
for supplemental in SUPPLEMENTAL_MODULES:
    for component, paths in supplemental.RESOURCE_PATHS.items():
        RESOURCE_PATHS[component].update(paths)


def _records(value, key=None):
    if key is not None and not isinstance(value, dict):
        raise ApiError("Unexpected paginated inventory response; expected an object.")
    records = value.get(key) if key else value
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ApiError("Unexpected inventory response structure; expected an array of objects.")
    return records


def _nonnegative_integer(value, label):
    if type(value) is not int or value < 0:
        raise ApiError(f"Invalid {label} in pagination metadata.")
    return value


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Return all records in the configured scope, or raise without claiming completeness."""
    component = client.target["component"]
    for supplemental in SUPPLEMENTAL_MODULES:
        if supplemental.supports(component, resource):
            return supplemental.collect_resource(client, resource, page_size=page_size, max_pages=max_pages)
    product = module_for(component)
    if product is not None:
        return product.collect_resource(client, resource, page_size=page_size, max_pages=max_pages)
    try:
        path = RESOURCE_PATHS[component][resource]
    except KeyError as exc:
        raise ApiError("Unknown inventory resource.") from exc
    path = path.format(site=client.target.get("site_id", "default"),
                       ep=client.target.get("enforcement_point_id", "default"),
                       domain=client.target.get("domain_id", "default"))
    if component == "sddc_manager" and resource == "appliance_info":
        appliance = client.get(path)
        if not isinstance(appliance, dict) or not isinstance(appliance.get("version"), str):
            raise ApiError("SDDC Manager returned invalid appliance information.")
        return [appliance]
    if component == "vcenter":
        return collect_vcenter(client, resource, max_pages=max_pages)
    combined = []
    seen = set()
    cursor = None
    expected_total = None
    for page in range(max_pages):
        if component == "nsx":
            params = {"page_size": page_size}
            if cursor is not None:
                params["cursor"] = cursor
            payload = client.get(path, params=params)
            rows = _records(payload, "results")
            combined.extend(rows)
            if page == 0 and payload.get("result_count") is not None:
                expected_total = _nonnegative_integer(payload["result_count"], "result_count")
            next_cursor = payload.get("cursor")
            if not next_cursor:
                if expected_total is not None and len(combined) != expected_total:
                    raise ApiError("NSX result count changed or pagination ended early; rerun the collection.")
                return combined
            if not isinstance(next_cursor, str) or next_cursor in seen:
                raise ApiError("NSX returned an invalid or repeated pagination cursor.")
            seen.add(next_cursor)
            cursor = next_cursor
        else:
            params = {} if resource == "network_pools" else {"pageNumber": page, "pageSize": page_size}
            payload = client.get(path, params=params)
            rows = _records(payload, "elements")
            # Detect servers that ignore pageNumber instead of silently repeating records.
            fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
            if rows and fingerprint in seen:
                raise ApiError("SDDC Manager repeated a page; pagination may be unsupported by this version.")
            seen.add(fingerprint)
            combined.extend(rows)
            metadata = payload.get("pageMetadata")
            if metadata is None:
                if resource == "network_pools" or not rows:
                    if expected_total is not None and len(combined) != expected_total:
                        raise ApiError("SDDC Manager pagination ended before totalElements was reached.")
                    return combined
                # Without metadata, a short page alone cannot establish completion.
                continue
            if not isinstance(metadata, dict):
                raise ApiError("Invalid SDDC Manager pagination metadata.")
            if "pageNumber" in metadata and _nonnegative_integer(metadata["pageNumber"], "pageNumber") != page:
                raise ApiError("SDDC Manager returned an unexpected page number.")
            total = metadata.get("totalElements")
            pages = metadata.get("totalPages")
            if total is not None:
                total = _nonnegative_integer(total, "totalElements")
                if expected_total is not None and total != expected_total:
                    raise ApiError("Inventory changed during pagination; rerun the collection.")
                expected_total = total
                if len(combined) > total:
                    raise ApiError("SDDC Manager returned more records than totalElements.")
            if pages is not None:
                pages = _nonnegative_integer(pages, "totalPages")
            if expected_total is not None and len(combined) > expected_total:
                raise ApiError("SDDC Manager returned more records than totalElements.")
            done = (expected_total is not None and len(combined) == expected_total) or (pages is not None and page + 1 >= pages)
            if done:
                if expected_total is not None and len(combined) != expected_total:
                    raise ApiError("SDDC Manager pagination ended before totalElements was reached.")
                return combined
            if resource == "network_pools":
                raise ApiError("Network pool response appears incomplete; this endpoint has no documented pagination parameters.")
            if not rows and expected_total is None and pages is None:
                return combined
            if not rows:
                raise ApiError("SDDC Manager returned an empty page before completing its inventory.")
    raise ApiError("Pagination exceeded max_pages; collection stopped without exporting an incomplete resource.")


def resources_for(target):
    """Select defaults for the configured product and API family."""
    if "resources" in target:
        return target["resources"]
    product = module_for(target["component"])
    if product is not None and hasattr(product, "default_resources"):
        return product.default_resources(target)
    return DEFAULT_RESOURCES[target["component"]]
