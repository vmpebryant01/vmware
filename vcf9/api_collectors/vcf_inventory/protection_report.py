"""Compare explicit protection requirements with observed evidence. Author: Paul Bryant."""

from datetime import datetime, timezone

from .report_support import parse_time, positive_number, record_index

REPLICATION_STATES = {"FULL_SYNC", "SYNC", "INITIAL_FULL_SYNC", "PAUSED", "RPO_VIOLATION", "MOVING", "OK", "ERROR",
                      "CONFIGURING", "NOT_ACTIVE", "UNKNOWN", "SYNC_RPO_VIOLATION", "NOT_ACTIVE_RPO_VIOLATION",
                      "ERROR_RPO_VIOLATION", "FULL_SYNC_RPO_VIOLATION", "RECOVERING", "RECOVERED", "DISK_RESIZING"}


def _identifier(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and len(value) <= 500 and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) - {"author", "requirements"}:
        raise ValueError("Protection policy must contain requirements and an optional author.")
    requirements = policy.get("requirements")
    if not isinstance(requirements, list) or not requirements or len(requirements) > 100000:
        raise ValueError("Protection policy requires a nonempty requirements array with at most 100000 entries.")
    seen = set()
    for requirement in requirements:
        allowed = {"vcenter_target", "vm_id", "replication", "site_recovery", "max_sync_age_hours"}
        if (not isinstance(requirement, dict) or set(requirement) - allowed
                or not all(_identifier(requirement.get(key)) for key in ("vcenter_target", "vm_id"))
                or not any(key in requirement for key in ("replication", "site_recovery"))):
            raise ValueError("Each protection requirement needs a vCenter target, VM ID, and at least one explicit protection reference.")
        key = (requirement["vcenter_target"], requirement["vm_id"])
        if key in seen:
            raise ValueError("Protection requirements repeat a vCenter VM identifier.")
        seen.add(key)
        positive_number(requirement.get("max_sync_age_hours", 24), "max_sync_age_hours")
        for reference, required in (("replication", {"target", "pairing_id", "source_vc_id", "vm_id"}),
                                    ("site_recovery", {"target", "pairing_id", "group_id", "vm_id"})):
            if reference not in requirement:
                continue
            value = requirement[reference]
            if not isinstance(value, dict) or set(value) != required or not all(_identifier(item) for item in value.values()):
                raise ValueError("Protection references must explicitly identify the target, pairing, and native VM context.")
    return requirements


def _paired_scope(document, pairing):
    if document.get("pairing_id") is not None:
        return document["pairing_id"] == pairing
    details = document.get("collection", {})
    pairings = details.get("queried_pairing_ids") if isinstance(details, dict) else None
    return isinstance(pairings, list) and all(_identifier(value) for value in pairings) and pairing in pairings


def _replication(run, reference, max_age, now):
    document = run["resources"].get((reference["target"], "vsphere_replication", "replications"))
    observation = {"state": "unknown", "target": reference["target"], "pairing_id": reference["pairing_id"]}
    if document is None or not _paired_scope(document, reference["pairing_id"]):
        observation["reason"] = "Successful replication evidence for the required pairing was not collected."
        return observation
    if document.get("source_vc_guid") not in (None, reference["source_vc_id"]):
        observation["reason"] = "The collected replication source-vCenter scope differs."
        return observation
    matches = [row for row in document["records"] if row.get("pairing_id") == reference["pairing_id"]
               and row.get("source_vc_id") == reference["source_vc_id"] and row.get("vm_id") == reference["vm_id"]]
    if len(matches) > 1:
        observation["reason"] = "More than one replication matches the explicitly identified VM."
        return observation
    if not matches:
        if any(not all(_identifier(row.get(field)) for field in ("pairing_id", "source_vc_id", "vm_id")) for row in document["records"]):
            observation["reason"] = "Some replication records lack the identifiers needed to establish absence."
        else:
            observation.update(state="gap", reason="Required VM was not observed in the selected replication inventory.")
        return observation
    row = matches[0]
    status = row.get("status") if isinstance(row.get("status"), dict) else {}
    last_sync = parse_time(row.get("last_sync_time"), "milliseconds")
    observed_at = parse_time(document.get("collected_at"))
    rpo = row.get("current_rpo_violation")
    native_status = status.get("status")
    observation.update(state="observed", replication_id=row.get("id"), native_status=native_status,
                       configuration_state=row.get("configuration_state"), rpo_minutes=row.get("rpo"),
                       last_sync_time=row.get("last_sync_time"), current_rpo_violation_minutes=rpo,
                       observed_at=document.get("collected_at"), findings=[])
    if status.get("rpo_violation") is True or (type(rpo) in (int, float) and rpo > 0) or (isinstance(native_status, str) and "RPO_VIOLATION" in native_status):
        observation["findings"].append("The API reports an RPO violation.")
    if row.get("configuration_state") == "ERROR" or native_status in ("ERROR", "PAUSED", "NOT_ACTIVE", "ERROR_RPO_VIOLATION", "NOT_ACTIVE_RPO_VIOLATION"):
        observation["findings"].append("The API reports an error, paused, or inactive replication state.")
    if observed_at is None or observed_at > now:
        observation.update(state="unknown", reason="The saved replication observation lacks a valid past collection time.")
    elif last_sync is None or last_sync > observed_at:
        observation.update(state="unknown", reason="A valid past synchronization timestamp was not available.")
    else:
        age = (observed_at - last_sync).total_seconds() / 3600
        observation["sync_age_hours"] = age
        observation["observation_age_hours"] = (now - observed_at).total_seconds() / 3600
        observation["max_sync_age_hours"] = max_age
        if age > max_age:
            observation["findings"].append("Synchronization age exceeds the operator's configured threshold.")
    if not isinstance(native_status, str) or native_status not in REPLICATION_STATES or native_status == "UNKNOWN":
        observation.update(state="unknown", reason="The API did not provide a known replication status.")
    observation["evidence_complete"] = observation["state"] != "unknown"
    if observation["findings"]:
        observation["state"] = "exception"
    return observation


def _site_recovery(run, reference):
    document = run["resources"].get((reference["target"], "live_site_recovery", "group_vms"))
    observation = {"state": "unknown", "target": reference["target"], "pairing_id": reference["pairing_id"], "group_id": reference["group_id"]}
    if document is None or not _paired_scope(document, reference["pairing_id"]):
        observation["reason"] = "Successful protected-VM evidence for the required pairing was not collected."
        return observation
    details = document.get("collection", {})
    groups = details.get("queried_group_ids") if isinstance(details, dict) else None
    if not isinstance(groups, list) or not all(_identifier(value) for value in groups) or reference["group_id"] not in groups:
        observation["reason"] = "The required protection group was outside the collected scope."
        return observation
    matches = [row for row in document["records"] if row.get("pairing_id") == reference["pairing_id"]
               and row.get("group_id") == reference["group_id"] and row.get("id") == reference["vm_id"]]
    if len(matches) > 1:
        observation["reason"] = "The required protected VM identifier is ambiguous."
    elif not matches:
        if any(not all(_identifier(row.get(field)) for field in ("pairing_id", "group_id", "id")) for row in document["records"]):
            observation["reason"] = "Some protected VM records lack identifiers needed to establish absence."
        else:
            observation.update(state="gap", reason="Required VM was not observed in the selected protection group.")
    else:
        row = matches[0]
        errors = row.get("protection_error_count")
        native = row.get("protection_status")
        complete = isinstance(native, str) and bool(native) and native != "UNKNOWN" and type(errors) is int and errors >= 0
        observation.update(state="exception" if type(errors) is int and errors > 0 else "observed" if complete else "unknown",
                           membership_observed=True, native_status=native, protection_error_count=errors, evidence_complete=complete)
        if not complete:
            observation["reason"] = "Membership was observed, but complete native protection-state evidence was not returned."
    return observation


def build_protection_report(run, policy, now=None):
    requirements = validate_policy(policy)
    now = parse_time(now or datetime.now(timezone.utc))
    if now is None:
        raise ValueError("Protection evaluation time must include a timezone.")
    result = {"author": "Paul Bryant", "schema_version": "1.0", "report_type": "protection_gaps", "status": "success", "records": [],
              "limitations": ["Requirements explicitly map native identifiers; display names and coincident local VM IDs are never matched automatically.",
                              "Observations cover only the account-visible inventory and selected API scopes, not proof of recoverability.",
                              "Synchronization-age thresholds apply at the saved resource collection time; reading an older run does not establish current recovery status."]}
    for requirement in requirements:
        document = run["resources"].get((requirement["vcenter_target"], "vcenter", "vms"))
        row = {"vcenter_target": requirement["vcenter_target"], "vm_id": requirement["vm_id"], "observations": {}}
        if document is None:
            row["inventory_state"] = "unknown"
        else:
            records, duplicates = record_index(document, "vm")
            vm = records.get(requirement["vm_id"])
            row["inventory_state"] = "unknown" if requirement["vm_id"] in duplicates else "observed" if vm else "not_observed"
            row["name"] = vm.get("name") if vm else None
        if "replication" in requirement:
            row["observations"]["replication"] = _replication(run, requirement["replication"], requirement.get("max_sync_age_hours", 24), now)
        if "site_recovery" in requirement:
            row["observations"]["site_recovery"] = _site_recovery(run, requirement["site_recovery"])
        states = [item["state"] for item in row["observations"].values()]
        uncertain = "unknown" in states or any(item.get("evidence_complete") is False for item in row["observations"].values())
        row["state"] = "exception" if any(state in ("gap", "exception") for state in states) else "unknown" if row["inventory_state"] != "observed" or "unknown" in states else "observed"
        if row["inventory_state"] != "observed" or uncertain:
            result["status"] = "partial"
        result["records"].append(row)
    return result
