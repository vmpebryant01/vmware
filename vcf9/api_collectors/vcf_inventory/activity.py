"""Optional migration, firewall, and request observations. Author: Paul Bryant."""

import math
import re
from urllib.parse import quote

from .http_client import ApiError


RESOURCE_PATHS = {
    "hcx": {"migrations": "/hybridity/api/migrations"},
    "nsx": {"rule_statistics": "/policy/api/v1/infra/domains/{domain_id}/security-policies/{policy_id}/rules/{rule_id}/statistics"},
    "vcf_automation": {"deployment_requests": "/deployment/api/deployments/{deployment_id}/requests"},
}
DEFAULT_RESOURCES = {}
# The shared transport must call allow_query for the one permitted POST query.
ALLOWED_OPERATIONS = set()
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")
HCX_FIELDS = (
    "id", "migrationId", "migrationGroupId", "entityId", "migrationType", "state",
    "creationDate", "lastUpdated", "isDeleted", "isArchived", "entity.entityName",
    "source.endpointId", "destination.endpointId", "progress.startTime", "progress.endTime",
    "progress.isDone", "progress.didFail", "progress.isCancelled", "progress.transfer.progress",
    "progress.transfer.completed", "progress.switchover.progress", "progress.switchover.completed",
    "progress.state.status", "progress.state.isDone", "progress.state.isTransferProgress",
    "progress.state.isSwitchoverProgress", "progress.state.isWaitingForMaintWindow",
    "progress.state.isParked", "progress.state.isCanceled", "progress.state.isAborted",
)
COUNTERS = ("byte_count", "hit_count", "packet_count", "session_count", "l7_accept_count",
            "l7_reject_count", "l7_reject_with_response_count")
STAT_CONTEXT = ("internal_rule_id", "lr_path", "segment_path", "rule")
REQUEST_FIELDS = ("id", "deploymentId", "actionId", "status", "createdAt", "initializedAt",
                  "approvedAt", "updatedAt", "completedAt", "estimatedCompletionTime",
                  "completedTasks", "totalTasks", "cancelable", "dismissed")


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def _safe_id(value):
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _ids(value, label):
    if (not isinstance(value, list) or not value or len(value) > 1000
            or any(not _safe_id(item) for item in value) or len(set(value)) != len(value)):
        raise ValueError(f"{label} must contain 1-1000 unique simple identifiers.")


def validate_target(target):
    """Validate explicit optional scopes without reading credentials or making requests."""
    component = target.get("component")
    resources = target.get("resources", [])
    if not isinstance(resources, list):
        raise ValueError("resources must be an array.")
    if "rule_ids" in target and component != "nsx":
        raise ValueError("rule_ids is only supported for NSX.")
    if "deployment_ids" in target:
        if component != "vcf_automation":
            raise ValueError("deployment_ids is only supported for Automation.")
        _ids(target["deployment_ids"], "deployment_ids")
    if component == "nsx" and "rule_statistics" in resources:
        _ids(target.get("policy_ids"), "policy_ids")
        for key in ("domain_id", "site_id", "enforcement_point_id"):
            if not _safe_id(target.get(key, "default")):
                raise ValueError(f"rule_statistics requires a simple {key}.")
    if "rule_ids" in target:
        _ids(target.get("policy_ids"), "policy_ids")
        rule_ids = target["rule_ids"]
        policies = target.get("policy_ids", [])
        if (not isinstance(rule_ids, dict) or not rule_ids
                or not isinstance(policies, list) or set(rule_ids) != set(policies)):
            raise ValueError("rule_ids must map every selected policy_id to its rule identifiers.")
        for value in rule_ids.values():
            _ids(value, "rule_ids values")
    if component == "vcf_automation" and "deployment_requests" in resources:
        if target.get("api_family") not in ("all_apps", "vm_apps"):
            raise ValueError("deployment_requests requires the all_apps or vm_apps API family.")
        _ids(target.get("deployment_ids"), "deployment_ids")


def _hcx_body(page_size, offset=0):
    return {"filter": {"includeArchived": True}, "paging": {"pageSize": page_size, "offset": offset}}


def allow_query(component, method, path, params, body):
    """Authorize only the fixed HCX database query, including its exact action and payload."""
    if (component != "hcx" or method != "POST" or path != RESOURCE_PATHS["hcx"]["migrations"]
            or params != {"action": "query"} or not isinstance(body, dict)
            or set(body) != {"filter", "paging"}
            or not isinstance(body["filter"], dict) or set(body["filter"]) != {"includeArchived"}
            or body["filter"]["includeArchived"] is not True or not isinstance(body["paging"], dict)
            or set(body["paging"]) != {"pageSize", "offset"}):
        return False
    paging = body["paging"]
    return (type(paging["pageSize"]) is int and 1 <= paging["pageSize"] <= 1000
            and type(paging["offset"]) is int and 0 <= paging["offset"] <= 1000000000)


def _select(item, fields):
    row = {}
    for field in fields:
        value = item
        for part in field.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value is None or type(value) in (str, int, bool) or (type(value) is float and math.isfinite(value)):
            row[field.replace(".", "_")] = value
        else:
            raise ApiError("Activity API returned an invalid selected metadata field.")
    return row


def _rows(payload, key):
    if (not isinstance(payload, dict) or payload.get("success") is False or payload.get("completed") is False or payload.get("errors")
            or payload.get("error_code") is not None):
        raise ApiError("Activity API did not return a successful collection envelope.")
    rows = payload.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ApiError("Activity API returned an unexpected collection array.")
    return rows


def _integer(value):
    if value is not None and (type(value) is not int or value < 0):
        raise ApiError("Activity API returned invalid pagination metadata.")
    return value


class _Budget:
    def __init__(self, client, maximum, details):
        self.client, self.maximum, self.details = client, maximum, details
        self.count = 0

    def request(self, method, path, params=None, body=None):
        if self.count >= self.maximum:
            raise ApiError("Activity collection exceeded max_pages; coverage is incomplete.")
        self.count += 1
        self.details["request_count"] = self.count
        if method == "GET":
            return self.client.get(path, params=params)
        return self.client.request(method, path, params=params, body=body)


def _unique(rows, seen, field="id"):
    for row in rows:
        identity = row.get(field)
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ApiError("Activity API returned a missing or repeated resource identifier.")
        seen.add(identity)


def _hcx(budget, page_size, details):
    result, seen, offset = [], set(), 0
    while True:
        payload = budget.request("POST", RESOURCE_PATHS["hcx"]["migrations"],
                                 {"action": "query"}, _hcx_body(page_size, offset))
        if (not isinstance(payload, dict) or payload.get("success") is False
                or payload.get("completed") is False or payload.get("errors")):
            raise ApiError("HCX migration query did not return a successful collection envelope.")
        rows = _rows(payload.get("data"), "items")
        _unique(rows, seen)
        result.extend(_select(row, HCX_FIELDS) for row in rows)
        if not rows:
            details["terminal_empty_page"] = True
            return result
        # The schema defines offset as a record offset; a short page is not proof of completion.
        offset += len(rows)


def _rules(budget, path, page_size):
    result, identities, cursors, cursor, expected_total = [], set(), set(), None, None
    while True:
        params = {"page_size": page_size}
        if cursor is not None:
            params["cursor"] = cursor
        payload = budget.request("GET", path, params)
        rows = _rows(payload, "results")
        _unique(rows, identities)
        result.extend(row["id"] for row in rows)
        count = _integer(payload.get("result_count"))
        if count is not None:
            if expected_total is not None and count != expected_total:
                raise ApiError("NSX rule count changed during discovery.")
            expected_total = count
        cursor = payload.get("cursor")
        if not cursor:
            if expected_total is not None and len(result) != expected_total:
                raise ApiError("NSX rule discovery ended before its advertised count.")
            return result
        if not isinstance(cursor, str) or cursor in cursors:
            raise ApiError("NSX rule discovery repeated an invalid cursor.")
        cursors.add(cursor)


def _nsx(budget, target, page_size, details):
    domain = target.get("domain_id", "default")
    ep = f"/infra/sites/{target.get('site_id', 'default')}/enforcement-points/{target.get('enforcement_point_id', 'default')}"
    details.update(domain_id=domain, enforcement_point_path=ep, policy_ids=list(target["policy_ids"]),
                   resolved_rule_ids={})
    result, identities = [], set()
    for policy in target["policy_ids"]:
        base = f"/policy/api/v1/infra/domains/{quote(domain, safe='')}/security-policies/{quote(policy, safe='')}/rules"
        rules = (target["rule_ids"][policy] if "rule_ids" in target
                 else _rules(budget, base, page_size))
        if any(not _safe_id(rule) for rule in rules):
            raise ApiError("NSX returned an unusable rule identifier.")
        details["resolved_rule_ids"][policy] = list(rules)
        for rule in rules:
            payload = budget.request("GET", f"{base}/{quote(rule, safe='')}/statistics",
                                     {"enforcement_point_path": ep})
            rows = _rows(payload, "results")
            total = _integer(payload.get("result_count"))
            if payload.get("cursor") or (total is not None and total != len(rows)):
                raise ApiError("NSX statistics advertised additional results without documented paging parameters.")
            for item in rows:
                actual_ep = item.get("enforcement_point", ep)
                if actual_ep != ep:
                    raise ApiError("NSX statistics returned a different enforcement point than requested.")
                stats = item.get("statistics")
                if not isinstance(stats, dict):
                    raise ApiError("NSX returned an unexpected rule statistics structure.")
                row = _select(stats, COUNTERS + STAT_CONTEXT)
                if any(row[key] is not None and not isinstance(row[key], str) for key in STAT_CONTEXT):
                    raise ApiError("NSX returned an invalid realized rule context.")
                row.update(domain_id=domain, policy_id=policy, rule_id=rule, enforcement_point=actual_ep,
                           container_cluster_path=item.get("container_cluster_path"))
                if row["container_cluster_path"] is not None and not isinstance(row["container_cluster_path"], str):
                    raise ApiError("NSX returned an invalid statistics context.")
                for key in COUNTERS:
                    if row[key] is not None and (type(row[key]) is not int or row[key] < 0):
                        raise ApiError("NSX returned an invalid statistics counter.")
                identity = tuple(row.get(key) for key in ("domain_id", "policy_id", "rule_id", "enforcement_point",
                                                         "container_cluster_path") + STAT_CONTEXT)
                if identity in identities:
                    raise ApiError("NSX returned ambiguous duplicate statistics contexts.")
                identities.add(identity)
                result.append(row)
    return result


def _request_pages(budget, path, deployment_id, page_size):
    result, seen, page, expected_total, expected_pages = [], set(), 0, None, None
    while True:
        payload = budget.request("GET", path, {"page": page, "size": page_size})
        rows = _rows(payload, "content")
        if payload.get("number") is not None and _integer(payload["number"]) != page:
            raise ApiError("Automation returned a different request page than requested.")
        for key, expected in (("totalElements", expected_total), ("totalPages", expected_pages)):
            value = _integer(payload.get(key))
            if value is not None and expected is not None and value != expected:
                raise ApiError("Automation request pagination changed during collection.")
        if payload.get("totalElements") is not None:
            expected_total = payload["totalElements"]
        if payload.get("totalPages") is not None:
            expected_pages = payload["totalPages"]
        _unique(rows, seen)
        for item in rows:
            if item.get("deploymentId") not in (None, deployment_id):
                raise ApiError("Automation returned a request from a different deployment.")
            row = _select(item, REQUEST_FIELDS)
            row["deploymentId"] = deployment_id
            result.append(row)
        last = payload.get("last")
        if last is not None and type(last) is not bool:
            raise ApiError("Automation returned an invalid last-page marker.")
        if expected_total is not None and len(result) > expected_total:
            raise ApiError("Automation returned more requests than its advertised count.")
        done = (not rows or last is True or (expected_total is not None and len(result) == expected_total)
                or (expected_pages is not None and page + 1 >= expected_pages))
        if done:
            if (last is False or (expected_total is not None and len(result) != expected_total)
                    or (expected_pages is not None and expected_pages > page + 1)
                    or (rows and expected_pages is not None and page + 1 > expected_pages)):
                raise ApiError("Automation request pagination ended with conflicting coverage metadata.")
            return result
        page += 1


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Collect optional scoped metadata with a global logical request budget."""
    component = client.target.get("component")
    if not supports(component, resource):
        raise ValueError("Unsupported activity resource.")
    if type(page_size) is not int or not 1 <= page_size <= 1000 or type(max_pages) is not int or max_pages < 1:
        raise ValueError("Activity page_size must be 1-1000 and max_pages must be positive.")
    target = dict(client.target, resources=[resource])
    validate_target(target)
    if not isinstance(getattr(client, "collection_metadata", None), dict):
        client.collection_metadata = {}
    details = {"coverage": "incomplete", "request_count": 0}
    client.collection_metadata[resource] = details
    budget = _Budget(client, max_pages, details)
    if component == "hcx":
        details.update(strategy="offset_query", include_archived=True)
        records = _hcx(budget, page_size, details)
    elif component == "nsx":
        details["strategy"] = "explicit_rules" if "rule_ids" in target else "rules_within_explicit_policies"
        records = _nsx(budget, target, page_size, details)
    else:
        details.update(strategy="requests_within_explicit_deployments", api_family=target["api_family"],
                       deployment_ids=list(target["deployment_ids"]), queried_deployment_ids=[])
        records = []
        for deployment_id in target["deployment_ids"]:
            path = RESOURCE_PATHS[component][resource].format(deployment_id=quote(deployment_id, safe=""))
            records.extend(_request_pages(budget, path, deployment_id, page_size))
            details["queried_deployment_ids"].append(deployment_id)
    details.update(coverage="complete", record_count=len(records))
    return records


def probe_request(target, resource):
    """Return a small read-only probe for an explicitly configured activity resource."""
    component = target.get("component")
    if not supports(component, resource):
        return None
    validate_target(dict(target, resources=[resource]))
    if component == "hcx":
        return ("POST", RESOURCE_PATHS[component][resource], {"action": "query"}, _hcx_body(1),
                "Migration query including archived records; probe does not establish full coverage.")
    if component == "vcf_automation":
        path = RESOURCE_PATHS[component][resource].format(deployment_id=quote(target["deployment_ids"][0], safe=""))
        return ("GET", path, {"page": 0, "size": 1}, None, "First explicitly configured deployment only.")
    domain, policy = target.get("domain_id", "default"), target["policy_ids"][0]
    path = f"/policy/api/v1/infra/domains/{quote(domain, safe='')}/security-policies/{quote(policy, safe='')}/rules"
    if "rule_ids" in target:
        rule_id = target["rule_ids"][policy][0]
        ep = f"/infra/sites/{target.get('site_id', 'default')}/enforcement-points/{target.get('enforcement_point_id', 'default')}"
        return ("GET", f"{path}/{quote(rule_id, safe='')}/statistics", {"enforcement_point_path": ep}, None,
                "Statistics for the first explicitly configured policy and rule only.")
    return ("GET", path, {"page_size": 1}, None, "Rule discovery in the first explicitly configured policy only.")
