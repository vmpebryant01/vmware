"""Protection coverage and native identity boundary tests. Author: Paul Bryant."""

import copy
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from vcf_inventory.http_client import ApiError
from vcf_inventory.protection_evidence import collect_resource, validate_target
from vcf_inventory.protection_report import build_protection_report, validate_policy

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def document(target, component, resource, records, **metadata):
    return dict(target=target, component=component, resource=resource, records=records, collected_at=NOW.isoformat(), **metadata)


class ProtectionReportTests(unittest.TestCase):
    def setUp(self):
        self.policy = {"author": "Paul Bryant", "requirements": [{"vcenter_target": "vc", "vm_id": "vm-1",
            "replication": {"target": "vr", "pairing_id": "pair", "source_vc_id": "vc-uuid", "vm_id": "native-vm-1"},
            "site_recovery": {"target": "srm", "pairing_id": "pair", "group_id": "group", "vm_id": "protected-1"}}]}
        self.run = {"resources": {
            ("vc", "vcenter", "vms"): document("vc", "vcenter", "vms", [{"vm": "vm-1", "name": "application"}]),
            ("vr", "vsphere_replication", "replications"): document("vr", "vsphere_replication", "replications", [
                {"id": "replication-1", "vm_id": "native-vm-1", "source_vc_id": "vc-uuid", "pairing_id": "pair",
                 "status": {"status": "OK", "rpo_violation": False}, "current_rpo_violation": 0,
                 "configuration_state": "OK", "last_sync_time": int(NOW.timestamp() * 1000) - 60000}], pairing_id="pair"),
            ("srm", "live_site_recovery", "group_vms"): document("srm", "live_site_recovery", "group_vms", [
                {"id": "protected-1", "pairing_id": "pair", "group_id": "group", "protection_status": "native-state",
                 "protection_error_count": 0}], pairing_id="pair", collection={"queried_group_ids": ["group"]})},
            "unavailable": {}}

    def report(self):
        return build_protection_report(self.run, self.policy, now=NOW)

    def test_explicit_native_contexts_observe_expected_vm(self):
        result = self.report()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["records"][0]["state"], "observed")
        self.assertNotIn("recoverable", str(result))

    def test_missing_or_failed_collection_stays_unknown(self):
        del self.run["resources"][("vr", "vsphere_replication", "replications")]
        result = self.report()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["records"][0]["observations"]["replication"]["state"], "unknown")

    def test_empty_explicit_scope_is_an_observed_gap(self):
        self.run["resources"][("vr", "vsphere_replication", "replications")]["records"] = []
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "gap")

    def test_unqueried_pairing_or_group_is_unknown_not_gap(self):
        self.run["resources"][("srm", "live_site_recovery", "group_vms")]["collection"]["queried_group_ids"] = ["other"]
        self.assertEqual(self.report()["records"][0]["observations"]["site_recovery"]["state"], "unknown")
        self.run["resources"][("vr", "vsphere_replication", "replications")]["pairing_id"] = "other"
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "unknown")

    def test_implicit_pairing_requires_resolved_scope_evidence(self):
        document = self.run["resources"][("vr", "vsphere_replication", "replications")]
        del document["pairing_id"]
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "unknown")
        document["collection"] = {"queried_pairing_ids": ["pair"]}
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "observed")

    def test_vcenter_local_id_never_matches_foreign_source_id(self):
        document = self.run["resources"][("vr", "vsphere_replication", "replications")]
        document["records"][0]["source_vc_id"] = "another-vcenter"
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "gap")

    def test_missing_native_fields_and_duplicates_are_unknown(self):
        rows = self.run["resources"][("vr", "vsphere_replication", "replications")]["records"]
        rows.append(copy.deepcopy(rows[0]))
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "unknown")
        rows[:] = [{"id": "missing-fields"}]
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "unknown")

    def test_rpo_and_stale_sync_are_reported_separately_from_membership(self):
        row = self.run["resources"][("vr", "vsphere_replication", "replications")]["records"][0]
        row["status"]["rpo_violation"] = True
        row["last_sync_time"] -= 48 * 3600 * 1000
        observation = self.report()["records"][0]["observations"]["replication"]
        self.assertEqual(observation["state"], "exception")
        self.assertEqual(len(observation["findings"]), 2)

    def test_zero_and_future_sync_times_are_unknown(self):
        row = self.run["resources"][("vr", "vsphere_replication", "replications")]["records"][0]
        for timestamp in (0, int(NOW.timestamp() * 1000) + 60000):
            row["last_sync_time"] = timestamp
            self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "unknown")

    def test_reading_old_run_does_not_create_new_stale_sync_alarm(self):
        future = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        observation = build_protection_report(self.run, self.policy, now=future)["records"][0]["observations"]["replication"]
        self.assertEqual(observation["state"], "observed")
        self.assertLess(observation["sync_age_hours"], 1)
        self.assertGreater(observation["observation_age_hours"], 24)

    def test_group_protection_errors_are_observed_exceptions(self):
        self.run["resources"][("srm", "live_site_recovery", "group_vms")]["records"][0]["protection_error_count"] = 2
        self.assertEqual(self.report()["records"][0]["observations"]["site_recovery"]["state"], "exception")

    def test_known_exception_does_not_hide_missing_timestamp_evidence(self):
        row = self.run["resources"][("vr", "vsphere_replication", "replications")]["records"][0]
        row["status"]["rpo_violation"] = True
        row["last_sync_time"] = 0
        report = self.report()
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["records"][0]["observations"]["replication"]["state"], "exception")
        self.assertFalse(report["records"][0]["observations"]["replication"]["evidence_complete"])

    def test_malformed_imported_scope_stays_unknown(self):
        document = self.run["resources"][("vr", "vsphere_replication", "replications")]
        del document["pairing_id"]
        document["collection"] = {"queried_pairing_ids": None}
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "unknown")
        self.run["resources"][("srm", "live_site_recovery", "group_vms")]["collection"]["queried_group_ids"] = None
        self.assertEqual(self.report()["records"][0]["observations"]["site_recovery"]["state"], "unknown")

    def test_membership_without_native_state_is_not_complete_protection_evidence(self):
        row = self.run["resources"][("srm", "live_site_recovery", "group_vms")]["records"][0]
        row.update(protection_status=None, protection_error_count=None)
        result = self.report()
        observation = result["records"][0]["observations"]["site_recovery"]
        self.assertTrue(observation["membership_observed"])
        self.assertEqual(observation["state"], "unknown")
        self.assertEqual(result["status"], "partial")

    def test_malformed_imported_native_status_is_unknown(self):
        row = self.run["resources"][("vr", "vsphere_replication", "replications")]["records"][0]
        row["status"]["status"] = {"unexpected": "value"}
        self.assertEqual(self.report()["records"][0]["observations"]["replication"]["state"], "unknown")

    def test_duplicate_and_invalid_requirements_are_rejected(self):
        self.policy["requirements"].append(copy.deepcopy(self.policy["requirements"][0]))
        with self.assertRaises(ValueError):
            validate_policy(self.policy)
        self.policy["requirements"].pop()
        self.policy["requirements"][0]["max_sync_age_hours"] = float("nan")
        with self.assertRaises(ValueError):
            validate_policy(self.policy)


class ProtectedVmCollectionTests(unittest.TestCase):
    def client(self, pages):
        return SimpleNamespace(target={"component": "live_site_recovery", "pairing_id": "pair", "group_ids": ["group"]},
                               get=Mock(side_effect=pages), headers={}, _product_state={}, collection_metadata={})

    def test_collection_projects_status_and_exact_empty_scopes(self):
        client = self.client([{"list": [{"pairing_id": "pair"}], "_meta": {"total": 1}},
                              {"list": [{"id": "vm-1", "protection_status_details": {"status": "native", "errors": [{"secret": "omitted"}]}}], "_meta": {"total": 1}}])
        rows = collect_resource(client, "group_vms")
        self.assertEqual(rows[0]["protection_error_count"], 1)
        self.assertNotIn("omitted", str(rows))
        self.assertEqual(client.collection_metadata["group_vms"]["queried_group_ids"], ["group"])
        client = self.client([{"list": [{"pairing_id": "pair"}], "_meta": {"total": 1}}, {"list": [], "_meta": {"total": 0}}])
        self.assertEqual(collect_resource(client, "group_vms"), [])
        self.assertEqual(client.collection_metadata["group_vms"]["coverage"], "complete")

    def test_nonapplicable_or_wrong_scope_is_not_empty_success(self):
        for payload in (None, {"list": [{"id": "vm", "group_id": "other"}], "_meta": {"total": 1}}):
            client = self.client([{"list": [{"pairing_id": "pair"}], "_meta": {"total": 1}}, payload])
            with self.assertRaises(ApiError):
                collect_resource(client, "group_vms")
            self.assertEqual(client.collection_metadata["group_vms"]["coverage"], "incomplete")

    def test_explicit_group_and_pairing_are_required(self):
        with self.assertRaises(ValueError):
            validate_target({"component": "live_site_recovery", "resources": ["group_vms"], "group_ids": ["group"]})
