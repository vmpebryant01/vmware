"""Evidence-based activity reports from saved observations. Author: Paul Bryant."""

import math
from datetime import datetime, timezone

from .activity import COUNTERS, HCX_FIELDS, REQUEST_FIELDS, STAT_CONTEXT
from .report_support import documents, parse_time, positive_number


_STAT_ID = ("domain_id", "policy_id", "rule_id", "enforcement_point", "container_cluster_path") + STAT_CONTEXT
_HCX_PROGRESS = ("progress_transfer_progress", "progress_transfer_completed",
                 "progress_switchover_progress", "progress_switchover_completed")
_TERMINAL = {"APPROVAL_REJECTED", "ABORTED", "SUCCESSFUL", "FAILED"}
_NONTERMINAL = {"CREATED", "PENDING", "INITIALIZATION", "CHECKING_APPROVAL", "APPROVAL_PENDING",
                "USER_INTERACTION_PENDING", "INPROGRESS", "COMPLETION"}


def _note(report, message, partial=False):
    if message not in report["limitations"]:
        report["limitations"].append(message)
    if partial:
        report["status"] = "partial"


def _report(run, component, resource, report_type):
    report = {"author": "Paul Bryant", "schema_version": "1.0", "report_type": report_type,
              "status": "success", "records": [], "scopes": [], "limitations": []}
    selected = documents(run, component, resource)
    if not selected:
        _note(report, "No complete saved observations are available for the requested resource.", True)
    if any(key[1:] == (component, resource) for key in run.get("unavailable", {})):
        _note(report, "One or more requested observations are unavailable or incomplete.", True)
    return report, selected


def _selected(row, fields):
    return {field: value for field in fields if (value := row.get(field)) is None
            or type(value) in (str, int, bool) or (type(value) is float and math.isfinite(value))}


def _identity(row, fields):
    values = tuple(row.get(field) for field in fields)
    if not values or any(value is not None and not isinstance(value, str) for value in values):
        return None
    return values if all(values[index] for index in range(min(4, len(values)))) else None


def _index(records, fields):
    index, ambiguous, invalid = {}, set(), False
    for row in records:
        identity = _identity(row, fields)
        if identity is None:
            invalid = True
        elif identity in index or identity in ambiguous:
            index.pop(identity, None)
            ambiguous.add(identity)
        else:
            index[identity] = row
    return index, bool(ambiguous) or invalid


def _scope(document, component):
    collection = document.get("collection")
    if not isinstance(collection, dict) or collection.get("coverage") != "complete":
        return None
    if component == "hcx":
        value = collection.get("include_archived")
        return {"include_archived": value} if type(value) is bool else None
    if component == "vcf_automation":
        ids = collection.get("queried_deployment_ids")
        if (collection.get("api_family") not in ("all_apps", "vm_apps") or not isinstance(ids, list)
                or any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids)):
            return None
        return {"api_family": collection["api_family"], "deployment_ids": sorted(ids)}
    policies, rules = collection.get("policy_ids"), collection.get("resolved_rule_ids")
    if (not isinstance(policies, list) or not policies or any(not isinstance(value, str) or not value for value in policies)
            or len(set(policies)) != len(policies) or not isinstance(rules, dict) or set(rules) != set(policies)
            or not isinstance(collection.get("domain_id"), str)
            or not isinstance(collection.get("enforcement_point_path"), str)):
        return None
    for values in rules.values():
        if (not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values)
                or len(set(values)) != len(values)):
            return None
    return {"domain_id": collection["domain_id"], "enforcement_point_path": collection["enforcement_point_path"],
            "policy_ids": sorted(policies), "resolved_rule_ids": {key: sorted(value) for key, value in sorted(rules.items())}}


def _previous(document, previous, component, resource, report):
    if previous is None:
        return None, None
    key = (document["target"], component, resource)
    older = previous.get("resources", {}).get(key)
    if older is None:
        _note(report, "A matching complete prior observation is unavailable; affected intervals remain unknown.")
        return None, None
    scope = _scope(document, component)
    if (older.get("endpoint") != document.get("endpoint") or scope is None
            or _scope(older, component) != scope or older.get("scope_filters", {}) != document.get("scope_filters", {})):
        _note(report, "Endpoint or resolved collection scope differs; affected intervals are not compared.")
        return None, None
    current_time, prior_time = parse_time(document.get("collected_at")), parse_time(older.get("collected_at"))
    if current_time is None or prior_time is None or current_time <= prior_time:
        _note(report, "Saved observation times do not establish a positive comparison interval.", True)
        return None, None
    return older, (current_time - prior_time).total_seconds() / 60


def _scope_record(report, document, component):
    scope = _scope(document, component)
    report["scopes"].append({"target": document["target"], "endpoint": document.get("endpoint"),
                             "collected_at": document.get("collected_at"), "scope": scope,
                             "record_count": len(document["records"])})
    if scope is None:
        _note(report, "Some observations lack complete resolved scope evidence.", True)
    return scope


def _active(row):
    return (row.get("progress_isDone") is not True and row.get("progress_state_isDone") is not True
            and any(row.get(key) in (True, 1) for key in
                    ("progress_state_isTransferProgress", "progress_state_isSwitchoverProgress")))


def _hcx_duration(row, document, unit):
    if unit is None:
        return None
    observation = parse_time(document.get("collected_at"))
    start = parse_time(row.get("progress_startTime"), epoch_unit=unit)
    raw_end = row.get("progress_endTime")
    end = parse_time(raw_end, epoch_unit=unit)
    if observation is None or start is None or start > observation:
        return None
    terminal = row.get("progress_isDone") is True or row.get("progress_state_isDone") is True
    if terminal:
        return (end - start).total_seconds() if end and start <= end <= observation else None
    if _active(row) and raw_end in (None, 0):
        return (observation - start).total_seconds()
    return None


def build_hcx_report(run, previous=None, stalled_minutes=30, hcx_time_unit=None):
    """Describe migration progress; a stall candidate needs two comparable active observations."""
    positive_number(stalled_minutes, "stalled_minutes")
    if hcx_time_unit not in (None, "milliseconds", "seconds"):
        raise ValueError("hcx_time_unit must be seconds or milliseconds when supplied.")
    report, selected = _report(run, "hcx", "migrations", "hcx_migrations")
    _note(report, "A possible stall means no selected progress change between two snapshots; it does not prove a migration is stuck.")
    fields = tuple(field.replace(".", "_") for field in HCX_FIELDS)
    if previous is None:
        _note(report, "One snapshot cannot establish a progress interval or a migration stall.")
    if hcx_time_unit is None:
        _note(report, "HCX numeric timestamp units are not established; elapsed durations remain unknown unless an operator supplies a unit.")
    for document in selected:
        _scope_record(report, document, "hcx")
        older, interval = _previous(document, previous, "hcx", "migrations", report)
        current, invalid = _index(document["records"], ("id",))
        prior, prior_invalid = _index(older["records"], ("id",)) if older else ({}, False)
        if invalid or prior_invalid:
            _note(report, "Missing or ambiguous migration identifiers prevent some assessments.", True)
        for identity, row in current.items():
            result = _selected(row, fields)
            result.update(target=document["target"], observation_time=document.get("collected_at"),
                          comparison_minutes=interval, possible_stall=None, assessment="interval_unknown",
                          duration_seconds=_hcx_duration(row, document, hcx_time_unit),
                          timestamp_basis=(f"operator_supplied_{hcx_time_unit}" if hcx_time_unit else "unit_not_verified"))
            if hcx_time_unit is not None and result["duration_seconds"] is None:
                _note(report, "Some migration timestamps or states cannot establish elapsed duration with the supplied unit.")
            if row.get("progress_isDone") is True or row.get("progress_state_isDone") is True:
                result["assessment"] = "completed_observation"
                result["possible_stall"] = False
            elif not _active(row):
                result["assessment"] = "active_transfer_not_established"
            elif identity in prior and interval is not None:
                old = prior[identity]
                usable = [key for key in _HCX_PROGRESS if type(row.get(key)) in (int, float)
                          and type(old.get(key)) in (int, float) and math.isfinite(row[key]) and math.isfinite(old[key])]
                available = [key for key in _HCX_PROGRESS if row.get(key) is not None or old.get(key) is not None]
                if not _active(old) or not usable or len(available) != len(usable):
                    result["assessment"] = "comparable_active_progress_not_available"
                elif row.get("migrationId") != old.get("migrationId") or any(row[key] < old[key] for key in usable):
                    result["assessment"] = "restart_or_counter_decrease_possible"
                elif (any(row[key] > old[key] for key in usable) or row.get("state") != old.get("state")
                      or row.get("progress_state_status") != old.get("progress_state_status")):
                    result.update(assessment="progress_or_state_change_observed", possible_stall=False)
                elif interval >= stalled_minutes:
                    result.update(assessment="possible_stall_no_observed_progress", possible_stall=True)
                else:
                    result["assessment"] = "observation_interval_below_threshold"
            report["records"].append(result)
    return report


def build_nsx_usage_report(run, previous=None):
    """Compare native counters per exact statistics context without inferring rule disuse."""
    report, selected = _report(run, "nsx", "rule_statistics", "nsx_rule_usage")
    _note(report, "Zero counters or unchanged counters do not establish that a rule is unused.")
    _note(report, "The API documents no counter reset timestamp; decreases suggest reset or replacement, and undetected resets can affect positive differences.")
    if previous is None:
        _note(report, "One snapshot cannot establish counter changes over an observation interval.")
    for document in selected:
        _scope_record(report, document, "nsx")
        older, interval = _previous(document, previous, "nsx", "rule_statistics", report)
        current, invalid = _index(document["records"], _STAT_ID)
        prior, prior_invalid = _index(older["records"], _STAT_ID) if older else ({}, False)
        if invalid or prior_invalid:
            _note(report, "Missing or duplicate statistics contexts prevent some counter comparisons.", True)
        for identity, row in current.items():
            result = _selected(row, _STAT_ID + COUNTERS)
            result.update(target=document["target"], observation_time=document.get("collected_at"),
                          comparison_minutes=interval, assessment="interval_unknown", observed_counter_change={})
            values = {key: row[key] for key in COUNTERS if type(row.get(key)) is int and row[key] >= 0}
            if not values:
                result["assessment"] = "counters_not_available"
            elif identity in prior and interval is not None:
                old = prior[identity]
                changes = {key: value - old[key] for key, value in values.items()
                           if type(old.get(key)) is int and old[key] >= 0}
                if not isinstance(row.get("internal_rule_id"), str) or not row["internal_rule_id"]:
                    result["assessment"] = "realized_rule_identity_not_available"
                elif not changes:
                    result["assessment"] = "comparable_counters_not_available"
                elif any(value < 0 for value in changes.values()):
                    result["assessment"] = "counter_reset_or_replacement_possible"
                else:
                    result["observed_counter_change"] = changes
                    result["assessment"] = ("counter_increase_observed" if any(changes.values())
                                            else "no_counter_increase_observed")
            report["records"].append(result)
    return report


def build_automation_report(run, long_running_minutes=60, now=None):
    """Describe request state and age; thresholds flag nonterminal requests for investigation."""
    positive_number(long_running_minutes, "long_running_minutes")
    reference = parse_time(datetime.now(timezone.utc) if now is None else now)
    if reference is None:
        raise ValueError("now must be a timezone-aware time.")
    report, selected = _report(run, "vcf_automation", "deployment_requests", "automation_requests")
    report["evaluated_at"] = reference.isoformat().replace("+00:00", "Z")
    _note(report, "Age flags describe saved request observations, not live request state or service-level violations.")
    for document in selected:
        _scope_record(report, document, "vcf_automation")
        current, invalid = _index(document["records"], ("deploymentId", "id"))
        if invalid:
            _note(report, "Missing or ambiguous request identifiers prevent some assessments.", True)
        observation = parse_time(document.get("collected_at"))
        if observation is None or observation > reference:
            _note(report, "Saved request observation time is invalid or later than the evaluation time.", True)
        for row in current.values():
            result = _selected(row, REQUEST_FIELDS)
            result.update(target=document["target"], observation_time=document.get("collected_at"),
                          age_minutes=None, long_running=None, assessment="state_or_time_unknown")
            status, created, completed = row.get("status"), parse_time(row.get("createdAt")), parse_time(row.get("completedAt"))
            if status in _TERMINAL:
                result.update(assessment="terminal_request", long_running=False)
                if created and completed and observation and created <= completed <= observation <= reference:
                    result["duration_minutes"] = (completed - created).total_seconds() / 60
                elif row.get("completedAt"):
                    _note(report, "Some completed request timestamps cannot establish duration at the saved observation.", True)
            elif status in _NONTERMINAL:
                if row.get("completedAt"):
                    _note(report, "Some request completion timestamps conflict with nonterminal state.", True)
                    result["assessment"] = "completion_time_state_conflict"
                elif created and observation and created <= observation <= reference:
                    # Age is evaluated at collection time so old saved runs do not create new live alarms.
                    age = (observation - created).total_seconds() / 60
                    result.update(age_minutes=age, long_running=age >= long_running_minutes,
                                  assessment="nonterminal_request_age")
                    result["waiting"] = status in {"CREATED", "PENDING", "CHECKING_APPROVAL", "APPROVAL_PENDING", "USER_INTERACTION_PENDING"}
                else:
                    _note(report, "Some request timestamps cannot establish age at the saved observation.", True)
            else:
                _note(report, "Some request states are missing or outside the documented status enumeration.", True)
            report["records"].append(result)
    return report
