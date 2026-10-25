"""Summarize saved desired images and cached compliance. Author: Paul Bryant."""

from datetime import datetime, timezone

from .exports import sanitize
from .lifecycle import valid_cluster_ids
from .report_support import parse_time, positive_number


_RESOURCES = ("lifecycle_desired_image", "lifecycle_compliance")
_BUCKETS = {"compliant_hosts": "COMPLIANT", "non_compliant_hosts": "NON_COMPLIANT",
            "incompatible_hosts": "INCOMPATIBLE", "unavailable_hosts": "UNAVAILABLE"}


def _version(value, key):
    section = value.get(key)
    result = section.get("version") if isinstance(section, dict) else None
    return result if isinstance(result, str) and result else None


def _scan(value, collected, max_age):
    scanned = parse_time(value)
    valid = scanned is not None and collected is not None and scanned <= collected
    age = (collected - scanned).total_seconds() / 3600 if valid else None
    return {"scan_completed_at": value, "scan_age_hours_at_collection": round(age, 6) if age is not None else None,
            "scan_freshness": "unknown" if age is None else "stale" if age > max_age else "within_threshold"}


def _status(native, freshness, reasons):
    if native not in ("COMPLIANT", "NON_COMPLIANT", "INCOMPATIBLE"):
        reasons.append("compliance_status_unknown_or_unavailable")
    if freshness == "unknown":
        reasons.append("scan_timestamp_unknown_invalid_or_future")
    if reasons:
        return "unknown"
    return "review" if native != "COMPLIANT" or freshness == "stale" else "observed"


def _document(run, key):
    if key in run.get("unavailable", {}):
        return None
    document = run["resources"].get(key)
    if (not isinstance(document, dict) or not isinstance(document.get("records"), list)
            or any(not isinstance(row, dict) for row in document["records"])):
        return None
    metadata = document.get("collection")
    if (not isinstance(metadata, dict) or metadata.get("coverage") != "complete"
            or not valid_cluster_ids(metadata.get("configured_cluster_ids"))
            or metadata.get("queried_cluster_ids") != metadata["configured_cluster_ids"]):
        return None
    return document


def _index(document):
    if document is None:
        return {}, set(), set()
    expected = set(document["collection"]["configured_cluster_ids"])
    rows, ambiguous = {}, set()
    for row in document["records"]:
        identity = row.get("cluster_id")
        if not isinstance(identity, str) or identity not in expected or row.get("id") != identity:
            ambiguous.update(expected)
            continue
        if identity in rows or identity in ambiguous:
            ambiguous.add(identity)
            rows.pop(identity, None)
        else:
            rows[identity] = row
    return rows, ambiguous, expected


def build_lifecycle_report(run, max_scan_age_hours=24, now=None):
    """Describe the cached scan, with freshness measured at saved collection time."""
    positive_number(max_scan_age_hours, "max_scan_age_hours")
    evaluated = datetime.now(timezone.utc) if now is None else parse_time(now)
    if evaluated is None:
        raise ValueError("now must contain a timezone-qualified date and time.")
    if not isinstance(run, dict) or not isinstance(run.get("resources"), dict) or not isinstance(run.get("summary"), dict):
        raise ValueError("A loaded completed inventory run is required.")
    records = []
    targets = {}
    for target in run["summary"].get("targets", []):
        if isinstance(target, dict) and target.get("component") == "vcenter" and isinstance(target.get("name"), str):
            requested = target.get("resources", [])
            if any(isinstance(row, dict) and row.get("resource") in _RESOURCES for row in requested):
                targets[target["name"]] = target
    for name, component, resource in (*run["resources"], *run.get("unavailable", {})):
        if component == "vcenter" and resource in _RESOURCES:
            targets.setdefault(name, {"name": name, "component": component})
    for name, target in sorted(targets.items()):
        documents = {resource: _document(run, (name, "vcenter", resource)) for resource in _RESOURCES}
        indexes = {resource: _index(document) for resource, document in documents.items()}
        desired_rows, desired_ambiguous, desired_scope = indexes["lifecycle_desired_image"]
        compliance_rows, compliance_ambiguous, compliance_scope = indexes["lifecycle_compliance"]
        configured = desired_scope | compliance_scope
        if not configured:
            records.append({"target": name, "component": "vcenter", "record_type": "cluster", "status": "unknown",
                            "unknown_reasons": ["successful_explicit_cluster_scope_unavailable"]})
        for identity in sorted(configured):
            reasons = []
            if desired_scope != compliance_scope:
                reasons.append("desired_image_and_compliance_scopes_differ")
            desired = desired_rows.get(identity) if identity not in desired_ambiguous else None
            compliance = compliance_rows.get(identity) if identity not in compliance_ambiguous else None
            if desired is None:
                reasons.append("desired_image_missing_or_ambiguous")
            if compliance is None:
                reasons.append("cached_compliance_missing_or_ambiguous")
            desired_document = documents["lifecycle_desired_image"]
            desired_collected = parse_time(desired_document.get("collected_at")) if desired_document else None
            if desired_document and (desired_collected is None or desired_collected > evaluated):
                reasons.append("desired_collection_timestamp_unknown_invalid_or_future")
            document = documents["lifecycle_compliance"]
            collected_raw = document.get("collected_at") if document else None
            collected = parse_time(collected_raw)
            if collected is None or collected > evaluated:
                collected = None
                reasons.append("collection_timestamp_unknown_invalid_or_future")
            native = compliance.get("status") if compliance else None
            scan = _scan(compliance.get("scan_time") if compliance else None, collected, max_scan_age_hours)
            membership, hosts, membership_valid = {}, {}, True
            if compliance:
                hosts = compliance.get("hosts")
                if not isinstance(hosts, dict) or any(not isinstance(value, dict) for value in hosts.values()):
                    hosts, membership_valid = {}, False
                for bucket, expected in _BUCKETS.items():
                    values = compliance.get(bucket)
                    if not isinstance(values, list) or any(not isinstance(value, str) for value in values) or len(values) != len(set(values)):
                        membership_valid = False
                        continue
                    for host in values:
                        membership.setdefault(host, []).append(expected)
                if any(len(value) != 1 for value in membership.values()):
                    membership_valid = False
                available = {host for host, classes in membership.items() if classes == ["UNAVAILABLE"]}
                if set(hosts) != set(membership) - available:
                    membership_valid = False
                if not membership_valid:
                    reasons.append("host_classifications_missing_or_inconsistent")
                if available:
                    reasons.append("some_hosts_unavailable_in_cached_scan")
            status = _status(native, scan["scan_freshness"], reasons)
            desired_version = _version(desired, "base_image") if desired else None
            if desired_version is None and "desired_image_missing_or_ambiguous" not in reasons:
                reasons.append("desired_base_image_version_unknown")
                status = "unknown"
            record = {"target": name, "component": "vcenter", "record_type": "cluster", "cluster_id": identity,
                      "status": status, "unknown_reasons": reasons, "native_compliance_status": native, **scan,
                      "compliance_collected_at": collected_raw, "source_age_hours":
                      round((evaluated - collected).total_seconds() / 3600, 6) if collected else None,
                      "max_scan_age_hours": max_scan_age_hours, "scan_commit": compliance.get("commit") if compliance else None,
                      "desired_base_image_version": desired_version, "desired_image":
                      {key: value for key, value in desired.items() if key not in ("id", "cluster_id")} if desired else None,
                      "desired_image_collected_at": documents["lifecycle_desired_image"].get("collected_at")
                      if documents["lifecycle_desired_image"] else None,
                      "host_classification_counts": {bucket: len(compliance[bucket]) for bucket in _BUCKETS}
                      if compliance and membership_valid else None,
                      "host_detail_count": len(hosts) if membership_valid else None,
                      "notification_counts": compliance.get("notification_counts") if compliance else None}
            records.append(record)
            for host in sorted(set(hosts) | set(membership)):
                value = hosts.get(host, {})
                # Each host has its own cached status and scan time. Another
                # unavailable host does not erase valid evidence for this one.
                host_reasons = [reason for reason in reasons if reason not in (
                    "some_hosts_unavailable_in_cached_scan", "compliance_status_unknown_or_unavailable",
                    "scan_timestamp_unknown_invalid_or_future")]
                classes = membership.get(host, [])
                host_native = value.get("status") if value else "UNAVAILABLE" if classes == ["UNAVAILABLE"] else None
                if value and classes != [host_native]:
                    host_reasons.append("host_status_and_classification_disagree")
                host_scan = _scan(value.get("scan_time"), collected, max_scan_age_hours)
                base = value.get("base_image") if isinstance(value.get("base_image"), dict) else {}
                target_version = _version(base, "target")
                host_status = _status(host_native, host_scan["scan_freshness"], host_reasons)
                records.append({"target": name, "component": "vcenter", "record_type": "host", "cluster_id": identity,
                                "host_id": host, "status": host_status, "unknown_reasons": host_reasons,
                                "native_compliance_status": host_native, "cached_classifications": classes, **host_scan,
                                "scan_commit": value.get("commit"), "compliance_collected_at": collected_raw,
                                "current_base_image_version": _version(base, "current"),
                                "scan_target_base_image_version": target_version,
                                "desired_base_image_version": desired_version,
                                "scan_target_base_matches_collected_desired_base":
                                target_version == desired_version if target_version and desired_version else None,
                                "base_image_compliance": base or None,
                                "add_on_compliance": value.get("add_on"),
                                "component_compliance": value.get("components"),
                                "removed_component_compliance": value.get("removed_components"),
                                "solution_compliance": value.get("solutions"),
                                "notification_counts": value.get("notification_counts")})
    if not records:
        records.append({"record_type": "cluster", "status": "unknown", "unknown_reasons": ["no_lifecycle_resources_collected"]})
    return sanitize({"author": "Paul Bryant", "schema_version": "1.0", "report_type": "lifecycle_compliance",
                     "status": "partial" if any(row["status"] == "unknown" for row in records) else "success",
                     "records": records, "limitations": [
                         "Compliance describes the last existing scan, not a fresh scan. No scan, precheck, staging, or remediation is started.",
                         "Scan freshness is evaluated at saved collection time. source_age_hours identifies old evidence at report evaluation.",
                         "Desired images and compliance are separate observations. A matching base-image version alone does not prove that the scan used the complete current desired image or its alternative images.",
                         "Host classification is limited to the cached scan and configured clusters. This report does not establish current inventory coverage, hardware compatibility, or upgrade readiness.",
                         "Notification messages, remediation instructions, and hardware details are omitted; notification counts and software version evidence are retained.",
                     ]})
