"""Run comparison and safe loading tests. Author: Paul Bryant."""

import json
import tempfile
import unittest
from pathlib import Path

from vcf_inventory.compare import compare_runs, main
from vcf_inventory.runs import RunError, identity_for, load_run


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_file(self, name, records, resource="vms", component="vcenter", **scope):
        path = self.root / name
        path.mkdir()
        document = dict(target="test", component=component, resource=resource, endpoint="https://test.example.com",
                        record_count=len(records), records=records, **scope)
        (path / "resource.json").write_text(json.dumps(document), encoding="utf-8")
        summary = {"status": "success", "completed_at": name, "targets": [{"name": "test", "component": component,
                   "endpoint": document["endpoint"], "resources": [{"resource": resource, "status": "success",
                   "record_count": len(records), "file": "resource.json"}]}]}
        (path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return path

    def change_summary(self, path, function):
        file = path / "summary.json"
        value = json.loads(file.read_text())
        function(value)
        file.write_text(json.dumps(value), encoding="utf-8")

    def test_added_removed_and_changed_use_ids(self):
        before = self.run_file("before", [{"vm": "1", "name": "old"}, {"vm": "2"}])
        after = self.run_file("after", [{"vm": "1", "name": "new"}, {"vm": "3"}])
        result = compare_runs(before, after)["resources"][0]
        self.assertEqual(result["counts"], {"added": 1, "removed": 1, "changed": 1, "no_longer_observed": 0})

    def test_missing_or_failed_resource_never_means_removed(self):
        before = self.run_file("before", [{"vm": "1"}])
        after = self.run_file("after", [])
        self.change_summary(after, lambda s: (s.update(status="incomplete"), s["targets"][0]["resources"][0].update(status="error")))
        report = compare_runs(before, after)
        self.assertEqual(report["status"], "partial")
        self.assertNotIn("removed", report["resources"][0])

    def test_changed_scope_skips_resource(self):
        before = self.run_file("before", [], scope_filters={"hosts": ["h1"]})
        after = self.run_file("after", [], scope_filters={"hosts": ["h2"]})
        self.assertEqual(compare_runs(before, after)["resources"][0]["status"], "skipped")

    def test_running_run_rejected(self):
        path = self.run_file("running", [])
        self.change_summary(path, lambda s: s.update(status="running"))
        with self.assertRaises(RunError):
            load_run(path)

    def test_escape_rejected_even_when_destination_exists(self):
        path = self.run_file("escape", [])
        (self.root / "other.json").write_text("{}")
        self.change_summary(path, lambda s: s["targets"][0]["resources"][0].update(file="../other.json"))
        with self.assertRaises(RunError):
            load_run(path)

    def test_count_mismatch_rejected(self):
        path = self.run_file("bad-count", [])
        self.change_summary(path, lambda s: s["targets"][0]["resources"][0].update(record_count=1))
        with self.assertRaises(RunError):
            load_run(path)

    def test_boolean_summary_count_is_not_accepted_as_integer_one(self):
        path = self.run_file("boolean-count", [{"vm": "1"}])
        self.change_summary(path, lambda s: s["targets"][0]["resources"][0].update(record_count=True))
        with self.assertRaises(RunError):
            load_run(path)

    def test_nonstring_or_blank_completion_metadata_is_rejected(self):
        for index, completion in enumerate((["finished"], {"status": "finished"}, " ")):
            path = self.run_file("completion" + str(index), [])
            self.change_summary(path, lambda s: s.update(completed_at=completion))
            with self.subTest(completion=completion), self.assertRaises(RunError):
                load_run(path)

    def test_nonfinite_numbers_and_duplicate_json_keys_are_rejected(self):
        for index, invalid in enumerate(("NaN", "Infinity", "-Infinity")):
            path = self.run_file("nonfinite" + str(index), [{"vm": "1"}])
            document = path / "resource.json"
            document.write_text(document.read_text().replace('"vm": "1"', '"vm": "1", "value": ' + invalid), encoding="utf-8")
            with self.subTest(invalid=invalid), self.assertRaises(RunError):
                load_run(path)
        path = self.run_file("duplicate-key", [{"vm": "1"}])
        document = path / "resource.json"
        document.write_text(document.read_text().replace('"vm": "1"', '"vm": "1", "vm": "2"'), encoding="utf-8")
        with self.assertRaises(RunError):
            load_run(path)

    def test_duplicate_and_missing_record_ids_skipped(self):
        for index, records in enumerate(([{"vm": "1"}, {"vm": "1"}], [{"name": "same"}])):
            before = self.run_file("before" + str(index), records)
            after = self.run_file("after" + str(index), records)
            self.assertEqual(compare_runs(before, after)["resources"][0]["status"], "skipped")

    def test_ignore_dotted_path(self):
        before = self.run_file("before", [{"vm": "1", "detail": {"lastSeen": 1}, "links": [1]}])
        after = self.run_file("after", [{"vm": "1", "detail": {"lastSeen": 2}, "links": [2]}])
        self.assertEqual(compare_runs(before, after, ["detail.lastSeen"])["resources"][0]["counts"]["changed"], 0)

    def test_rolling_task_window_is_not_deletion(self):
        before = self.run_file("before", [{"id": "1"}, {"id": "2", "tasksCompletedAfterEpochMs": 1}], "failed_tasks", "sddc_manager", task_days=30)
        after = self.run_file("after", [{"id": "2", "tasksCompletedAfterEpochMs": 2}], "failed_tasks", "sddc_manager", task_days=30)
        result = compare_runs(before, after)["resources"][0]
        self.assertNotIn("removed", result)
        self.assertEqual(len(result["no_longer_observed"]), 1)
        self.assertFalse(result["changed"])

    def test_imported_records_are_redacted_before_returning_comparison(self):
        before = self.run_file("before", [{"vm": "1", "password": "old-private-value"}])
        after = self.run_file("after", [{"vm": "1", "password": "new-private-value"}, {"vm": "2", "credentials": {"secret": "added-private-value"}}])
        report = compare_runs(before, after)
        rendered = json.dumps(report)
        self.assertNotIn("old-private-value", rendered)
        self.assertNotIn("new-private-value", rendered)
        self.assertNotIn("added-private-value", rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_partition_incomplete_skipped(self):
        path = self.run_file("incomplete", [], collection={"coverage": "incomplete"})
        run = load_run(path)
        self.assertFalse(run["resources"])
        self.assertEqual(len(run["unavailable"]), 1)

    def test_changed_resolved_certificate_domain_scope_does_not_imply_removals(self):
        record = {"domain_id": "d1", "resourceType": "VCENTER", "resourceName": "vc", "issuedTo": "vc.example.test"}
        before = self.run_file("before", [record], "certificates", "sddc_manager",
                               collection={"coverage": "complete", "queried_domain_ids": ["d1", "d2"]})
        after = self.run_file("after", [], "certificates", "sddc_manager",
                              collection={"coverage": "complete", "queried_domain_ids": ["d2"]})
        result = compare_runs(before, after)["resources"][0]
        self.assertEqual(result["status"], "skipped")
        self.assertNotIn("removed", result)

    def test_resolved_certificate_domain_order_is_not_a_scope_change(self):
        scope = {"coverage": "complete", "queried_domain_ids": ["d1", "d2"]}
        before = self.run_file("before", [], "certificates", "sddc_manager", collection=scope)
        after = self.run_file("after", [], "certificates", "sddc_manager",
                              collection={"coverage": "complete", "queried_domain_ids": ["d2", "d1"]})
        self.assertEqual(compare_runs(before, after)["resources"][0]["status"], "compared")

    def test_missing_resolved_certificate_scope_is_not_assumed_complete(self):
        before = self.run_file("before", [], "certificates", "sddc_manager")
        after = self.run_file("after", [], "certificates", "sddc_manager")
        self.assertEqual(compare_runs(before, after)["resources"][0]["status"], "skipped")

    def test_composite_scoped_ids(self):
        a = identity_for("nsx", "security_rules", {"id": "1", "domain_id": "d", "policy_id": "a"})
        b = identity_for("nsx", "security_rules", {"id": "1", "domain_id": "d", "policy_id": "b"})
        self.assertNotEqual(a, b)
        self.assertIsNotNone(identity_for("vcf_fleet", "component_statuses", {"component_id": "1"}))

    def test_cli_writes_inspectable_report_and_csv(self):
        before = self.run_file("before", [{"vm": "1"}])
        after = self.run_file("after", [{"vm": "2"}])
        output = self.root / "report.json"
        self.assertEqual(main(["--before", str(before), "--after", str(after), "--output", str(output), "--csv"]), 0)
        self.assertEqual(json.loads(output.read_text())["author"], "Paul Bryant")
        self.assertTrue((self.root / "report_changes.csv").is_file())

    def test_backup_history_absence_is_not_an_infrastructure_removal(self):
        before = self.run_file("before", [{"id": "backup-1"}], "backup_jobs", "vcenter")
        after = self.run_file("after", [], "backup_jobs", "vcenter")
        result = compare_runs(before, after)["resources"][0]
        self.assertNotIn("removed", result)
        self.assertEqual(len(result["no_longer_observed"]), 1)

    def test_changed_resolved_recovery_scope_does_not_report_removals(self):
        before = self.run_file("before", [{"id": "vm", "pairing_id": "p", "group_id": "g"}], "group_vms", "live_site_recovery",
                               collection={"coverage": "complete", "queried_pairing_ids": ["p"], "queried_group_ids": ["g"]})
        after = self.run_file("after", [], "group_vms", "live_site_recovery",
                              collection={"coverage": "complete", "queried_pairing_ids": ["p"], "queried_group_ids": ["other"]})
        result = compare_runs(before, after)["resources"][0]
        self.assertEqual(result["status"], "skipped")
        self.assertNotIn("removed", result)

    def test_rule_statistics_ids_include_native_backend_context(self):
        left = {"domain_id": "d", "policy_id": "p", "rule_id": "r", "enforcement_point": "ep", "lr_path": "one"}
        right = dict(left, lr_path="two")
        self.assertNotEqual(identity_for("nsx", "rule_statistics", left), identity_for("nsx", "rule_statistics", right))

    def test_cli_cannot_overwrite_files_in_either_input_run(self):
        before = self.run_file("before", [{"vm": "1"}])
        after = self.run_file("after", [{"vm": "2"}])
        original_before = (before / "summary.json").read_bytes()
        original_after = (after / "resource.json").read_bytes()
        for output in (before / "summary.json", after / "resource.json", after / "new-report.json"):
            with self.subTest(output=output):
                self.assertEqual(main(["--before", str(before), "--after", str(after), "--output", str(output)]), 1)
        self.assertEqual((before / "summary.json").read_bytes(), original_before)
        self.assertEqual((after / "resource.json").read_bytes(), original_after)
        self.assertFalse((after / "new-report.json").exists())
