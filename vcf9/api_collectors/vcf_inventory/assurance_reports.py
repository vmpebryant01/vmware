"""Backup freshness and authorization observations. Author: Paul Bryant."""

from datetime import datetime, timezone
from urllib.parse import urlsplit

from .exports import sanitize
from .report_support import parse_time, positive_number


def _report(kind, records, limitations):
    return sanitize({"author": "Paul Bryant", "schema_version": "1.0", "report_type": kind,
                     "status": "partial" if any(row.get("status") == "unknown" for row in records) else "success",
                     "records": records, "limitations": limitations})


def _targets(run, components):
    if not isinstance(run, dict) or not isinstance(run.get("summary"), dict) or not isinstance(run.get("resources"), dict):
        raise ValueError("A loaded completed inventory run is required.")
    targets = run["summary"].get("targets")
    if not isinstance(targets, list):
        raise ValueError("The run has no valid target list.")
    result, seen = [], set()
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("The run contains invalid target metadata.")
        if target.get("component") not in components:
            continue
        if any(not isinstance(target.get(key), str) or not target[key] for key in ("name", "component", "endpoint")):
            raise ValueError("The run contains incomplete target metadata.")
        identity = (target["name"], target["component"], target["endpoint"])
        if identity in seen:
            raise ValueError("The run contains duplicate target metadata.")
        seen.add(identity)
        result.append(target)
    return result


def _context(target):
    return {"target": target["name"], "component": target["component"], "endpoint": target["endpoint"]}


def _resource(run, target, resource):
    key = (target["name"], target["component"], resource)
    if key in run.get("unavailable", {}):
        return None
    document = run["resources"].get(key)
    if not isinstance(document, dict) or not isinstance(document.get("records"), list):
        return None
    if any(not isinstance(row, dict) for row in document["records"]):
        return None
    collection = document.get("collection", {})
    if not isinstance(collection, dict) or collection.get("coverage") not in (None, "complete"):
        return None
    return document


def _unavailable(target, resource, kind):
    return {**_context(target), "record_type": kind, "resource": resource, "status": "unknown",
            "observation": "resource_unavailable", "reason": "Resource was not collected successfully with complete coverage."}


def _iso(value):
    return value.isoformat(timespec="seconds") if value is not None else None


def _observed_at(run, document, evaluated_at):
    value = document.get("collected_at", run["summary"].get("completed_at"))
    observed = parse_time(value)
    return observed if observed is not None and observed <= evaluated_at else None


def _observation_fields(observed, evaluated_at):
    return {"observed_at": _iso(observed),
            "source_age_hours": round((evaluated_at - observed).total_seconds() / 3600, 6) if observed else None}


def _backup_observation(target, rows, kind, max_age_hours, observed_at, evaluated_at, epoch_unit=None):
    successful, failed, in_progress, unrecognized = [], [], 0, 0
    for row in rows:
        if target["component"] == "vcenter":
            status = row.get("status")
            if status == "SUCCEEDED":
                successful.append(parse_time(row.get("end_time")))
            elif status == "FAILED":
                failed.append(parse_time(row.get("end_time")))
            elif status in ("PENDING", "RUNNING", "BLOCKED"):
                in_progress += 1
            else:
                unrecognized += 1
        elif type(row.get("success")) is bool:
            destination = successful if row["success"] else failed
            destination.append(parse_time(row.get("end_time"), epoch_unit=epoch_unit) if epoch_unit else None)
        else:
            unrecognized += 1
    valid_success = [value for value in successful if value is not None and observed_at is not None and value <= observed_at]
    invalid_success_count = len(successful) - len(valid_success)
    valid_failed = [value for value in failed if value is not None and observed_at is not None and value <= observed_at]
    latest = max(valid_success) if valid_success else None
    latest_failure = max(valid_failed) if valid_failed else None
    age = (observed_at - latest).total_seconds() / 3600 if latest else None
    reason = None
    if observed_at is None:
        observation, status, reason = "freshness_unknown", "unknown", "observation_timestamp_unavailable_or_future"
    elif target["component"] == "nsx" and epoch_unit is None:
        observation, status, reason = "freshness_unknown", "unknown", "timestamp_unit_not_configured"
    elif invalid_success_count or unrecognized:
        observation, status = "freshness_unknown", "unknown"
    elif latest is None:
        observation, status = "no_success_in_visible_history", "unknown"
    elif age > max_age_hours:
        observation, status = "stale", "review"
    else:
        observation, status = "fresh", "observed"
    return {**_context(target), "record_type": "backup_history", "backup_kind": kind,
            **_observation_fields(observed_at, evaluated_at),
            "timestamp_basis": ("operator_supplied_epoch_milliseconds" if epoch_unit == "milliseconds" else "not_verified")
                               if target["component"] == "nsx" else "timezone_qualified_iso8601",
            "freshness_unknown_reason": reason,
            "status": status, "observation": observation, "max_age_hours": max_age_hours,
            "history_count": len(rows), "success_count": len(successful), "failure_count": len(failed),
            "in_progress_count": in_progress, "unrecognized_status_count": unrecognized,
            "success_timestamp_unknown_count": invalid_success_count,
            "failure_timestamp_unknown_count": len(failed) - len(valid_failed),
            "latest_dated_success_at": _iso(latest),
            "last_success_at": _iso(latest) if invalid_success_count == 0 else None,
            "last_success_age_hours": round(age, 6) if age is not None and invalid_success_count == 0 else None,
            "latest_dated_failure_at": _iso(latest_failure),
            "failure_after_latest_dated_success": (latest_failure > latest) if latest_failure is not None and latest is not None else None}


def build_backup_report(run, max_age_hours=24, now=None, nsx_time_unit=None):
    """Evaluate successful completion age within retained, account-visible history."""
    positive_number(max_age_hours, "max_age_hours")
    if nsx_time_unit not in (None, "milliseconds"):
        raise ValueError("nsx_time_unit must be milliseconds when supplied.")
    now = datetime.now(timezone.utc) if now is None else parse_time(now)
    if now is None:
        raise ValueError("now must be an aware datetime or an ISO timestamp with a timezone.")
    records = []
    targets = _targets(run, {"vcenter", "nsx"})
    for target in targets:
        if target["component"] == "vcenter":
            jobs = _resource(run, target, "backup_jobs")
            records.append(_unavailable(target, "backup_jobs", "backup_history") if jobs is None else
                           _backup_observation(target, jobs["records"], "appliance", max_age_hours, _observed_at(run, jobs, now), now))
            schedules = _resource(run, target, "backup_schedules")
            observed = _observed_at(run, schedules, now) if schedules is not None else None
            if schedules is None:
                records.append(_unavailable(target, "backup_schedules", "backup_schedule"))
            elif not schedules["records"]:
                records.append({**_context(target), "record_type": "backup_schedule", **_observation_fields(observed, now),
                                "status": "review" if observed is not None else "unknown",
                                "observation": "no_schedules_in_visible_inventory" if observed is not None else "schedule_observation_timestamp_unknown",
                                "schedule_count": 0})
            else:
                for schedule in schedules["records"]:
                    enabled = schedule.get("enable")
                    identifier = schedule.get("id")
                    known = type(enabled) is bool and isinstance(identifier, str) and bool(identifier) and observed is not None
                    record = {**_context(target), "record_type": "backup_schedule", "schedule_id": identifier,
                              **_observation_fields(observed, now),
                              "status": ("observed" if enabled else "review") if known else "unknown",
                              "observation": ("schedule_enabled" if enabled else "schedule_disabled") if known else "schedule_state_unknown",
                              "enabled": enabled if type(enabled) is bool else None}
                    for field in ("recurrence_info", "retention_info"):
                        if isinstance(schedule.get(field), dict):
                            allowed = ("minute", "hour", "days") if field == "recurrence_info" else ("max_count",)
                            record[field] = {key: schedule[field][key] for key in allowed if key in schedule[field]}
                    records.append(record)
        else:
            history = _resource(run, target, "backup_history")
            if history is None:
                records.append(_unavailable(target, "backup_history", "backup_history"))
            else:
                kinds = ("cluster", "node", "inventory")
                for kind in kinds:
                    rows = [row for row in history["records"] if row.get("backup_kind") == kind]
                    records.append(_backup_observation(target, rows, kind, max_age_hours, _observed_at(run, history, now), now,
                                                       epoch_unit=nsx_time_unit))
                if any(row.get("backup_kind") not in kinds for row in history["records"]):
                    records.append({**_context(target), "record_type": "backup_history", "status": "unknown",
                                    "observation": "unrecognized_backup_kind"})
    if not targets:
        records.append({"record_type": "backup_history", "status": "unknown", "observation": "no_eligible_targets"})
    return _report("backup_freshness", records, [
        "History is limited to records retained by each appliance and visible to the collection account.",
        "A successful job and an enabled schedule do not prove backup content integrity, destination availability, or restorability.",
        "Freshness is evaluated as of the saved resource collected_at timestamp, or summary completed_at only when collected_at is absent. source_age_hours shows the age of that evidence at evaluation; later backups are not observed.",
        "vCenter completion timestamps require explicit timezones. NSX age remains unknown unless the operator supplies nsx_time_unit=milliseconds; its explicit timestamp-unit schema could not be verified. Raw numeric times remain in the inventory. Missing, invalid, or future success timestamps remain unknown.",
        "NSX cluster, node, and inventory histories are evaluated separately. NSX schedule configuration is outside this report.",
    ])


_ASSIGNMENT_FIELDS = ("principal_type", "principal_name", "principal_domain", "role_id", "object_type", "object_id", "propagating")


def _assignment_key(value):
    return tuple(value.get(field) for field in _ASSIGNMENT_FIELDS)


def _baseline(baseline):
    if baseline is None:
        return None
    if not isinstance(baseline, dict) or set(baseline) - {"author", "schema_version", "permissions"}:
        raise ValueError("The access baseline must contain a permissions array and optional author/schema_version.")
    if "author" in baseline and (not isinstance(baseline["author"], str) or not baseline["author"].strip() or len(baseline["author"]) > 200):
        raise ValueError("The optional baseline author must be a nonempty string of at most 200 characters.")
    if baseline.get("schema_version", "1.0") != "1.0":
        raise ValueError("The baseline schema_version must be 1.0 when supplied.")
    permissions = baseline.get("permissions")
    if not isinstance(permissions, list):
        raise ValueError("The access baseline permissions field must be an array.")
    seen, result = set(), []
    required = {"target", "endpoint", *_ASSIGNMENT_FIELDS}
    for entry in permissions:
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("Each baseline entry must specify an exact target, endpoint, principal, role, object, and propagation.")
        for field in required - {"principal_domain", "propagating"}:
            if not isinstance(entry[field], str) or not entry[field]:
                raise ValueError("Access baseline identifiers must be nonempty strings.")
        if entry["principal_domain"] is not None and not isinstance(entry["principal_domain"], str):
            raise ValueError("The baseline principal_domain must be a string or null.")
        if type(entry["propagating"]) is not bool:
            raise ValueError("The baseline propagating field must be a boolean.")
        try:
            url = urlsplit(entry["endpoint"])
            valid_port = url.port is None or 1 <= url.port <= 65535
        except ValueError:
            raise ValueError("Baseline endpoints must be HTTPS origins.") from None
        if (url.scheme != "https" or not url.hostname or not valid_port or url.username is not None
                or url.password is not None or url.path or url.query or url.fragment
                or "\\" in entry["endpoint"] or any(c.isspace() for c in entry["endpoint"])):
            raise ValueError("Baseline endpoints must be HTTPS origins without paths or credentials.")
        key = (entry["target"], entry["endpoint"], *_assignment_key(entry))
        if key in seen:
            raise ValueError("The baseline repeats an assignment.")
        seen.add(key)
        result.append(entry)
    return result


def _roles_index(document):
    result, ambiguous = {}, set()
    if document is None:
        return result, ambiguous
    for role in document["records"]:
        identifier = role.get("role_id", role.get("id"))
        if not isinstance(identifier, str) or not identifier:
            ambiguous.add(None)
        elif identifier in result or identifier in ambiguous:
            result.pop(identifier, None)
            ambiguous.add(identifier)
        else:
            result[identifier] = role
    return result, ambiguous


def _role_observation(role, threshold):
    privileges = role.get("privileges") if role else None
    if not isinstance(privileges, list) or any(not isinstance(value, str) or not value for value in privileges):
        return {"role_name": role.get("name") if role else None, "role_privilege_count": None,
                "broad_role": None, "role_status": "unknown"}
    count = len(set(privileges))
    return {"role_name": role.get("name"), "role_system": role.get("system"),
            "role_privilege_count": count, "broad_role": count >= threshold, "role_status": "observed"}


def build_access_report(run, baseline=None, broad_privilege_threshold=100):
    """Join explicit assignments to role metadata without inferring effective access."""
    if type(broad_privilege_threshold) is not int or not 1 <= broad_privilege_threshold <= 100000:
        raise ValueError("broad_privilege_threshold must be an integer from 1 to 100000.")
    baseline = _baseline(baseline)
    baseline_index = {} if baseline is None else {
        (entry["target"], entry["endpoint"], *_assignment_key(entry)): entry for entry in baseline}
    observed, checked_targets, records = set(), set(), []
    targets = _targets(run, {"vcenter"})
    for target in targets:
        context = _context(target)
        role_document = _resource(run, target, "authorization_roles")
        permissions = _resource(run, target, "authorization_permissions")
        roles, ambiguous = _roles_index(role_document)
        if role_document is None:
            records.append(_unavailable(target, "authorization_roles", "role_catalog"))
        elif ambiguous:
            records.append({**context, "record_type": "role_catalog", "status": "unknown",
                            "observation": "role_identifiers_invalid_or_ambiguous"})
        for identifier, role in sorted(roles.items()):
            description = _role_observation(role, broad_privilege_threshold)
            records.append({**context, "record_type": "role", "role_id": identifier, **description,
                            "status": "unknown" if description["role_status"] == "unknown" else
                                      "review" if description["broad_role"] else "observed",
                            "observation": "role_privileges", "broad_privilege_threshold": broad_privilege_threshold})
        if permissions is None:
            records.append(_unavailable(target, "authorization_permissions", "permission_assignments"))
            continue
        if not permissions["records"]:
            records.append({**context, "record_type": "permission_assignments", "status": "observed",
                            "observation": "no_assignments_in_visible_inventory", "assignment_count": 0})
        identifier_counts = {}
        for permission in permissions["records"]:
            identifier = permission.get("permission_id", permission.get("id"))
            if isinstance(identifier, str):
                identifier_counts[identifier] = identifier_counts.get(identifier, 0) + 1
        all_assignments_valid = True
        for permission in permissions["records"]:
            identifier = permission.get("permission_id", permission.get("id"))
            valid = (isinstance(identifier, str) and bool(identifier) and identifier_counts.get(identifier) == 1
                     and all(isinstance(permission.get(field), str) and bool(permission[field])
                             for field in ("principal_type", "principal_name", "role_id", "object_type", "object_id"))
                     and (permission.get("principal_domain") is None or isinstance(permission["principal_domain"], str))
                     and type(permission.get("propagating")) is bool)
            if not valid:
                all_assignments_valid = False
                records.append({**context, "record_type": "permission", "status": "unknown",
                                "observation": "assignment_invalid_or_ambiguous"})
                continue
            key = (target["name"], target["endpoint"], *_assignment_key(permission))
            observed.add(key)
            match = key in baseline_index
            role = roles.get(permission["role_id"])
            description = _role_observation(role, broad_privilege_threshold)
            reasons = []
            if description["broad_role"]:
                reasons.append("role_privilege_count_at_or_above_threshold")
            if baseline is not None and not match:
                reasons.append("assignment_not_in_baseline")
            row = {**context, "record_type": "permission", "permission_id": identifier,
                   **{field: permission.get(field) for field in _ASSIGNMENT_FIELDS}, **description,
                   "global_scope": permission["object_type"] == "GlobalAcl" and permission["object_id"] == "GlobalAcl",
                   "baseline_status": "not_supplied" if baseline is None else "observed" if match else "not_in_baseline",
                   "review_reasons": reasons, "broad_privilege_threshold": broad_privilege_threshold,
                   "status": "unknown" if description["role_status"] == "unknown" else "review" if reasons else "observed",
                   "observation": "explicit_assignment"}
            records.append(row)
        if all_assignments_valid:
            checked_targets.add((target["name"], target["endpoint"]))
    for key, entry in sorted(baseline_index.items(), key=lambda item: repr(item[0])):
        if key in observed:
            continue
        checked = (entry["target"], entry["endpoint"]) in checked_targets
        records.append({"target": entry["target"], "component": "vcenter", "endpoint": entry["endpoint"],
                        "record_type": "baseline_assignment", **{field: entry[field] for field in _ASSIGNMENT_FIELDS},
                        "status": "review" if checked else "unknown",
                        "observation": "baseline_assignment_not_observed" if checked else "baseline_scope_not_observed"})
    if not targets:
        records.append({"record_type": "permission_assignments", "status": "unknown", "observation": "no_eligible_targets"})
    return _report("access_permissions", records, [
        "Assignments and roles reflect the collection account's visible API scope; absence is an observation, not proof of revocation.",
        "Privilege count is an operator-selected review threshold, not a security severity or a determination that an administrator role is inappropriate.",
        "Group membership, user-specific precedence, inheritance resolution, and effective user access are not evaluated.",
        "The optional baseline matches exact target, endpoint, principal, role identifier, object, and propagation. Matching does not establish that an assignment is safe.",
    ])
