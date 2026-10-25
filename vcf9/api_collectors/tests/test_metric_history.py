"""Offline historical query scope and sample-statistic tests. Author: Paul Bryant."""

import copy
import json
import unittest
from unittest.mock import Mock

from vcf_inventory import metric_history as history
from vcf_inventory.http_client import ApiError
from vcf_inventory.metric_history_report import build_metric_history_report


BEGIN = 1792800000000
END = BEGIN + 3600000


def target(two=False):
    windows = [{"label": "earlier", "begin": "2026-10-24T00:00:00Z", "end": "2026-10-24T01:00:00Z"}]
    if two:
        windows.append({"label": "later", "begin": "2026-10-24T01:00:00Z", "end": "2026-10-24T02:00:00Z"})
    return {"component": "vcf_operations", "resources": ["metric_history"], "resource_ids": ["resource"],
            "stat_keys": ["cpu|usage_average"], "metric_history": {"windows": windows, "rollup_type": "AVG",
            "interval_type": "MINUTES", "interval_quantifier": 5}}


def metadata(unit="PERCENT"):
    return [{"identifier": "resource", "resourceKey": {"name": "resource-name", "adapterKindKey": "VMWARE", "resourceKindKey": "VirtualMachine"}},
            {"resourceTypeAttributes": [{"key": "cpu|usage_average", "unit": unit}]}]


def payload(values=None, stamps=None, **changes):
    stat = {"statKey": {"key": "cpu|usage_average"}, "timestamps": stamps if stamps is not None else [BEGIN, BEGIN + 300000],
            "data": values if values is not None else [10, 20], "rollUpType": "AVG",
            "intervalUnit": {"intervalType": "MINUTES", "quantifier": 5}}
    stat.update(changes)
    return {"values": [{"resourceId": "resource", "stat-list": {"stat": [stat]}}]}


def client(replies, selected=None):
    result = Mock(target=selected or target())
    result.collection_metadata = {}
    result.get.side_effect = replies
    return result


def collected_run(selected=None, series=None, unit="PERCENT"):
    selected = selected or target()
    series = [payload()] if series is None else series
    transport = client(metadata(unit) + series, selected)
    records = history.collect_resource(transport, "metric_history")
    document = {"target": "operations", "component": "vcf_operations", "resource": "metric_history",
                "endpoint": "https://operations.example.test", "collected_at": "2026-10-24T02:00:00Z",
                "records": records, "collection": transport.collection_metadata["metric_history"]}
    return {"summary": {"status": "success"}, "resources": {("operations", "vcf_operations", "metric_history"): document}, "unavailable": {}}


def report_records(run):
    return build_metric_history_report(run)["records"]


class HistoryValidationTests(unittest.TestCase):
    def test_explicit_scope_and_millisecond_window(self):
        selected = target()
        history.validate_target(selected)
        request = history.probe_request(selected, "metric_history")
        self.assertEqual(request[:2], ("GET", "/suite-api/api/resources/stats"))
        self.assertEqual(request[2]["begin"], BEGIN)
        self.assertEqual(request[2]["end"], END)
        self.assertEqual(request[2]["resourceId"], ["resource"])
        self.assertEqual(request[2]["statKey"], ["cpu|usage_average"])
        self.assertEqual(request[2]["rollUpType"], "AVG")
        self.assertNotIn("latestMaxSamples", request[2])

    def test_missing_or_unbounded_scope_is_rejected(self):
        for field in ("resource_ids", "stat_keys", "metric_history"):
            selected = target()
            del selected[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                history.validate_target(selected)
        for changes in ({"rollup_type": "LATEST"}, {"rollup_type": []}, {"interval_type": "MONTHS"},
                        {"interval_quantifier": True}, {"windows": []}, {"extra": True}):
            selected = target()
            selected["metric_history"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                history.validate_target(selected)

    def test_requires_aware_positive_bounded_windows(self):
        for begin, end in (("2026-10-24T00:00:00", "2026-10-24T01:00:00Z"),
                           ("2026-10-24T01:00:00Z", "2026-10-24T00:00:00Z"),
                           ("2025-01-01T00:00:00Z", "2026-10-24T00:00:00Z"),
                           ("1900-01-01T00:00:00Z", "1900-01-01T01:00:00Z")):
            selected = target()
            selected["metric_history"]["windows"][0].update(begin=begin, end=end)
            with self.subTest(begin=begin), self.assertRaises(ValueError):
                history.validate_target(selected)

    def test_nominal_sample_and_series_budgets(self):
        selected = target()
        selected["metric_history"]["windows"][0]["end"] = "2026-10-25T00:00:00Z"
        selected["metric_history"].update(interval_type="SECONDS", interval_quantifier=1)
        with self.assertRaises(ValueError):
            history.validate_target(selected)
        selected = target(two=True)
        selected["resource_ids"] = ["r" + str(value) for value in range(501)]
        with self.assertRaises(ValueError):
            history.validate_target(selected)

    def test_unrelated_target_without_history_is_untouched(self):
        history.validate_target({"component": "vcenter"})
        self.assertFalse(history.supports("vcenter", "metric_history"))
        self.assertIsNone(history.probe_request({"component": "vcenter"}, "metric_history"))
        self.assertEqual(history.DEFAULT_RESOURCES, {})
        self.assertEqual(history.ALLOWED_OPERATIONS, set())


class HistoryCollectionTests(unittest.TestCase):
    def test_collects_units_and_selected_samples_without_extra_fields(self):
        transport = client(metadata() + [payload(password="secret", links=[{"href": "private"}])])
        rows = history.collect_resource(transport, "metric_history")
        self.assertEqual(rows[0]["unit"], "PERCENT")
        self.assertEqual(rows[0]["data"], [10, 20])
        self.assertEqual(transport.get.call_count, 3)
        self.assertEqual(transport.collection_metadata["metric_history"]["coverage"], "complete")
        self.assertNotIn("secret", json.dumps(rows))
        self.assertNotIn("private", json.dumps(rows))
        transport.request.assert_not_called()

    def test_budget_includes_resource_and_unit_metadata(self):
        transport = client(metadata() + [payload()])
        with self.assertRaises(ApiError):
            history.collect_resource(transport, "metric_history", max_pages=2)
        self.assertEqual(transport.get.call_count, 2)
        self.assertEqual(transport.collection_metadata["metric_history"]["coverage"], "incomplete")

    def test_missing_series_has_explicit_empty_samples(self):
        transport = client(metadata() + [{"values": []}])
        row = history.collect_resource(transport, "metric_history")[0]
        self.assertEqual(row["availability"], "no_samples_returned")
        self.assertEqual(row["timestamps"], [])
        self.assertEqual(row["data"], [])

    def test_optional_outer_values_and_resource_stat_list_may_be_omitted(self):
        for response in ({}, {"values": [{"resourceId": "resource"}]}, {"values": [{"stat-list": {}}]}):
            with self.subTest(response=response):
                transport = client(metadata() + [response])
                row = history.collect_resource(transport, "metric_history")[0]
                self.assertEqual(row["availability"], "no_samples_returned")
                self.assertEqual(row["timestamps"], [])
                self.assertEqual(transport.collection_metadata["metric_history"]["coverage"], "complete")

    def test_optional_numeric_data_may_be_omitted_for_an_empty_series(self):
        response = payload(values=[], stamps=[])
        del response["values"][0]["stat-list"]["stat"][0]["data"]
        row = history.collect_resource(client(metadata() + [response]), "metric_history")[0]
        self.assertEqual(row["data"], [])
        self.assertEqual(row["availability"], "no_samples_returned")

    def test_response_scope_and_sample_errors_fail_without_claiming_complete(self):
        invalid = [payload(stamps=[BEGIN, BEGIN]), payload(stamps=[BEGIN - 1, BEGIN]),
                   payload(values=[1]), payload(values=[1, float("nan")]), payload(values=[10**400, 20]), payload(rollUpType=[]),
                   payload(intervalUnit={"intervalType": "MINUTES", "quantifier": True}), payload(unit=10),
                   payload(intervalUnit={"intervalType": "UNKNOWN", "quantifier": 1}), payload(unit=""),
                   {"values": [], "cursor": "next"}, {"values": [] , "pageInfo": {"totalCount": 2}}]
        wrong_resource = payload()
        wrong_resource["values"][0]["resourceId"] = "unselected"
        invalid.append(wrong_resource)
        wrong_key = payload(statKey={"key": "other"})
        invalid.append(wrong_key)
        repeated = payload()
        repeated["values"][0]["stat-list"]["stat"].append(copy.deepcopy(repeated["values"][0]["stat-list"]["stat"][0]))
        invalid.append(repeated)
        for response in invalid:
            transport = client(metadata() + [response])
            with self.subTest(response=response), self.assertRaises(ApiError):
                history.collect_resource(transport, "metric_history")
            self.assertEqual(transport.collection_metadata["metric_history"]["coverage"], "incomplete")

    def test_sorts_paired_samples_and_keeps_requested_and_reported_semantics(self):
        transport = client(metadata() + [payload(values=[20, 10], stamps=[BEGIN + 300000, BEGIN], rollUpType="MAX")])
        row = history.collect_resource(transport, "metric_history")[0]
        self.assertEqual(row["timestamps"], [BEGIN, BEGIN + 300000])
        self.assertEqual(row["data"], [10, 20])
        self.assertEqual(row["requested_rollup_type"], "AVG")
        self.assertEqual(row["reported_rollup_type"], "MAX")

    def test_conflicting_units_fail(self):
        transport = client(metadata() + [payload(unit="MILLISECONDS")])
        with self.assertRaises(ApiError):
            history.collect_resource(transport, "metric_history")

    def test_count_rollup_does_not_reuse_the_source_metrics_unit(self):
        selected = target()
        selected["metric_history"]["rollup_type"] = "COUNT"
        transport = client(metadata() + [payload(rollUpType="COUNT")], selected)
        row = history.collect_resource(transport, "metric_history")[0]
        self.assertEqual(row["metric_unit"], "PERCENT")
        self.assertIsNone(row["unit"])

    def test_empty_attribute_unit_is_not_treated_as_measurement_evidence(self):
        with self.assertRaises(ApiError):
            history.collect_resource(client(metadata(unit="") + [payload()]), "metric_history")

    def test_metadata_is_cached_across_windows(self):
        later = payload(stamps=[END, END + 300000])
        transport = client(metadata() + [payload(), later], target(two=True))
        rows = history.collect_resource(transport, "metric_history")
        self.assertEqual(len(rows), 2)
        self.assertEqual(transport.get.call_count, 4)
        self.assertEqual(transport.get.call_args.kwargs["params"]["begin"], END)


class HistoryReportTests(unittest.TestCase):
    def test_native_metadata_types_are_checked_before_confirming_cadence(self):
        selected = target()
        selected["metric_history"]["interval_quantifier"] = 1
        saved = collected_run(selected, [payload(intervalUnit={"intervalType": "MINUTES", "quantifier": 1})])
        invalid = [
            {"reported_interval": {"intervalType": "MINUTES", "quantifier": True}},
            {"reported_interval": {"intervalType": "MINUTES", "quantifier": 1.0}},
            {"reported_interval": {"intervalType": "MINUTES", "quantifier": 0}},
            {"reported_interval": {"intervalType": "UNKNOWN", "quantifier": 1}},
            {"reported_interval": {"intervalType": "MINUTES", "quantifier": 1, "extra": True}},
            {"reported_interval": []}, {"reported_rollup_type": []}, {"reported_rollup_type": "UNKNOWN"},
            {"unit": ""}, {"unit": False}, {"metric_unit": "  "}, {"reported_series_unit": 1},
            {"requested_interval_quantifier": True}, {"unit": "MILLISECONDS"},
            {"reported_series_unit": "MILLISECONDS"}, {"data": [10**400, 20]},
            {"timestamps": [BEGIN + value for value in range(history.MAX_SAMPLES + 2)],
             "data": [1] * (history.MAX_SAMPLES + 2)},
        ]
        for changes in invalid:
            altered = copy.deepcopy(saved)
            next(iter(altered["resources"].values()))["records"][0].update(changes)
            with self.subTest(changes=changes):
                report = build_metric_history_report(altered)
                self.assertEqual(report["status"], "partial")
                self.assertEqual(report["records"], [])

    def test_optional_native_metadata_remains_unknown_when_absent(self):
        saved = collected_run()
        row = next(iter(saved["resources"].values()))["records"][0]
        for field in ("reported_rollup_type", "reported_interval", "unit", "metric_unit", "reported_series_unit"):
            row.pop(field, None)
        report = build_metric_history_report(saved)
        self.assertEqual(len(report["records"]), 1)
        self.assertEqual(report["status"], "partial")
        self.assertIsNone(report["records"][0]["nominal_expected_samples"])

    def test_count_sample_unit_must_be_unknown_and_metric_unit_is_preserved(self):
        selected = target()
        selected["metric_history"]["rollup_type"] = "COUNT"
        saved = collected_run(selected, [payload(rollUpType="COUNT")])
        report = build_metric_history_report(saved)
        self.assertIsNone(report["records"][0]["unit"])
        self.assertEqual(report["records"][0]["metric_unit"], "PERCENT")
        next(iter(saved["resources"].values()))["records"][0]["unit"] = "PERCENT"
        self.assertEqual(build_metric_history_report(saved)["records"], [])

    def test_saved_scope_reuses_collection_bounds_before_expected_set(self):
        saved = collected_run()
        original = next(iter(saved["resources"].values()))["collection"]
        invalid = [
            {"resource_ids": ["r" + str(value) for value in range(1001)]},
            {"resource_ids": ["r" + str(value) for value in range(501)], "stat_keys": ["one", "two"]},
            {"resource_ids": ["r" + str(value) for value in range(1000)],
             "windows": [{"label": "earlier", "begin_ms": BEGIN, "end_ms": BEGIN + 4 * 86400000}]},
            {"requested_interval_quantifier": True}, {"requested_interval_quantifier": 1000001},
            {"windows": [{"label": "earlier", "begin_ms": BEGIN, "end_ms": BEGIN + 367 * 86400000}]},
            {"windows": [{"label": "earlier", "begin_ms": 10**400, "end_ms": 10**400 + 1}]},
            {"windows": [{"label": "earlier", "begin_ms": BEGIN, "end_ms": BEGIN + 86400000}],
             "requested_interval_type": "SECONDS", "requested_interval_quantifier": 1},
        ]
        self.assertIs(history.validated_scope(original), original)
        for changes in invalid:
            altered = copy.deepcopy(saved)
            scope = next(iter(altered["resources"].values()))["collection"]
            scope.update(changes)
            with self.subTest(fields=sorted(changes)):
                self.assertIsNone(history.validated_scope(scope))
                report = build_metric_history_report(altered)
                self.assertEqual(report["status"], "partial")
                self.assertEqual(report["records"], [])

    def test_available_sample_statistics_and_nominal_coverage(self):
        report = build_metric_history_report(collected_run())
        row = report["records"][0]
        self.assertEqual(row["minimum_of_returned_samples"], 10)
        self.assertEqual(row["maximum_of_returned_samples"], 20)
        self.assertEqual(row["mean_of_returned_samples"], 15)
        self.assertEqual(row["p95_of_returned_samples"], 20)
        self.assertEqual(row["nominal_expected_samples"], 12)
        self.assertAlmostEqual(row["sample_coverage_percent_estimate"], 100 / 6)
        self.assertEqual(row["estimated_missing_interior_samples"], 0)
        self.assertFalse(row["boundary_coverage_known"])
        self.assertEqual(row["statistic_basis"], "returned_AVG_samples")

    def test_interior_gaps_and_irregular_cadence_are_distinct(self):
        report = build_metric_history_report(collected_run(series=[payload(stamps=[BEGIN, BEGIN + 900000])]))
        row = report["records"][0]
        self.assertEqual(row["estimated_missing_interior_samples"], 2)
        self.assertEqual(row["interior_gap_count"], 1)
        self.assertEqual(report["status"], "partial")
        row = report_records(collected_run(series=[payload(stamps=[BEGIN, BEGIN + 430000])]))[0]
        self.assertIsNone(row["estimated_missing_interior_samples"])
        self.assertIsNone(row["sample_coverage_percent_estimate"])

    def test_missing_rollup_or_unit_does_not_invent_semantics(self):
        response = payload()
        del response["values"][0]["stat-list"]["stat"][0]["rollUpType"]
        report = build_metric_history_report(collected_run(series=[response], unit=None))
        row = report["records"][0]
        self.assertIsNone(row["unit"])
        self.assertIsNone(row["nominal_expected_samples"])
        self.assertEqual(report["status"], "partial")

    def test_p95_nearest_rank(self):
        selected = target()
        selected["metric_history"].update(interval_type="SECONDS", interval_quantifier=1)
        row = report_records(collected_run(selected, [payload(values=list(range(1, 101)),
                                    stamps=[BEGIN + value * 1000 for value in range(100)],
                                    intervalUnit={"intervalType": "SECONDS", "quantifier": 1})]))[0]
        self.assertEqual(row["p95_of_returned_samples"], 95)

    def test_no_samples_are_unknown_not_zero(self):
        row = report_records(collected_run(series=[{"values": []}]))[0]
        self.assertEqual(row["sample_count"], 0)
        self.assertIsNone(row["mean_of_returned_samples"])
        self.assertIsNone(row["estimated_missing_interior_samples"])

    def test_compares_equal_nonoverlapping_windows_with_same_units_and_rollup(self):
        later = payload(values=[20, 40], stamps=[END, END + 300000])
        rows = report_records(collected_run(target(two=True), [payload(), later]))
        row = next(value for value in rows if value["window_label"] == "later")
        self.assertEqual(row["comparison_status"], "available_samples_only")
        self.assertEqual(row["mean_change"], 15)
        self.assertEqual(row["mean_change_percent"], 100)

    def test_comparison_requires_nonoverlapping_equal_windows(self):
        selected = target(two=True)
        selected["metric_history"]["windows"][1].update(begin="2026-10-24T00:30:00Z", end="2026-10-24T01:30:00Z")
        later = payload(values=[20, 40], stamps=[BEGIN + 1800000, BEGIN + 2100000])
        row = next(value for value in report_records(collected_run(selected, [payload(), later])) if value["window_label"] == "later")
        self.assertEqual(row["comparison_status"], "unknown")
        self.assertIsNone(row["mean_change"])

    def test_zero_mean_baseline_has_absolute_change_only(self):
        later = payload(values=[20, 40], stamps=[END, END + 300000])
        rows = report_records(collected_run(target(two=True), [payload(values=[0, 0]), later]))
        row = next(value for value in rows if value["window_label"] == "later")
        self.assertEqual(row["mean_change"], 30)
        self.assertIsNone(row["mean_change_percent"])

    def test_missing_and_ambiguous_saved_scope_is_partial(self):
        saved = collected_run()
        document = next(iter(saved["resources"].values()))
        document["records"].append(copy.deepcopy(document["records"][0]))
        report = build_metric_history_report(saved)
        self.assertEqual(report["records"], [])
        self.assertEqual(report["status"], "partial")
        document["collection"]["coverage"] = "incomplete"
        self.assertEqual(build_metric_history_report(saved)["records"], [])
        self.assertEqual(build_metric_history_report({"resources": {}, "unavailable": {}})["status"], "partial")

    def test_endpoint_boundary_is_explicitly_uncertain(self):
        row = report_records(collected_run(series=[payload(stamps=[BEGIN, END])]))[0]
        self.assertEqual(row["last_sample_ms"], END)
        self.assertFalse(row["boundary_coverage_known"])

    def test_finite_json_even_when_comparison_overflows(self):
        for magnitude in (1e308, 10**308):
            with self.subTest(number_type=type(magnitude).__name__):
                later = payload(values=[magnitude, magnitude], stamps=[END, END + 300000])
                report = build_metric_history_report(collected_run(target(two=True), [payload(values=[-magnitude, -magnitude]), later]))
                json.dumps(report, allow_nan=False)
                row = next(value for value in report["records"] if value["window_label"] == "later")
                self.assertEqual(row["comparison_status"], "unknown")
                self.assertIsNone(row["mean_change"])


if __name__ == "__main__":
    unittest.main()
