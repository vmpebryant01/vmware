"""Selected operational metadata through the shared transport. Author: Paul Bryant."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from .http_client import ApiError
from .products import protection_recovery


RECOVERY_SUFFIXES = {
    "folder_mappings": "folders", "network_mappings": "networks",
    "resource_mappings": "resources", "storage_policy_mappings": "storage-policies",
    "test_network_mappings": "test-networks",
}
RESOURCE_PATHS = {
    "sddc_manager": {
        "certificates": "/v1/domains/{domain_id}/resource-certificates",
        "failed_tasks": "/v1/tasks",
    },
    "nsx": {"security_rules": "/policy/api/v1/infra/domains/{domain_id}/security-policies/{policy_id}/rules"},
    "vcf_automation": {"catalog_items": "/catalog/api/items"},
    "vcf_operations": {"collectors": "/suite-api/api/collectors"},
    "live_site_recovery": {
        resource: "/api/rest/srm/v2/pairings/{pairing_id}/srms/{srm_id}/inventory-mappings/" + suffix
        for resource, suffix in RECOVERY_SUFFIXES.items()
    },
}
# Optional resources do not change the existing default inventory scope.
DEFAULT_RESOURCES = {}
ALLOWED_OPERATIONS = set()
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")
CERTIFICATE_FIELDS = (
    "resourceType", "resourceName", "issuedTo", "notAfter", "numberOfDaysToExpire",
    "expirationStatus", "isInstalled", "autoRenew", "autoRenewStatus",
)
TASK_FIELDS = ("id", "name", "type", "status", "creationTimestamp", "completionTimestamp", "resolutionStatus")
RULE_FIELDS = ("id", "display_name", "action", "direction", "disabled", "logged", "sequence_number")
CATALOG_FIELDS = ("id", "name", "isRequestable", "global", "createdAt", "lastUpdatedAt")
MAPPING_FIELDS = ("id", "primary_object_name", "secondary_object_name", "reverse_mapping_type")
TEST_MAPPING_FIELDS = ("id", "target_network", "test_network", "test_network_name")
COLLECTOR_FIELDS = ("id", "name", "state", "local", "dataPersistenceEnabled")


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def _safe_id(value):
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _id_list(target, key, required=False):
    value = target.get(key)
    if value is None and not required:
        return
    if (not isinstance(value, list) or not value or len(value) > 1000
            or any(not _safe_id(item) for item in value) or len(set(value)) != len(value)):
        raise ValueError(f"{key} must contain 1-1000 unique simple identifiers.")


def validate_target(target):
    """Validate operational scope and thresholds without reading credentials."""
    component = target.get("component")
    selected = target.get("resources", [])
    if not isinstance(selected, list):
        raise ValueError("resources must be an array.")
    for key, expected_component in (
        ("task_days", "sddc_manager"), ("certificate_attention_days", "sddc_manager"),
        ("domain_ids", "sddc_manager"), ("policy_ids", "nsx"), ("srm_ids", "live_site_recovery"),
    ):
        if key in target and component != expected_component:
            raise ValueError(f"{key} is not an option for this component.")
    for key in ("task_days", "certificate_attention_days"):
        if key in target and (type(target[key]) is not int or not 1 <= target[key] <= 3650):
            raise ValueError(f"{key} must be an integer from 1 to 3650.")
    _id_list(target, "domain_ids")
    _id_list(target, "policy_ids", component == "nsx" and "security_rules" in selected)
    _id_list(target, "srm_ids", component == "live_site_recovery" and any(resource in RECOVERY_SUFFIXES for resource in selected))
    if component == "nsx" and "security_rules" in selected and not _safe_id(target.get("domain_id", "default")):
        raise ValueError("security_rules requires a simple domain_id.")
    if component == "vcf_automation" and "catalog_items" in selected and target.get("api_family") not in ("all_apps", "vm_apps"):
        raise ValueError("catalog_items requires the all_apps or vm_apps API family.")
    if component == "live_site_recovery" and any(resource in RECOVERY_SUFFIXES for resource in selected):
        if not _safe_id(target.get("pairing_id")):
            raise ValueError("Recovery mappings require an explicit pairing_id.")


def _scalar(value):
    return value if value is None or type(value) in (str, int, float, bool) else None


def _select(item, fields):
    result = {}
    for field in fields:
        value = item
        for part in field.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        result[field.replace(".", "_")] = _scalar(value)
    return result


def _integer(value):
    if value is not None and (type(value) is not int or value < 0):
        raise ApiError("Operational API returned invalid pagination metadata.")
    return value


def _rows(payload, key):
    if not isinstance(payload, dict):
        raise ApiError("Operational API returned an unexpected collection envelope.")
    rows = payload.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ApiError("Operational API returned an unexpected inventory array.")
    return rows


def _pages(client, path, style, page_size, max_pages, filters=None):
    """Collect fixed-origin page or cursor APIs without following response URLs."""
    combined, seen, identifiers = [], set(), set()
    cursor = None
    expected_total = expected_pages = None
    for page in range(max_pages):
        query = dict(filters or {})
        if style == "cursor":
            query["page_size"] = page_size
            if cursor is not None:
                query["cursor"] = cursor
        elif style == "sddc":
            query.update(pageNumber=page, pageSize=page_size)
        else:
            query.update(page=page, size=page_size)
        payload = client.get(path, params=query)
        rows = _rows(payload, {"cursor": "results", "sddc": "elements", "spring": "content"}[style])
        metadata = payload.get("pageMetadata") if style == "sddc" else payload
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ApiError("Operational API returned invalid pagination metadata.")
        number = metadata.get("pageNumber" if style == "sddc" else "number") if style != "cursor" else None
        if number is not None and _integer(number) != page:
            raise ApiError("Operational API returned an unexpected page number.")
        total = _integer(metadata.get("result_count" if style == "cursor" else "totalElements"))
        pages = _integer(metadata.get("totalPages")) if style != "cursor" else None
        for current, expected, label in ((total, expected_total, "total"), (pages, expected_pages, "page count")):
            if current is not None and expected is not None and current != expected:
                raise ApiError(f"Operational inventory {label} changed during pagination; rerun collection.")
        if total is not None:
            expected_total = total
        if pages is not None:
            expected_pages = pages
        if rows:
            digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
            if digest in seen:
                raise ApiError("Operational API repeated an inventory page.")
            seen.add(digest)
            for row in rows:
                identity = row.get("id")
                if isinstance(identity, str) and identity:
                    if identity in identifiers:
                        raise ApiError("Operational API repeated a resource identifier.")
                    identifiers.add(identity)
        combined.extend(rows)
        if expected_total is not None and len(combined) > expected_total:
            raise ApiError("Operational API returned more records than its total count.")
        if style == "cursor":
            next_cursor = payload.get("cursor")
            if not next_cursor:
                if expected_total is not None and len(combined) != expected_total:
                    raise ApiError("Operational cursor collection ended before its advertised total.")
                return combined
            if not isinstance(next_cursor, str) or next_cursor in seen:
                raise ApiError("Operational API returned an invalid or repeated cursor.")
            seen.add(next_cursor)
            cursor = next_cursor
            continue
        last = payload.get("last") if style == "spring" else None
        if last is not None and type(last) is not bool:
            raise ApiError("Operational API returned an invalid last-page marker.")
        done = (not rows or last is True
                or (expected_total is not None and len(combined) == expected_total)
                or (expected_pages is not None and page + 1 >= expected_pages))
        if done:
            if expected_total is not None and len(combined) != expected_total:
                raise ApiError("Operational API pagination ended before its advertised total.")
            if expected_pages is not None and expected_pages > page + 1:
                raise ApiError("Operational API pagination ended before its declared page count.")
            if rows and expected_pages is not None and page + 1 > expected_pages:
                raise ApiError("Operational API returned records beyond its declared page count.")
            if last is False:
                raise ApiError("Operational API returned conflicting end-of-pagination metadata.")
            return combined
    raise ApiError("Operational collection exceeded max_pages; incomplete inventory was not exported.")


def _utc_now():
    return datetime.now(timezone.utc)


def _collection_details(client, resource, **scope):
    metadata = getattr(client, "collection_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        client.collection_metadata = metadata
    details = dict(scope, coverage="incomplete")
    metadata[resource] = details
    return details


def _certificates(client, page_size, max_pages):
    target = client.target
    threshold = target.get("certificate_attention_days", 60)
    details = _collection_details(
        client, "certificates", strategy="explicit_domains" if target.get("domain_ids") else "discovered_domains",
        queried_domain_ids=[], certificate_attention_days=threshold)
    if target.get("domain_ids"):
        domains = [{"id": domain_id, "name": domain_id} for domain_id in target["domain_ids"]]
    else:
        domains = _pages(client, "/v1/domains", "sddc", page_size, max_pages)
    result = []
    for domain in domains:
        domain_id = domain.get("id")
        if not _safe_id(domain_id):
            raise ApiError("A certificate inventory domain has an unusable identifier.")
        details["queried_domain_ids"].append(domain_id)
        path = RESOURCE_PATHS["sddc_manager"]["certificates"].format(domain_id=quote(domain_id, safe=""))
        for certificate in _pages(client, path, "sddc", page_size, max_pages):
            row = _select(certificate, CERTIFICATE_FIELDS)
            days = certificate.get("numberOfDaysToExpire")
            row["numberOfDaysToExpire"] = days if type(days) is int else None
            row["domain_id"] = domain_id
            row["domain"] = _scalar(domain.get("name")) or domain_id
            row["attentionThresholdDays"] = threshold
            status = str(certificate.get("expirationStatus") or "").upper()
            row["attention"] = certificate.get("isInstalled") is True and (
                status in ("EXPIRED", "ABOUT_TO_EXPIRE") or (type(days) is int and days <= threshold))
            result.append(row)
    details["coverage"] = "complete"
    details["record_count"] = len(result)
    return result


def _failed_tasks(client, page_size, max_pages):
    days = client.target.get("task_days", 30)
    cutoff = int((_utc_now() - timedelta(days=days)).timestamp() * 1000)
    details = _collection_details(client, "failed_tasks", strategy="completed_task_window",
                                  task_days=days, completed_after_epoch_ms=cutoff,
                                  query_filters={"completedAfter": cutoff})
    tasks = _pages(client, "/v1/tasks", "sddc", min(page_size, 100), max_pages, {"completedAfter": cutoff})
    result = [dict(_select(task, TASK_FIELDS), tasksCompletedAfterEpochMs=cutoff, taskWindowDays=days)
              for task in tasks if str(task.get("status") or "").upper() == "FAILED"]
    details.update(coverage="complete", queried_task_count=len(tasks), record_count=len(result))
    return result


def _security_rules(client, page_size, max_pages):
    target = client.target
    domain = target.get("domain_id", "default")
    result = []
    for policy in target["policy_ids"]:
        path = RESOURCE_PATHS["nsx"]["security_rules"].format(
            domain_id=quote(domain, safe=""), policy_id=quote(policy, safe=""))
        result.extend(dict(_select(row, RULE_FIELDS), domain_id=domain, policy_id=policy)
                      for row in _pages(client, path, "cursor", page_size, max_pages))
    return result


def _catalog_items(client, page_size, max_pages):
    rows = _pages(client, "/catalog/api/items", "spring", page_size, max_pages)
    result = []
    for item in rows:
        row = _select(item, CATALOG_FIELDS)
        projects = item.get("projectIds")
        row["visibleProjectCount"] = len(projects) if isinstance(projects, list) else None
        result.append(row)
    return result


def _recovery_mappings(client, resource, page_size, max_pages):
    pairing = client.target["pairing_id"]
    protection_recovery._pairings(client, page_size, max_pages)
    protection_recovery._ensure_remote(client, pairing)
    result = []
    for srm in client.target["srm_ids"]:
        path = RESOURCE_PATHS["live_site_recovery"][resource].format(
            pairing_id=quote(pairing, safe=""), srm_id=quote(srm, safe=""))
        rows = protection_recovery._paginate(client, path, page_size, max_pages)
        for item in rows:
            if (("pairing_id" in item and item["pairing_id"] != pairing)
                    or ("srm_id" in item and item["srm_id"] != srm)):
                raise ApiError("Recovery mapping refers to a different configured scope.")
            fields = TEST_MAPPING_FIELDS if resource == "test_network_mappings" else MAPPING_FIELDS
            result.append(dict(_select(item, fields), pairing_id=pairing, srm_id=srm))
    return result


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Collect optional allowlisted operational metadata through the active client."""
    if not supports(client.target.get("component"), resource):
        raise ApiError("Unknown operational resource for this component.")
    try:
        selected = dict(client.target, resources=[resource])
        validate_target(selected)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    if type(page_size) is not int or not 1 <= page_size <= 1000 or type(max_pages) is not int or max_pages < 1:
        raise ApiError("Operational pagination requires page_size from 1 to 1000 and a positive max_pages.")
    component = client.target["component"]
    if component == "sddc_manager":
        return _certificates(client, page_size, max_pages) if resource == "certificates" else _failed_tasks(client, page_size, max_pages)
    if component == "nsx":
        return _security_rules(client, page_size, max_pages)
    if component == "vcf_automation":
        return _catalog_items(client, page_size, max_pages)
    if component == "live_site_recovery":
        return _recovery_mappings(client, resource, page_size, max_pages)
    rows = _rows(client.get(RESOURCE_PATHS["vcf_operations"]["collectors"]), "collector")
    return [_select(row, COLLECTOR_FIELDS) for row in rows]
