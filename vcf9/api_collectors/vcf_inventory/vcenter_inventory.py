"""Coverage-preserving vCenter inventory partitioning. Author: Paul Bryant."""

from copy import deepcopy

from .http_client import ApiError


PATHS = {"datacenters": "/api/vcenter/datacenter", "clusters": "/api/vcenter/cluster",
         "hosts": "/api/vcenter/host", "datastores": "/api/vcenter/datastore",
         "networks": "/api/vcenter/network", "vms": "/api/vcenter/vm"}
VCENTER_LIMITS = {"datacenters": 1000, "clusters": 1000, "hosts": 2500,
                  "datastores": 2500, "networks": 1000, "vms": 4000}
ID_KEYS = {"datacenters": "datacenter", "clusters": "cluster", "hosts": "host",
           "datastores": "datastore", "networks": "network", "vms": "vm"}
# Each documented array is a union within that field. Other fields remain AND constraints.
SPLIT_FIELDS = {
    "datacenters": ("datacenters", "names", "folders"),
    "clusters": ("clusters", "names", "datacenters", "folders"),
    "hosts": ("hosts", "names", "datacenters", "clusters", "folders", "connection_states", "host_uuids"),
    "datastores": ("datastores", "names", "datacenters", "folders", "types"),
    "networks": ("networks", "names", "datacenters", "folders", "types"),
    "vms": ("vms", "names", "datacenters", "clusters", "hosts", "folders", "resource_pools", "power_states"),
}
VM_POWER_STATES = ("POWERED_OFF", "POWERED_ON", "SUSPENDED")
LIMIT_ERROR_TYPES = {"UNABLE_TO_ALLOCATE_RESOURCE", "com.vmware.vapi.std.errors.unable_to_allocate_resource"}


def _values(value):
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    unique = []
    for item in values:
        if item not in unique:
            unique.append(item)
    return unique


class _Collection:
    def __init__(self, client, resource, max_requests):
        self.client = client
        self.resource = resource
        self.max_requests = max_requests
        self.leaves = []
        self.datacenters = None
        self.metadata = {
            "strategy": "direct", "coverage": "incomplete", "request_count": 0,
            "partition_count": 0, "deduplicated_count": 0, "partitions": [],
            "coverage_notes": ["Coverage is limited to the original filters and objects visible to the account."],
            "missing_coverage": [],
        }
        current = getattr(client, "collection_metadata", None)
        if not isinstance(current, dict):
            current = {}
            client.collection_metadata = current
        current[resource] = self.metadata

    def fail(self, reason, filters=None, status=None):
        self.metadata["missing_coverage"].append({"filters": deepcopy(filters or {}), "reason": reason})
        raise ApiError(f"Cannot establish complete vCenter {self.resource} coverage: {reason}", status=status)

    def query(self, resource, filters, purpose="inventory"):
        if self.metadata["request_count"] >= self.max_requests:
            self.fail("The request budget was exhausted before discovery and verification completed.", filters)
        event = {"resource": resource, "filters": deepcopy(filters), "purpose": purpose, "status": "requesting"}
        self.metadata["partitions"].append(event)
        self.metadata["request_count"] += 1
        try:
            rows = self.client.get(PATHS[resource], params=deepcopy(filters))
        except ApiError as error:
            event["status"] = "error"
            if error.status is not None:
                event["http_status"] = error.status
            if error.status != 500:
                raise
            error_type = getattr(error, "error_type", None)
            if error_type is not None and error_type not in LIMIT_ERROR_TYPES:
                raise
            event["status"] = "limit_error" if error_type in LIMIT_ERROR_TYPES else "unclassified_http_500"
            if error_type in LIMIT_ERROR_TYPES:
                event["error_classification"] = "unable_to_allocate_resource"
            else:
                event["error_classification"] = "unknown"
                note = "HTTP 500 triggered narrower coverage checks; the transport did not establish that it was a result-limit error."
                if note not in self.metadata["coverage_notes"]:
                    self.metadata["coverage_notes"].append(note)
            return None, True
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            event["status"] = "invalid_response"
            self.fail("The API returned an unexpected inventory array.", filters)
        key = ID_KEYS[resource]
        seen = set()
        explicit_ids = _values(filters.get(resource))
        names = _values(filters.get("names"))
        powers = _values(filters.get("power_states")) if resource == "vms" else []
        for row in rows:
            identifier = row.get(key)
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                event["status"] = "invalid_identifiers"
                self.fail("An inventory response has missing or repeated stable identifiers.", filters)
            seen.add(identifier)
            if explicit_ids and identifier not in explicit_ids:
                event["status"] = "filter_mismatch"
                self.fail("An inventory result does not match its identifier filter.", filters)
            if names and row.get("name") not in names:
                event["status"] = "filter_mismatch"
                self.fail("An inventory result does not match its exact-name filter.", filters)
            if powers and row.get("power_state") not in powers:
                event["status"] = "filter_mismatch"
                self.fail("A VM result does not match its power-state filter.", filters)
        event["record_count"] = len(rows)
        limited = len(rows) >= VCENTER_LIMITS[resource]
        event["status"] = "result_boundary" if limited else "complete"
        return rows, limited

    def merge(self, resource, parts, filters, sample=None, disjoint=False):
        key = ID_KEYS[resource]
        combined = {}
        for part in parts:
            for row in part:
                identifier = row[key]
                if identifier in combined and (disjoint or combined[identifier] != row):
                    self.fail("Partitions overlapped unexpectedly or returned conflicting versions of an object; rerun against a stable inventory.", filters)
                combined[identifier] = row
        if sample and not {row[key] for row in sample}.issubset(combined):
            self.fail("Some objects from the parent query are missing from its child scopes; container visibility or inventory changes left missing coverage.", filters)
        return list(combined.values())

    def discover_datacenters(self):
        if self.datacenters is None:
            rows, limited = self.query("datacenters", {}, purpose="discovery")
            if limited:
                self.fail("Datacenter discovery is capped or failed with HTTP 500; the full datacenter partition set is unknown.")
            if not rows:
                self.fail("No visible datacenters were discovered for a query that needs partitioning.")
            self.datacenters = rows
        return self.datacenters

    def resolve(self, resource, filters):
        rows, limited = self.query(resource, filters)
        if not limited:
            self.leaves.append((resource, deepcopy(filters), deepcopy(rows)))
            return rows
        self.metadata["strategy"] = "partitioned"
        for field in SPLIT_FIELDS[resource]:
            values = _values(filters.get(field))
            if len(values) > 1:
                parts = []
                midpoint = len(values) // 2
                for subset in (values[:midpoint], values[midpoint:]):
                    narrowed = deepcopy(filters)
                    narrowed[field] = subset
                    parts.append(self.resolve(resource, narrowed))
                return self.merge(resource, parts, filters, sample=rows)
        if resource != "datacenters" and not _values(filters.get("datacenters")):
            parts = []
            for datacenter in self.discover_datacenters():
                narrowed = deepcopy(filters)
                narrowed["datacenters"] = [datacenter["datacenter"]]
                parts.append(self.resolve(resource, narrowed))
            return self.merge(resource, parts, filters, sample=rows, disjoint=True)
        if resource == "vms" and not _values(filters.get("power_states")):
            if rows and any(row.get("power_state") not in VM_POWER_STATES for row in rows):
                self.fail("An unknown VM power state prevents establishing exhaustive power-state partitions.", filters)
            parts = []
            for power_state in VM_POWER_STATES:
                narrowed = deepcopy(filters)
                narrowed["power_states"] = [power_state]
                parts.append(self.resolve(resource, narrowed))
            return self.merge(resource, parts, filters, sample=rows, disjoint=True)
        self.fail("A child query still reaches the result boundary or returns HTTP 500, and no exhaustive supported filter split remains. Supply narrower explicit identifier, name, folder, datacenter, cluster, or host scopes.", filters)

    def verify(self):
        # Partitioning is sequential. Recheck each successful leaf and the discovered
        # container set to detect common inventory-movement and permission changes.
        for resource, filters, expected in self.leaves:
            rows, limited = self.query(resource, filters, purpose="verification")
            if limited:
                self.fail("A partition became capped or failed during verification.", filters)
            key = ID_KEYS[resource]
            if {row[key]: row for row in rows} != {row[key]: row for row in expected}:
                self.fail("A partition changed during verification; rerun against a stable inventory.", filters)
        if self.datacenters is not None:
            rows, limited = self.query("datacenters", {}, purpose="discovery_verification")
            if limited or {row["datacenter"] for row in rows} != {row["datacenter"] for row in self.datacenters}:
                self.fail("The discovered datacenter set changed or could not be verified.")


def collect_vcenter(client, resource, max_pages=1000):
    """Return a complete visible resource scope, or fail without returning partial rows.

    max_pages is a global API query budget for this collection, including
    datacenter discovery and verification. Transport retries can add HTTP
    attempts. Evidence is placed in
    client.collection_metadata[resource], including when collection fails.
    """
    if resource not in PATHS:
        raise ApiError("Unknown vCenter inventory resource.")
    if type(max_pages) is not int or max_pages < 1:
        raise ApiError("The vCenter request budget must be a positive integer.")
    collection = _Collection(client, resource, max_pages)
    all_filters = client.target.get("filters", {})
    if not isinstance(all_filters, dict) or not isinstance(all_filters.get(resource, {}), dict):
        collection.fail("The configured resource filters must be an object.")
    filters = deepcopy(all_filters.get(resource, {}))
    collection.metadata["applied_filters"] = deepcopy(filters)
    try:
        rows = collection.resolve(resource, filters)
        if collection.metadata["strategy"] == "partitioned":
            collection.verify()
            collection.metadata["coverage_notes"].append("Every child scope and the discovered datacenter set were rechecked. Sequential requests are not an atomic inventory snapshot.")
        collection.metadata["coverage"] = "complete"
        collection.metadata["partition_count"] = len(collection.leaves)
        collection.metadata["record_count"] = len(rows)
        collection.metadata["deduplicated_count"] = sum(len(part) for _, _, part in collection.leaves) - len(rows)
        return rows
    except ApiError:
        collection.metadata["coverage"] = "incomplete"
        collection.metadata["partition_count"] = len(collection.leaves)
        raise
