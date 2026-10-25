"""Saved-run reporting and shared integration tests. Author: Paul Bryant."""

import io
import json
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vcf_inventory import reporting
from vcf_inventory.config import load_config
from vcf_inventory.preflight import run_preflight
from vcf_inventory.protection_report import validate_policy
from vcf_inventory.report_support import parse_time


class ReportCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.run.mkdir()
        summary = {"author": "Paul Bryant", "status": "success", "completed_at": "2020-01-01T01:00:00Z", "targets": []}
        targets = {}
        for target, component, resource, details in [
            ("vc", "vcenter", "vms", {}), ("vc", "vcenter", "backup_jobs", {}), ("vc", "vcenter", "backup_schedules", {}),
            ("vc", "vcenter", "authorization_roles", {}), ("vc", "vcenter", "authorization_permissions", {}),
            ("nsx", "nsx", "backup_history", {}),
            ("nsx", "nsx", "rule_statistics", {"domain_id": "default", "enforcement_point_path": "/infra/sites/default/enforcement-points/default",
                                               "policy_ids": ["policy"], "resolved_rule_ids": {"policy": []}}),
            ("hcx", "hcx", "migrations", {"include_archived": True}),
            ("automation", "vcf_automation", "deployment_requests", {"api_family": "all_apps", "queried_deployment_ids": ["deployment"]}),
            ("vsan", "vsan", "health_summary", {}), ("vsan", "vsan", "space_usage", {}),
        ]:
            endpoint = "https://" + target + ".example.com"
            if target not in targets:
                targets[target] = {"name": target, "component": component, "endpoint": endpoint, "status": "success", "resources": []}
                summary["targets"].append(targets[target])
            filename = target + "_" + resource + ".json"
            document = {"author": "Paul Bryant", "target": target, "component": component, "resource": resource,
                        "endpoint": endpoint, "collected_at": "2020-01-01T00:00:00Z", "record_count": 0, "records": [],
                        "collection": dict(details, coverage="complete")}
            (self.run / filename).write_text(json.dumps(document), encoding="utf-8")
            targets[target]["resources"].append({"resource": resource, "status": "success", "record_count": 0, "file": filename})
        (self.run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        self.policy = self.root / "policy.json"
        self.policy.write_text(json.dumps({"author": "Paul Bryant", "requirements": [{"vcenter_target": "vc", "vm_id": "vm-1",
            "replication": {"target": "vr", "pairing_id": "pair", "source_vc_id": "vc-id", "vm_id": "native-vm"}}]}), encoding="utf-8")

    def test_all_report_commands_write_actual_json_and_csv_without_network(self):
        with patch("vcf_inventory.http_client.build_opener") as opener, patch("sys.stdout", new_callable=io.StringIO):
            for report_type in reporting.REPORTS:
                with self.subTest(report=report_type):
                    output = self.root / "reports" / (report_type + ".json")
                    args = ["--run", str(self.run), "--output", str(output), "--csv"]
                    if report_type == "protection_gaps":
                        args += ["--policy", str(self.policy)]
                    if report_type == "access_permissions":
                        args += ["--baseline", str(Path(__file__).resolve().parents[1] / "examples" / "access-baseline.example.json")]
                    self.assertIn(reporting.main(args, report_type=report_type), (0, 2))
                    document = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(document["author"], "Paul Bryant")
                    self.assertEqual(document["report_type"], report_type)
                    self.assertEqual(document["record_count"], len(document["records"]))
                    self.assertNotIn(str(self.run), json.dumps(document))
                    self.assertTrue(output.with_name(output.stem + "_records.csv").is_file())
                    sidecar = json.loads(output.with_name(output.stem + "_records.json").read_text(encoding="utf-8"))
                    self.assertEqual(sidecar["author"], "Paul Bryant")
        opener.assert_not_called()

    def test_reports_cannot_overwrite_runs_or_policy(self):
        before = self.policy.read_bytes()
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(reporting.main(["--run", str(self.run), "--output", str(self.run / "summary.json")], "backup_freshness"), 1)
            self.assertEqual(reporting.main(["--run", str(self.run), "--output", str(self.policy), "--policy", str(self.policy)], "protection_gaps"), 1)
        self.assertEqual(self.policy.read_bytes(), before)

    def test_unrelated_options_and_invalid_thresholds_are_not_silently_ignored(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            for options in (["--max-age-hours", "0"], ["--max-age-hours", "nan"], ["--stalled-minutes", "30"]):
                self.assertEqual(reporting.main(["--run", str(self.run), "--output", str(self.root / "bad.json"), *options], "backup_freshness"), 1)

    def test_all_report_wrappers_pass_the_expected_type(self):
        toolkit = Path(__file__).resolve().parents[1]
        for report_type in reporting.REPORTS:
            with self.subTest(report=report_type), patch.object(reporting, "main", return_value=0) as main:
                with self.assertRaises(SystemExit):
                    runpy.run_path(str(toolkit / ("report_" + report_type + ".py")), run_name="__main__")
                main.assert_called_once_with(report_type=report_type)

    def test_all_collection_examples_and_protection_policy_validate_offline(self):
        toolkit = Path(__file__).resolve().parents[1]
        with patch("vcf_inventory.http_client.build_opener") as opener:
            for file in (toolkit / "examples").glob("*.json"):
                content = json.loads(file.read_text(encoding="utf-8-sig"))
                if "targets" in content and all("component" in row for row in content["targets"]):
                    load_config(file)
                elif "targets" in content:
                    from vcf_inventory.management_services_report import validate_baseline
                    validate_baseline(content)
                if "requirements" in content:
                    validate_policy(content)
        opener.assert_not_called()

    def test_preflight_permissions_uses_list_post_and_not_create_or_get(self):
        target = {"name": "vc", "component": "vcenter", "url": "https://vc.example.com", "resources": ["authorization_permissions"]}
        client = SimpleNamespace(authenticate=Mock(), close=Mock(), request=Mock(side_effect=[{"version": "9.0"}, {"items": []}]))
        result = run_preflight([target], {}, client_factory=Mock(return_value=client))
        self.assertEqual(result["status"], "success")
        self.assertEqual(client.request.call_args.args, ("POST", "/api/vcenter/authorization/permissions"))
        self.assertEqual(client.request.call_args.kwargs, {"params": {"action": "list"}, "body": {"iterate": {"page_size": 1}}})
        client.close.assert_called_once()

    def test_time_helpers_require_explicit_units_and_timezones(self):
        self.assertIsNone(parse_time(1600000000000))
        self.assertIsNone(parse_time("2020-01-01T00:00:00"))
        self.assertIsNotNone(parse_time(1600000000000, "milliseconds"))
