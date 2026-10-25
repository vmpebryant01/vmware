"""Shared collection and analysis integration tests. Author: Paul Bryant."""

import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from vcf_inventory import cli, operational
from vcf_inventory.collectors import collect_resource, resources_for
from vcf_inventory.config import ConfigError, load_config
from vcf_inventory.http_client import ApiError
from vcf_inventory.products import operations
from vcf_inventory.runs import load_run


class SharedToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def config(self, targets):
        path = self.root / "config.json"
        path.write_text(json.dumps({"author": "Paul Bryant", "targets": targets}), encoding="utf-8")
        return path

    def test_saved_examples_validate_without_reading_credentials(self):
        toolkit = Path(__file__).resolve().parents[1]
        with patch("vcf_inventory.http_client.build_opener") as opener:
            for file in [toolkit / "config.example.json", *sorted((toolkit / "examples").glob("*.json"))]:
                # Policy and baseline files are consumed separately from collection configuration.
                content = json.loads(file.read_text(encoding="utf-8-sig"))
                if "targets" in content and all("component" in target for target in content["targets"]):
                    with self.subTest(file=file.name):
                        load_config(file)
        opener.assert_not_called()

    def test_fleet_has_its_own_module_and_keeps_all_default_resources(self):
        target = {"name": "fleet", "component": "vcf_fleet", "url": "https://fleet.example.com", "token_env": "FLEET_TOKEN"}
        parsed = load_config(self.config([target]))["targets"][0]
        self.assertEqual(resources_for(parsed), ["components", "component_nodes", "component_statuses"])
        client = Mock(target=parsed)
        with patch("vcf_inventory.products.fleet.collect_resource", return_value=[]) as collect:
            self.assertEqual(collect_resource(client, "components"), [])
        collect.assert_called_once()

    def test_operational_catalog_uses_shared_dispatch_before_product_handler(self):
        target = {"name": "catalog", "component": "vcf_automation", "url": "https://automation.example.com",
                  "token_env": "TOKEN", "api_family": "all_apps", "resources": ["catalog_items"]}
        parsed = load_config(self.config([target]))["targets"][0]
        client = Mock(target=parsed)
        with patch.object(operational, "collect_resource", return_value=[]) as collect:
            collect_resource(client, "catalog_items", page_size=10, max_pages=2)
        collect.assert_called_once_with(client, "catalog_items", page_size=10, max_pages=2)

    def test_fleet_does_not_accept_unused_password_credentials(self):
        with self.assertRaises(ConfigError):
            load_config(self.config([{"name": "fleet", "component": "vcf_fleet", "url": "https://fleet.example.com",
                                      "token_env": "TOKEN", "username_env": "USER", "password_env": "PASSWORD"}]))

    def test_cli_preserves_partition_evidence_in_document_and_summary(self):
        target = {"name": "vc", "component": "vcenter", "url": "https://vc.example.com",
                  "username_env": "USER", "password_env": "PASSWORD", "resources": ["vms"]}
        client = Mock()
        evidence = {"coverage": "complete", "strategy": "partitioned", "request_count": 5}
        client.collection_metadata = {"vms": evidence}
        with patch.object(cli, "HttpClient", return_value=client), patch.object(cli, "collect_resource", return_value=[{"vm": "1"}]), \
                patch("sys.stdout", new_callable=io.StringIO):
            status = cli.main(["--config", str(self.config([target])), "--output", str(self.root / "runs")])
        self.assertEqual(status, 0)
        run = load_run(next((self.root / "runs").iterdir()))
        self.assertEqual(run["resources"][("vc", "vcenter", "vms")]["collection"], evidence)
        self.assertEqual(run["summary"]["targets"][0]["resources"][0]["collection"], evidence)
        client.close.assert_called_once()

    def test_failed_partition_records_missing_coverage_without_inventory_export(self):
        target = {"name": "vc", "component": "vcenter", "url": "https://vc.example.com",
                  "username_env": "USER", "password_env": "PASSWORD", "resources": ["vms"]}
        client = Mock()
        client.collection_metadata = {"vms": {"coverage": "incomplete", "missing_coverage": [{"reason": "budget"}]}}
        with patch.object(cli, "HttpClient", return_value=client), patch.object(cli, "collect_resource", side_effect=ApiError("Coverage incomplete.")), \
                patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
            status = cli.main(["--config", str(self.config([target])), "--output", str(self.root / "runs")])
        self.assertEqual(status, 2)
        directory = next((self.root / "runs").iterdir())
        run = load_run(directory)
        self.assertFalse(run["resources"])
        self.assertFalse((directory / "vc" / "vms.json").exists())
        self.assertEqual(run["summary"]["targets"][0]["resources"][0]["collection"]["coverage"], "incomplete")

    def test_empty_failed_tasks_keep_exact_window_in_saved_inventory_and_summary(self):
        target = {"name": "sddc", "component": "sddc_manager", "url": "https://sddc.example.com",
                  "username_env": "USER", "password_env": "PASSWORD", "resources": ["failed_tasks"], "task_days": 7}
        client = Mock(target=target, collection_metadata={})
        client.get.return_value = {"elements": [], "pageMetadata": {"pageNumber": 0, "totalElements": 0, "totalPages": 0}}
        now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        expected_cutoff = int((now - timedelta(days=7)).timestamp() * 1000)
        with patch.object(cli, "HttpClient", return_value=client), patch.object(operational, "_utc_now", return_value=now), \
                patch("sys.stdout", new_callable=io.StringIO):
            status = cli.main(["--config", str(self.config([target])), "--output", str(self.root / "task-runs")])
        self.assertEqual(status, 0)
        directory = next((self.root / "task-runs").iterdir())
        document = json.loads((directory / "sddc" / "failed_tasks.json").read_text())
        summary = json.loads((directory / "summary.json").read_text())
        self.assertEqual(document["records"], [])
        details = document["collection"]
        self.assertEqual(details["coverage"], "complete")
        self.assertEqual(details["completed_after_epoch_ms"], expected_cutoff)
        self.assertEqual(details["query_filters"], {"completedAfter": expected_cutoff})
        self.assertEqual(details["record_count"], 0)
        self.assertEqual(summary["targets"][0]["resources"][0]["collection"], details)

    def test_empty_certificates_keep_resolved_domain_scope_in_saved_inventory(self):
        target = {"name": "sddc", "component": "sddc_manager", "url": "https://sddc.example.com",
                  "username_env": "USER", "password_env": "PASSWORD", "resources": ["certificates"]}
        client = Mock(target=target, collection_metadata={})
        client.get.side_effect = [
            {"elements": [{"id": "domain-1"}, {"id": "domain-2"}],
             "pageMetadata": {"pageNumber": 0, "totalElements": 2, "totalPages": 1}},
            {"elements": [], "pageMetadata": {"pageNumber": 0, "totalElements": 0, "totalPages": 0}},
            {"elements": [], "pageMetadata": {"pageNumber": 0, "totalElements": 0, "totalPages": 0}},
        ]
        with patch.object(cli, "HttpClient", return_value=client), patch("sys.stdout", new_callable=io.StringIO):
            status = cli.main(["--config", str(self.config([target])), "--output", str(self.root / "certificate-runs")])
        self.assertEqual(status, 0)
        directory = next((self.root / "certificate-runs").iterdir())
        document = json.loads((directory / "sddc" / "certificates.json").read_text())
        self.assertEqual(document["records"], [])
        self.assertEqual(document["collection"]["queried_domain_ids"], ["domain-1", "domain-2"])
        self.assertEqual(document["collection"]["strategy"], "discovered_domains")
        self.assertEqual(document["collection"]["coverage"], "complete")

    def test_operational_query_errors_keep_coverage_incomplete(self):
        for resource in ("failed_tasks", "certificates"):
            target = {"component": "sddc_manager", "resources": [resource], "domain_ids": ["domain-1"]}
            client = Mock(target=target, collection_metadata={})
            client.get.side_effect = ApiError("Forbidden.", status=403)
            with self.subTest(resource=resource), self.assertRaises(ApiError):
                collect_resource(client, resource)
            details = client.collection_metadata[resource]
            self.assertEqual(details["coverage"], "incomplete")
            if resource == "certificates":
                self.assertEqual(details["queried_domain_ids"], ["domain-1"])
            else:
                self.assertIsInstance(details["completed_after_epoch_ms"], int)

    def metric_client(self, reported_unit, metadata_unit="percent", empty=False):
        target = {"component": "vcf_operations", "resources": ["latest_metrics"],
                  "resource_ids": ["resource-1"], "stat_keys": ["cpu|usage_average"]}
        attributes = [] if metadata_unit is None else [{"key": "cpu|usage_average", "unit": metadata_unit}]
        series = {"statKey": {"key": "cpu|usage_average"}, "unit": reported_unit,
                  "timestamps": [] if empty else [1000], "data": [] if empty else [25.0]}
        client = Mock(target=target)
        client.get.side_effect = [
            {"identifier": "resource-1", "resourceKey": {"name": "vm-1", "adapterKindKey": "VMWARE", "resourceKindKey": "VirtualMachine"}},
            {"resourceTypeAttributes": attributes},
            {"values": [{"resourceId": "resource-1", "stat-list": {"stat": [series]}}]},
        ]
        return client

    def test_empty_returned_metric_series_is_explicitly_unavailable(self):
        rows = operations.collect_resource(self.metric_client("percent", empty=True), "latest_metrics")
        self.assertEqual(rows[0]["timestamps"], [])
        self.assertEqual(rows[0]["data"], [])
        self.assertEqual(rows[0]["availability"], "no_samples_returned")
        self.assertEqual(rows[0]["unit"], "percent")

    def test_undocumented_series_unit_does_not_replace_missing_attribute_unit(self):
        row = operations.collect_resource(self.metric_client("percent", metadata_unit=None), "latest_metrics")[0]
        self.assertIsNone(row["unit"])
        self.assertEqual(row["reported_series_unit"], "percent")

    def test_conflicting_series_and_documented_attribute_units_fail(self):
        with self.assertRaisesRegex(ApiError, "conflicting"):
            operations.collect_resource(self.metric_client("kilobytes", metadata_unit="percent"), "latest_metrics")

    def test_preflight_cli_writes_report_without_collecting(self):
        target = {"name": "nsx", "component": "nsx", "url": "https://nsx.example.com",
                  "username_env": "USER", "password_env": "PASSWORD", "resources": ["segments"]}
        report = {"author": "Paul Bryant", "status": "partial", "targets": []}
        with patch("vcf_inventory.preflight.run_preflight", return_value=report), patch.object(cli, "collect_resource") as collect, \
                patch.object(cli, "HttpClient") as client, patch("sys.stdout", new_callable=io.StringIO):
            status = cli.main(["--config", str(self.config([target])), "--output", str(self.root / "reports"), "--preflight"])
        self.assertEqual(status, 2)
        collect.assert_not_called()
        client.assert_not_called()
        saved = next((self.root / "reports").glob("*/preflight.json"))
        self.assertEqual(json.loads(saved.read_text()), report)
