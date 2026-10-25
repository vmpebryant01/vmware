"""Offline lifecycle API and saved-evidence tests. Author: Paul Bryant."""

import copy
import json
import unittest
from unittest.mock import Mock, patch

from vcf_inventory import lifecycle
from vcf_inventory.http_client import ApiError, HttpClient
from vcf_inventory.lifecycle_report import build_lifecycle_report


NOW = "2026-10-25T12:00:00Z"
COLLECTED = "2026-10-25T10:00:00Z"
SCAN = "2026-10-25T09:00:00Z"


def desired():
    return {"base_image": {"version": "9.0.1.0.24957456", "details": {"private": "secret"}},
            "components": {"driver": {"version": "1.2", "details": {"private": "secret"}}},
            "add_on": {"name": "oem", "version": "9.0"}, "solutions": {}, "removed_components": {},
            "alternative_images": {"image-1": {"base_image": {"version": "9.0.0.0"}, "components": {}}}}


def compliance():
    return {"status": "NON_COMPLIANT", "scan_time": SCAN, "commit": "scan-commit",
            "impact": "REBOOT", "compliant_hosts": [], "non_compliant_hosts": ["host-1"],
            "incompatible_hosts": [], "unavailable_hosts": [],
            "notifications": {"info": [], "warnings": [{"message": "private secret"}], "errors": []},
            "hosts": {"host-1": {"status": "NON_COMPLIANT", "scan_time": SCAN, "commit": "scan-commit",
                                   "base_image": {"status": "NON_COMPLIANT", "current": {"version": "9.0.0.0"},
                                                  "target": {"version": "9.0.1.0.24957456"}},
                                   "components": {"driver": {"status": "COMPLIANT", "current": {"version": "1.2"},
                                                             "target": {"version": "1.2"}}},
                                   "remediation_details": {"secret": "private"}}}}


def client(replies=(), ids=None):
    result = Mock(target={"component": "vcenter", "lifecycle_cluster_ids": ["domain-c1"] if ids is None else ids})
    result.collection_metadata = {}
    result.get.side_effect = iter(replies)
    return result


def saved_run(image=None, scan=None, ids=None):
    ids = ["domain-c1"] if ids is None else ids
    resources = {}
    c = client([desired() if image is None else image], ids=ids)
    image_records = lifecycle.collect_resource(c, "lifecycle_desired_image")
    d = client([compliance() if scan is None else scan], ids=ids)
    scan_records = lifecycle.collect_resource(d, "lifecycle_compliance")
    for resource, records, transport in (("lifecycle_desired_image", image_records, c), ("lifecycle_compliance", scan_records, d)):
        resources[("vc", "vcenter", resource)] = {"records": records, "collected_at": COLLECTED,
                                               "collection": transport.collection_metadata[resource]}
    target = {"name": "vc", "component": "vcenter", "endpoint": "https://vc.example.com",
              "resources": [{"resource": resource, "status": "success"} for resource in lifecycle.RESOURCE_PATHS["vcenter"]]}
    return {"summary": {"status": "success", "completed_at": COLLECTED, "targets": [target]},
            "resources": resources, "unavailable": {}}


class LifecycleCollectionTests(unittest.TestCase):
    def test_supplemental_resources_are_optional(self):
        self.assertEqual(lifecycle.DEFAULT_RESOURCES, {})
        self.assertEqual(lifecycle.ALLOWED_OPERATIONS, set())
        self.assertTrue(lifecycle.supports("vcenter", "lifecycle_compliance"))
        self.assertFalse(lifecycle.supports("nsx", "lifecycle_compliance"))
        lifecycle.validate_target({"component": "vcenter", "resources": ["vms"]})

    def test_rejects_unsafe_or_implicit_cluster_scopes_before_requests(self):
        for ids in (None, [], ["domain-c1", "domain-c1"], ["../domain-c1"], ["domain-c1?refresh=true"],
                    ["cluster-1"], [True], ["domain-c" + "1" * 19], ["domain-c1"] * 1001):
            c = client(ids=ids)
            if ids is None:
                c.target.pop("lifecycle_cluster_ids")
            with self.subTest(ids=ids), self.assertRaises(ApiError):
                lifecycle.collect_resource(c, "lifecycle_compliance")
            c.get.assert_not_called()
        with self.assertRaises(ValueError):
            lifecycle.validate_target({"component": "nsx", "lifecycle_cluster_ids": ["domain-c1"]})

    def test_lifecycle_filters_are_not_silently_ignored(self):
        target = {"component": "vcenter", "lifecycle_cluster_ids": ["domain-c1"],
                  "filters": {"lifecycle_compliance": {"x": "y"}}}
        with self.assertRaises(ValueError):
            lifecycle.validate_target(target)

    def test_reads_exact_explicit_clusters_and_projects_software_versions(self):
        c = client([desired(), desired()], ids=["domain-c1", "domain-c2"])
        rows = lifecycle.collect_resource(c, "lifecycle_desired_image")
        self.assertEqual([call.args[0] for call in c.get.call_args_list], [
            "/api/esx/settings/clusters/domain-c1/software", "/api/esx/settings/clusters/domain-c2/software"])
        self.assertEqual([row["id"] for row in rows], ["domain-c1", "domain-c2"])
        self.assertEqual(rows[0]["alternative_images"]["image-1"]["base_image"], {"version": "9.0.0.0"})
        self.assertEqual(rows[0]["components"], {"driver": {"version": "1.2"}})
        self.assertNotIn("secret", json.dumps(rows))
        metadata = c.collection_metadata["lifecycle_desired_image"]
        self.assertEqual(metadata["coverage"], "complete")
        self.assertEqual(metadata["queried_cluster_ids"], ["domain-c1", "domain-c2"])
        self.assertFalse(metadata["refresh_requested"])
        c.request.assert_not_called()

    def test_projects_compliance_without_messages_or_remediation_payloads(self):
        c = client([compliance()])
        rows = lifecycle.collect_resource(c, "lifecycle_compliance")
        self.assertEqual(c.get.call_args.args[0], "/api/esx/settings/clusters/domain-c1/software/compliance")
        self.assertEqual(rows[0]["notification_counts"], {"info": 0, "warnings": 1, "errors": 0})
        self.assertEqual(rows[0]["scan_time"], SCAN)
        self.assertEqual(rows[0]["commit"], "scan-commit")
        self.assertEqual(rows[0]["hosts"]["host-1"]["base_image"]["current"], {"version": "9.0.0.0"})
        self.assertNotIn("secret", json.dumps(rows))
        self.assertNotIn("remediation_details", rows[0]["hosts"]["host-1"])

    def test_retains_addon_and_removed_component_compliance_versions(self):
        scan = compliance()
        scan["hosts"]["host-1"]["add_on"] = {"status": "NON_COMPLIANT", "current": {"name": "oem", "version": "9.0"},
                                                "target": {"name": "oem", "version": "9.1"}}
        scan["hosts"]["host-1"]["removed_components"] = {"driver-old": {"status": "NON_COMPLIANT", "current": {"version": "1.0"}}}
        result = build_lifecycle_report(saved_run(scan=scan), now=NOW)
        host = result["records"][1]
        self.assertEqual(host["add_on_compliance"]["target"], {"name": "oem", "version": "9.1"})
        self.assertEqual(host["removed_component_compliance"]["driver-old"]["current"], {"version": "1.0"})

    def test_partial_fanout_keeps_incomplete_metadata_and_queried_scope(self):
        c = client(ids=["domain-c1", "domain-c2"])
        c.get.side_effect = [compliance(), ApiError("HTTP 404", status=404)]
        with self.assertRaises(ApiError):
            lifecycle.collect_resource(c, "lifecycle_compliance")
        metadata = c.collection_metadata["lifecycle_compliance"]
        self.assertEqual(metadata["coverage"], "incomplete")
        self.assertEqual(metadata["queried_cluster_ids"], ["domain-c1"])
        self.assertEqual(metadata["request_count"], 2)

    def test_rejects_error_envelopes_and_malformed_success_bodies(self):
        documents = [{"messages": [{"message": "private secret"}]}, [], None,
                     {**compliance(), "hosts": []}, {**compliance(), "compliant_hosts": [True]},
                     {**compliance(), "non_compliant_hosts": ["host-1", "host-1"]},
                     {**compliance(), "hosts": {"host-1": {"status": {"private": "secret"}}}}]
        for payload in documents:
            c = client([payload])
            with self.subTest(payload=payload), self.assertRaises(ApiError) as error:
                lifecycle.collect_resource(c, "lifecycle_compliance")
            self.assertNotIn("secret", str(error.exception))
            self.assertEqual(c.collection_metadata["lifecycle_compliance"]["coverage"], "incomplete")

    def test_rejects_invalid_desired_image_schemas(self):
        for payload in ({"base_image": {"version": "9.0"}}, {"base_image": {"version": True}, "components": {}},
                        {**desired(), "alternative_images": []}, {**desired(), "components": {"x": {}}}):
            c = client([payload])
            with self.subTest(payload=payload), self.assertRaises(ApiError):
                lifecycle.collect_resource(c, "lifecycle_desired_image")

    def test_preflight_only_reads_first_configured_cluster(self):
        target = {"component": "vcenter", "lifecycle_cluster_ids": ["domain-c1", "domain-c2"]}
        method, path, params, body, _ = lifecycle.probe_request(target, "lifecycle_compliance")
        self.assertEqual((method, path, params, body), ("GET", "/api/esx/settings/clusters/domain-c1/software/compliance", None, None))
        self.assertIsNone(lifecycle.probe_request({"component": "vcenter"}, "lifecycle_compliance"))

    def test_transport_refuses_scan_stage_and_apply_actions_before_network(self):
        with patch("vcf_inventory.http_client.build_opener") as opener:
            transport = HttpClient({"component": "vcenter", "url": "https://vc.example.com"})
        for action in ("scan", "stage", "apply", "check"):
            with self.subTest(action=action), self.assertRaises(ApiError):
                transport.request("POST", "/api/esx/settings/clusters/domain-c1/software", params={"action": action})
        opener.return_value.open.assert_not_called()


class LifecycleReportTests(unittest.TestCase):
    def test_noncompliance_is_review_not_incomplete_coverage(self):
        result = build_lifecycle_report(saved_run(), now=NOW)
        self.assertEqual(result["status"], "success")
        cluster, host = result["records"]
        self.assertEqual(cluster["status"], "review")
        self.assertEqual(host["status"], "review")
        self.assertEqual(cluster["scan_age_hours_at_collection"], 1)
        self.assertEqual(cluster["source_age_hours"], 2)
        self.assertEqual(host["current_base_image_version"], "9.0.0.0")
        self.assertEqual(host["scan_target_base_matches_collected_desired_base"], True)
        self.assertEqual(cluster["scan_commit"], "scan-commit")

    def test_compliant_status_uses_cached_scan_and_preserves_current_desired_difference(self):
        scan = compliance()
        scan.update(status="COMPLIANT", compliant_hosts=["host-1"], non_compliant_hosts=[])
        scan["hosts"]["host-1"]["status"] = "COMPLIANT"
        image = desired()
        image["base_image"]["version"] = "9.0.2.0"
        result = build_lifecycle_report(saved_run(image=image, scan=scan), now=NOW)
        self.assertEqual(result["records"][0]["status"], "observed")
        self.assertFalse(result["records"][1]["scan_target_base_matches_collected_desired_base"])
        self.assertIn("matching base-image version alone", " ".join(result["limitations"]))

    def test_stale_scan_is_review_at_collection_not_at_later_evaluation(self):
        run = saved_run()
        early = build_lifecycle_report(run, max_scan_age_hours=2, now=NOW)
        late = build_lifecycle_report(run, max_scan_age_hours=2, now="2027-10-25T12:00:00Z")
        self.assertEqual(early["records"][0]["scan_freshness"], "within_threshold")
        self.assertEqual(late["records"][0]["scan_freshness"], "within_threshold")
        stale = build_lifecycle_report(run, max_scan_age_hours=0.5, now=NOW)
        self.assertEqual(stale["records"][0]["scan_freshness"], "stale")

    def test_invalid_naive_numeric_and_future_scan_times_remain_unknown(self):
        for time in ("2026-10-25T11:00:00Z", "2026-10-25T09:00:00", "bad", 1234567890, None):
            run = saved_run()
            run["resources"][("vc", "vcenter", "lifecycle_compliance")]["records"][0]["scan_time"] = time
            result = build_lifecycle_report(run, now=NOW)
            self.assertEqual(result["status"], "partial")
            self.assertIsNone(result["records"][0]["scan_age_hours_at_collection"])

    def test_missing_or_failed_resource_is_not_treated_as_compliance(self):
        for fail in (False, True):
            run = saved_run()
            key = ("vc", "vcenter", "lifecycle_compliance")
            if fail:
                run["unavailable"][key] = "failed"
            else:
                del run["resources"][key]
            result = build_lifecycle_report(run, now=NOW)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["records"][0]["status"], "unknown")
            self.assertIsNone(result["records"][0]["native_compliance_status"])

    def test_incomplete_scope_and_scope_changes_do_not_join_as_complete(self):
        for kind in ("incomplete", "changed"):
            run = saved_run()
            doc = run["resources"][("vc", "vcenter", "lifecycle_desired_image")]
            if kind == "incomplete":
                doc["collection"]["coverage"] = "incomplete"
            else:
                doc["collection"].update(configured_cluster_ids=["domain-c2"], queried_cluster_ids=["domain-c2"])
                doc["records"][0].update(id="domain-c2", cluster_id="domain-c2")
            result = build_lifecycle_report(run, now=NOW)
            self.assertEqual(result["status"], "partial")
            self.assertTrue(all(row["status"] == "unknown" for row in result["records"]))

    def test_duplicate_and_out_of_scope_saved_rows_are_unknown(self):
        for duplicate in (True, False):
            run = saved_run()
            doc = run["resources"][("vc", "vcenter", "lifecycle_compliance")]
            row = copy.deepcopy(doc["records"][0])
            if not duplicate:
                row.update(id="domain-c2", cluster_id="domain-c2")
            doc["records"].append(row)
            result = build_lifecycle_report(run, now=NOW)
            self.assertEqual(result["records"][0]["status"], "unknown")

    def test_invalid_saved_cluster_identifier_does_not_crash_or_join(self):
        run = saved_run()
        run["resources"][("vc", "vcenter", "lifecycle_compliance")]["records"][0]["cluster_id"] = []
        result = build_lifecycle_report(run, now=NOW)
        self.assertEqual(result["records"][0]["status"], "unknown")

    def test_unavailable_hosts_and_inconsistent_classification_remain_unknown(self):
        for conflict in (False, True):
            scan = compliance()
            if conflict:
                scan["compliant_hosts"] = ["host-1"]
            else:
                scan["unavailable_hosts"] = ["host-2"]
            result = build_lifecycle_report(saved_run(scan=scan), now=NOW)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["records"][0]["status"], "unknown")
            if not conflict:
                row = next(row for row in result["records"] if row.get("host_id") == "host-2")
                self.assertEqual(row["native_compliance_status"], "UNAVAILABLE")
                self.assertEqual(row["status"], "unknown")
                known = next(row for row in result["records"] if row.get("host_id") == "host-1")
                self.assertEqual(known["status"], "review")

    def test_desired_image_observation_time_is_required(self):
        run = saved_run()
        run["resources"][("vc", "vcenter", "lifecycle_desired_image")]["collected_at"] = None
        result = build_lifecycle_report(run, now=NOW)
        self.assertEqual(result["records"][0]["status"], "unknown")
        self.assertIn("desired_collection_timestamp_unknown_invalid_or_future", result["records"][0]["unknown_reasons"])

    def test_unknown_native_status_never_becomes_compliant(self):
        scan = compliance()
        scan["status"] = "NEW_VENDOR_STATUS"
        result = build_lifecycle_report(saved_run(scan=scan), now=NOW)
        self.assertEqual(result["records"][0]["status"], "unknown")
        self.assertEqual(result["records"][0]["native_compliance_status"], "NEW_VENDOR_STATUS")

    def test_missing_and_future_collection_time_remains_unknown(self):
        for time in (None, "2026-10-26T12:00:00Z"):
            run = saved_run()
            run["resources"][("vc", "vcenter", "lifecycle_compliance")]["collected_at"] = time
            result = build_lifecycle_report(run, now=NOW)
            self.assertEqual(result["records"][0]["status"], "unknown")

    def test_no_lifecycle_targets_returns_an_explicit_unknown_record(self):
        result = build_lifecycle_report({"summary": {"targets": []}, "resources": {}, "unavailable": {}}, now=NOW)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["records"][0]["unknown_reasons"], ["no_lifecycle_resources_collected"])

    def test_thresholds_and_evaluation_time_are_validated(self):
        for threshold in (True, 0, -1, float("nan"), float("inf"), "24"):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                build_lifecycle_report(saved_run(), max_scan_age_hours=threshold, now=NOW)
        with self.assertRaises(ValueError):
            build_lifecycle_report(saved_run(), now="2026-10-25T12:00:00")


if __name__ == "__main__":
    unittest.main()
