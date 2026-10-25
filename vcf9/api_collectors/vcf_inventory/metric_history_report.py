"""Historical sample summaries without inferred peaks or forecasts. Author: Paul Bryant."""

import math
from statistics import mean

from .metric_history import INTERVAL_SECONDS, INTERVAL_TYPES, MAX_SAMPLES, ROLLUPS, finite_number, validated_scope
from .report_support import documents


def _note(report, message, partial=False):
    if message not in report["limitations"]:
        report["limitations"].append(message)
    if partial:
        report["status"] = "partial"


def _number(value):
    return finite_number(value)


def _scope(document):
    return validated_scope(document.get("collection"))


def _valid(row, scope):
    if row.get("resource_id") not in scope["resource_ids"] or row.get("stat_key") not in scope["stat_keys"]:
        return False
    window = next((value for value in scope["windows"] if value["label"] == row.get("window_label")), None)
    if window is None or any(type(row.get(key)) is not int or row[key] != window[key] for key in ("begin_ms", "end_ms")):
        return False
    if any(row.get(key) != scope[key] for key in ("requested_rollup_type", "requested_interval_type", "requested_interval_quantifier")):
        return False
    if type(row.get("requested_interval_quantifier")) is not int:
        return False
    rollup, interval = row.get("reported_rollup_type"), row.get("reported_interval")
    if rollup is not None and (not isinstance(rollup, str) or rollup not in ROLLUPS | {"NONE", "LATEST"}):
        return False
    if interval is not None and (not isinstance(interval, dict) or set(interval) != {"intervalType", "quantifier"}
                                 or not isinstance(interval["intervalType"], str) or interval["intervalType"] not in INTERVAL_TYPES
                                 or type(interval["quantifier"]) is not int or interval["quantifier"] < 1):
        return False
    for field in ("unit", "metric_unit", "reported_series_unit"):
        unit = row.get(field)
        if unit is not None and (not isinstance(unit, str) or not unit.strip()):
            return False
    if (scope["requested_rollup_type"] == "COUNT" or rollup == "COUNT") and row.get("unit") is not None:
        return False
    if row.get("unit") is not None and row.get("metric_unit") is not None and row["unit"] != row["metric_unit"]:
        return False
    if (row.get("reported_series_unit") is not None and row.get("metric_unit") is not None
            and row["reported_series_unit"] != row["metric_unit"]):
        return False
    stamps, values = row.get("timestamps"), row.get("data")
    return (isinstance(stamps, list) and isinstance(values, list) and len(stamps) == len(values) and len(stamps) <= MAX_SAMPLES + 1
            and all(type(value) is int and window["begin_ms"] <= value <= window["end_ms"] for value in stamps)
            and len(set(stamps)) == len(stamps) and all(_number(value) for value in values))


def _summarize(row, scope, document, report):
    result = {key: row.get(key) for key in ("resource_id", "resource_name", "stat_key", "unit", "metric_unit", "window_label",
               "begin_ms", "end_ms", "requested_rollup_type", "requested_interval_type", "requested_interval_quantifier",
               "reported_rollup_type", "reported_interval")}
    result.update(target=document["target"], endpoint=document.get("endpoint"), sample_count=len(row["data"]),
                  summary_status="observed" if row["data"] else "no_samples_returned",
                  boundary_coverage_known=False, comparison_status="not_requested")
    requested_interval = {"intervalType": scope["requested_interval_type"], "quantifier": scope["requested_interval_quantifier"]}
    confirmed = row.get("reported_rollup_type") == scope["requested_rollup_type"] and row.get("reported_interval") == requested_interval
    result["sample_semantics"] = "confirmed_requested_rollup_and_interval" if confirmed else "unconfirmed_or_different_rollup_or_interval"
    if not confirmed:
        _note(report, "Some returned series omit or differ from requested rollup or interval metadata; cadence estimates and period comparisons remain unknown.", True)
    if not row.get("unit"):
        _note(report, "Some selected metrics have no exact measurement-unit metadata; their units and period comparisons remain unknown.", True)
    if not row["data"]:
        _note(report, "Some explicitly selected series returned no samples; absence is not a zero value or proof that the resource was idle.", True)
    pairs = sorted(zip(row["timestamps"], row["data"]))
    values = sorted(row["data"])
    result.update(first_sample_ms=pairs[0][0] if pairs else None, last_sample_ms=pairs[-1][0] if pairs else None,
                  minimum_of_returned_samples=values[0] if values else None,
                  maximum_of_returned_samples=values[-1] if values else None,
                  mean_of_returned_samples=mean(values) if values else None,
                  p95_of_returned_samples=values[max(0, math.ceil(len(values) * 0.95) - 1)] if values else None,
                  nominal_expected_samples=None, sample_coverage_percent_estimate=None,
                  estimated_missing_interior_samples=None, interior_gap_count=None)
    if confirmed:
        interval_ms = INTERVAL_SECONDS[scope["requested_interval_type"]] * scope["requested_interval_quantifier"] * 1000
        expected = math.ceil((row["end_ms"] - row["begin_ms"]) / interval_ms)
        result["nominal_expected_samples"] = expected
        result["sample_coverage_percent_estimate"] = min(100, len(values) * 100 / expected)
        missing, gaps, irregular = 0, 0, False
        tolerance = min(1000, interval_ms * 0.01)
        for left, right in zip(pairs, pairs[1:]):
            elapsed = right[0] - left[0]
            steps = round(elapsed / interval_ms)
            if steps < 1 or abs(elapsed - steps * interval_ms) > tolerance:
                irregular = True
            elif steps > 1:
                missing += steps - 1
                gaps += 1
        if irregular:
            result["sample_coverage_percent_estimate"] = None
            _note(report, "Some timestamps do not follow the returned fixed cadence; their interior missing-sample counts and coverage estimates remain unknown.", True)
        else:
            result.update(estimated_missing_interior_samples=missing, interior_gap_count=gaps)
            if gaps:
                _note(report, "Fixed-cadence timestamp gaps are present; summaries describe available samples and may not represent the whole window.", True)
    result["statistic_basis"] = "returned_" + str(row.get("reported_rollup_type") or "unconfirmed") + "_samples"
    return result


def _compare(records, scope, report):
    if len(scope["windows"]) != 2:
        return
    earlier, later = sorted(scope["windows"], key=lambda value: value["begin_ms"])
    comparable = (earlier["end_ms"] <= later["begin_ms"]
                  and earlier["end_ms"] - earlier["begin_ms"] == later["end_ms"] - later["begin_ms"])
    index = {(row["resource_id"], row["stat_key"], row["window_label"]): row for row in records}
    for row in records:
        if row["window_label"] != later["label"]:
            continue
        previous = index.get((row["resource_id"], row["stat_key"], earlier["label"]))
        row.update(comparison_status="unknown", compared_window=earlier["label"], mean_change=None, mean_change_percent=None)
        if (not comparable or previous is None or not row["unit"] or row["unit"] != previous["unit"]
                or any(value["sample_semantics"] != "confirmed_requested_rollup_and_interval"
                       or not value["sample_count"] for value in (row, previous))):
            _note(report, "A period comparison requires equal-duration nonoverlapping windows, known equal units, confirmed matching rollup and interval metadata, and samples in both windows.")
            continue
        change = row["mean_of_returned_samples"] - previous["mean_of_returned_samples"]
        if not finite_number(change):
            _note(report, "An observed period change exceeds finite numeric range; its comparison remains unknown.", True)
            continue
        row["mean_change"] = change
        baseline = previous["mean_of_returned_samples"]
        percent = change / abs(baseline) * 100 if baseline != 0 else None
        row["mean_change_percent"] = percent if percent is not None and math.isfinite(percent) else None
        row["comparison_status"] = "available_samples_only"
        if baseline == 0:
            _note(report, "A zero baseline mean has no defined percentage change; the absolute change remains available.")


def build_metric_history_report(run):
    """Summarize saved samples and compare compatible windows within each saved scope."""
    report = {"author": "Paul Bryant", "schema_version": "1.0", "report_type": "metric_history",
              "status": "success", "records": [], "scopes": [], "limitations": [
                  "Statistics summarize returned samples using the reported rollup; a maximum of AVG samples is not a raw instantaneous peak.",
                  "P95 uses the nearest-rank method across returned samples. Means and percentiles are not time-weighted and do not reconstruct underlying raw samples.",
                  "Coverage uses a nominal fixed interval count, with unverified bucket alignment and endpoint inclusion. It is an estimate, not proof of full retention or boundary coverage.",
                  "Period changes compare available sample means, can be affected by missing samples, and are not forecasts or capacity guarantees."]}
    selected = documents(run, "vcf_operations", "metric_history")
    if not selected:
        _note(report, "No complete saved historical metric observations are available.", True)
    if any(key[1:] == ("vcf_operations", "metric_history") for key in run.get("unavailable", {})):
        _note(report, "One or more requested historical observations are unavailable or incomplete.", True)
    for document in selected:
        scope = _scope(document)
        report["scopes"].append({"target": document["target"], "endpoint": document.get("endpoint"),
                                 "collected_at": document.get("collected_at"), "scope": scope})
        if scope is None:
            _note(report, "A saved historical observation lacks complete explicit scope evidence; its records are not summarized.", True)
            continue
        expected = {(identity, key, window["label"]) for identity in scope["resource_ids"]
                    for key in scope["stat_keys"] for window in scope["windows"]}
        seen, valid, ambiguous = set(), {}, set()
        for row in document["records"]:
            identity = (row.get("resource_id"), row.get("stat_key"), row.get("window_label"))
            if not _valid(row, scope):
                _note(report, "Malformed or out-of-scope saved historical records were excluded.", True)
            elif identity in seen:
                valid.pop(identity, None)
                ambiguous.add(identity)
                _note(report, "Duplicate saved historical series are ambiguous and were excluded.", True)
            else:
                seen.add(identity)
                valid[identity] = row
        if set(valid) != expected or ambiguous:
            _note(report, "The saved historical scope is missing one or more unambiguous selected series.", True)
        if sum(len(row["data"]) for row in valid.values()) > 1000000:
            _note(report, "The saved historical observation exceeds the returned-sample budget and was excluded.", True)
            continue
        records = [_summarize(row, scope, document, report) for _, row in sorted(valid.items())]
        _compare(records, scope, report)
        report["records"].extend(records)
    return report
