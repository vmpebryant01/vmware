"""Compare like-for-like completed inventories. Author: Paul Bryant."""

import argparse
import fnmatch
import json
import sys
from pathlib import Path

from .exports import sanitize, write_json, write_resource
from .runs import RunError, identity_for, load_run

SCOPE_FIELDS = ("endpoint", "scope_filters", "site_id", "enforcement_point_id", "domain_id",
                "api_family", "api_version", "org_id", "pairing_id", "source_vc_guid", "domain_ids",
                "task_days", "certificate_attention_days", "policy_ids", "srm_ids", "resource_ids", "stat_keys")
DEFAULT_IGNORES = ("_links", "links")


def _clean(value, ignores, prefix=""):
    if isinstance(value, dict):
        return {key: _clean(item, ignores, f"{prefix}.{key}" if prefix else key)
                for key, item in value.items()
                if not any(fnmatch.fnmatchcase(f"{prefix}.{key}" if prefix else key, pattern) for pattern in ignores)}
    if isinstance(value, list):
        return [_clean(item, ignores, prefix + "[]") for item in value]
    return value


def _index(key, records):
    result = {}
    for row in records:
        identity = identity_for(key[1], key[2], row)
        if identity is None:
            raise RunError("At least one record has no supported stable identifier.")
        if identity in result:
            raise RunError("Duplicate record identifiers prevent an unambiguous comparison.")
        result[identity] = row
    return result


def _certificate_domains(document):
    collection = document.get("collection")
    domains = collection.get("queried_domain_ids") if isinstance(collection, dict) else None
    if (not isinstance(domains, list) or any(not isinstance(value, str) or not value for value in domains)
            or len(set(domains)) != len(domains)):
        return None
    return sorted(domains)


def compare_runs(before, after, ignore_fields=()):
    """Missing, failed and differently scoped resources never imply deletion."""
    old, new = load_run(before), load_run(after)
    ignores = tuple(dict.fromkeys(DEFAULT_IGNORES + tuple(ignore_fields)))
    report = {"author": "Paul Bryant", "schema_version": "1.0", "ignored_fields": list(ignores),
              "before_completed_at": old["summary"]["completed_at"], "after_completed_at": new["summary"]["completed_at"],
              "resources": [], "status": "success"}
    keys = set(old["resources"]) | set(new["resources"]) | set(old["unavailable"]) | set(new["unavailable"])
    for key in sorted(keys):
        result = {"target": key[0], "component": key[1], "resource": key[2]}
        report["resources"].append(result)
        left, right = old["resources"].get(key), new["resources"].get(key)
        reason = None
        if left is None or right is None:
            reason = "Resource is missing or unsuccessful in at least one run."
        elif any(left.get(field) != right.get(field) for field in SCOPE_FIELDS):
            reason = "Endpoint or configured collection scope differs."
        elif key[2] == "certificates":
            left_domains, right_domains = _certificate_domains(left), _certificate_domains(right)
            if left_domains is None or right_domains is None:
                reason = "Queried certificate domain scope is unavailable or invalid."
            elif left_domains != right_domains:
                reason = "The queried certificate domain scope differs."
        if reason:
            result.update(status="skipped", reason=reason)
            report["status"] = "partial"
            continue
        try:
            a, b = _index(key, left["records"]), _index(key, right["records"])
        except RunError as exc:
            result.update(status="skipped", reason=str(exc))
            report["status"] = "partial"
            continue
        added = [{"identity": list(i), "record": b[i]} for i in sorted(b.keys() - a.keys())]
        removed = [{"identity": list(i), "record": a[i]} for i in sorted(a.keys() - b.keys())]
        resource_ignores = ignores + (("tasksCompletedAfterEpochMs",) if key[2] == "failed_tasks" else ())
        changed = [{"identity": list(i), "before": a[i], "after": b[i]} for i in sorted(a.keys() & b.keys())
                   if _clean(a[i], resource_ignores) != _clean(b[i], resource_ignores)]
        result.update(status="compared", added=added, removed=removed, changed=changed)
        if key[2] == "failed_tasks":
            result["no_longer_observed"] = result.pop("removed")
            result["reason"] = "Tasks use a rolling completion-time window; missing tasks are not deletions."
        result["counts"] = {name: len(result.get(name, [])) for name in ("added", "removed", "changed", "no_longer_observed")}
    return sanitize(report)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare completed inventory runs with matching scopes.")
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Comparison JSON file")
    parser.add_argument("--ignore-field", action="append", default=[], help="Dotted field path or glob; repeatable")
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args(argv)
    try:
        destination = args.output.resolve()
        if any(destination.is_relative_to(source.resolve()) for source in (args.before, args.after)):
            raise RunError("Comparison output must be outside both input run directories.")
        report = compare_runs(args.before, args.after, args.ignore_field)
        write_json(args.output, report)
        if args.csv:
            rows = []
            for item in report["resources"]:
                for kind in ("added", "removed", "changed", "no_longer_observed"):
                    for change in item.get(kind, []):
                        rows.append({"target": item["target"], "component": item["component"], "resource": item["resource"],
                                     "change": kind, "identity": json.dumps(change["identity"], ensure_ascii=False)})
                if item["status"] == "skipped":
                    rows.append({"target": item["target"], "component": item["component"], "resource": item["resource"],
                                 "change": "skipped", "reason": item["reason"]})
            write_resource(args.output.parent, args.output.stem + "_changes", rows, {}, write_csv=True)
        print(f"Comparison: {args.output}")
        return 2 if report["status"] == "partial" else 0
    except (RunError, OSError):
        print("Comparison failed: check completed run files and output permissions.", file=sys.stderr)
        return 1
