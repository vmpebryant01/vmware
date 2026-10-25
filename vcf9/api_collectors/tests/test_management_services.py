"""Appliance configuration collection and baseline tests. Author: Paul Bryant."""

import copy
import unittest
from unittest.mock import Mock

from vcf_inventory import management_services as services
from vcf_inventory.http_client import ApiError
from vcf_inventory.management_services_report import build_management_services_report, validate_baseline


def baseline(**changes):
    entry = {"target": "vc-a", "endpoint": "https://vc.example", "dns": {"mode": "static", "servers": ["192.0.2.53"]},
             "ntp": {"servers": ["time.example"]}, "timesync": {"mode": "NTP"},
             "syslog": {"servers": [{"hostname": "logs.example", "port": 514, "protocol": "UDP"}]}, **changes}
    return {"author": "Paul Bryant", "schema_version": "1.0", "targets": [entry]}


def run():
    records = {
        "appliance_dns": [{"id": "configuration", "mode": "static", "servers": ["192.0.2.53"]}],
        "appliance_ntp": [{"id": "configuration", "servers": ["time.example"]}],
        "appliance_timesync": [{"id": "configuration", "mode": "NTP"}],
        "appliance_syslog": [{"id": "configuration", "servers": [{"hostname": "logs.example", "port": 514, "protocol": "UDP"}]}],
    }
    resources = {("vc-a", "vcenter", resource): {"records": rows, "collection": {"coverage": "complete"},
                 "collected_at": "2026-10-25T12:00:00Z"} for resource, rows in records.items()}
    return {"summary": {"targets": [{"name": "vc-a", "component": "vcenter", "endpoint": "https://vc.example"}]},
            "resources": resources, "unavailable": {}}


class CollectionTests(unittest.TestCase):
    def test_only_selected_vcenter_resources(self):
        self.assertEqual(services.DEFAULT_RESOURCES, {})
        self.assertEqual(services.ALLOWED_OPERATIONS, set())
        self.assertTrue(services.supports("vcenter", "appliance_ntp"))
        self.assertFalse(services.supports("nsx", "appliance_ntp"))

    def test_fixed_get_and_allowlist_projection(self):
        client = Mock(target={"component": "vcenter"}, collection_metadata={})
        client.get.return_value = {"mode": "static", "servers": ["192.0.2.53"], "password": "discard"}
        self.assertEqual(services.collect_resource(client, "appliance_dns"),
                         [{"id": "configuration", "mode": "static", "servers": ["192.0.2.53"]}])
        client.get.assert_called_once_with("/api/appliance/networking/dns/servers")
        self.assertEqual(client.collection_metadata["appliance_dns"]["coverage"], "complete")
        client.request.assert_not_called()

    def test_empty_lists_are_observed_configuration(self):
        for resource in ("appliance_ntp", "appliance_syslog"):
            self.assertEqual(services.normalize_config(resource, []), {"servers": []})

    def test_ntp_and_mode_are_distinct(self):
        self.assertEqual(services.normalize_config("appliance_timesync", "HOST"), {"mode": "HOST"})
        with self.assertRaises(ApiError):
            services.normalize_config("appliance_timesync", {"mode": "NTP"})

    def test_malformed_configurations_fail(self):
        cases = [("appliance_dns", {"mode": "static", "servers": "192.0.2.53"}),
                 ("appliance_ntp", ["same", "same"]), ("appliance_ntp", ["line\nbreak"]),
                 ("appliance_syslog", [{"hostname": "log", "port": True, "protocol": "UDP"}]),
                 ("appliance_syslog", [{"hostname": "log", "port": 65536, "protocol": "UDP"}])]
        for resource, value in cases:
            with self.subTest(resource=resource, value=value), self.assertRaises(ApiError):
                services.normalize_config(resource, value)

    def test_failed_collection_remains_incomplete(self):
        client = Mock(target={"component": "vcenter"}, collection_metadata={})
        client.get.return_value = None
        with self.assertRaises(ApiError):
            services.collect_resource(client, "appliance_dns")
        self.assertEqual(client.collection_metadata["appliance_dns"]["coverage"], "incomplete")

    def test_filters_rejected_before_request(self):
        client = Mock(target={"component": "vcenter", "filters": {"appliance_ntp": {"server": "x"}}})
        with self.assertRaises(ApiError):
            services.collect_resource(client, "appliance_ntp")
        client.get.assert_not_called()

    def test_probe_get_does_not_run_service_tests(self):
        for resource in services.RESOURCE_PATHS["vcenter"]:
            method, path, params, body, note = services.probe_request({"component": "vcenter"}, resource)
            self.assertEqual(method, "GET")
            self.assertIsNone(params)
            self.assertIsNone(body)
            self.assertIn("no DNS", note)


class BaselineTests(unittest.TestCase):
    def test_exact_matches_are_configuration_evidence(self):
        report = build_management_services_report(run(), baseline())
        self.assertEqual(report["status"], "success")
        self.assertTrue(all(row["baseline_match"] is True for row in report["records"]))
        self.assertTrue(all(row["status"] == "observed" for row in report["records"]))
        self.assertIn("clock synchronization", " ".join(report["limitations"]))

    def test_differences_request_review_without_partial_coverage(self):
        report = build_management_services_report(run(), baseline(ntp={"servers": ["other.example"]}))
        ntp = next(row for row in report["records"] if row["service"] == "ntp")
        self.assertEqual(ntp["status"], "review")
        self.assertFalse(ntp["baseline_match"])
        self.assertEqual(report["status"], "success")

    def test_server_order_ignored_but_case_and_protocol_exact(self):
        inventory = run()
        inventory["resources"][("vc-a", "vcenter", "appliance_ntp")]["records"][0]["servers"] = ["b", "a"]
        report = build_management_services_report(inventory, baseline(ntp={"servers": ["a", "b"]}))
        self.assertTrue(next(row for row in report["records"] if row["service"] == "ntp")["baseline_match"])
        report = build_management_services_report(run(), baseline(timesync={"mode": "ntp"}))
        self.assertFalse(next(row for row in report["records"] if row["service"] == "timesync")["baseline_match"])

    def test_no_baseline_does_not_imply_compliance(self):
        report = build_management_services_report(run())
        self.assertTrue(all(row["baseline_match"] is None for row in report["records"]))
        self.assertTrue(all("without_baseline" in row["observation"] for row in report["records"]))

    def test_missing_failed_duplicate_and_invalid_records_are_unknown(self):
        for kind in ("missing", "failed", "duplicate", "invalid"):
            inventory = run()
            key = ("vc-a", "vcenter", "appliance_ntp")
            if kind == "missing":
                del inventory["resources"][key]
            elif kind == "failed":
                inventory["unavailable"][key] = "failure"
            elif kind == "duplicate":
                inventory["resources"][key]["records"] *= 2
            else:
                inventory["resources"][key]["records"][0]["servers"] = None
            report = build_management_services_report(inventory, baseline())
            self.assertEqual(report["status"], "partial")
            self.assertEqual(next(row for row in report["records"] if row["service"] == "ntp")["status"], "unknown")

    def test_baseline_endpoint_mismatch_never_matches_target_name_alone(self):
        report = build_management_services_report(run(), baseline(endpoint="https://other.example"))
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["records"][-1]["observation"], "baseline_target_not_in_run")
        self.assertIsNone(report["records"][0]["baseline_match"])

    def test_strict_baseline_rejects_wrong_schema_or_extra_fields(self):
        cases = [baseline(), baseline(), baseline(), baseline(), baseline()]
        cases[0]["schema_version"] = "2.0"
        cases[1]["targets"].append(copy.deepcopy(cases[1]["targets"][0]))
        cases[2]["targets"][0]["endpoint"] = "https://user:pass@vc.example"
        cases[3]["targets"][0]["ntp"]["timeout"] = 1
        cases[4]["targets"][0]["syslog"]["servers"][0]["password"] = "x"
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_baseline(value)

    def test_empty_run_is_partial(self):
        inventory = run()
        inventory["summary"]["targets"] = []
        self.assertEqual(build_management_services_report(inventory)["status"], "partial")


if __name__ == "__main__":
    unittest.main()
