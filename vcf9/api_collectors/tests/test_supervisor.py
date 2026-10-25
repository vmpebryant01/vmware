"""Supervisor selector, state and quota evidence tests. Author: Paul Bryant."""

import copy
import unittest
from unittest.mock import Mock

from vcf_inventory import supervisor
from vcf_inventory.http_client import ApiError
from vcf_inventory.supervisor_report import build_supervisor_report


def summary():
    return {"name": "Supervisor One", "config_status": "RUNNING", "kubernetes_status": "READY",
            "stats": {"cpu_used": 9, "cpu_capacity": 10, "memory_used": 50, "memory_capacity": 100,
                      "storage_used": 20, "storage_capacity": 100}}


def conditions():
    return [{"type": "Ready", "status": "TRUE", "last_transition_time": "2026-10-25T10:00:00Z", "reason": "Ready"}]


def namespace():
    return {"cluster": "domain-c1", "config_status": "RUNNING", "stats": {"cpu_used": 4, "memory_used": 10, "storage_used": 20},
            "resource_spec": {"cpu": 8, "memory": "16Gi"},
            "storage_specs": [{"policy": "policy-1", "limit": 100}, {"policy": "policy-2"}], "messages": []}


def run():
    source = {"supervisor_summaries": {"id": "sup-1", "supervisor_id": "sup-1", **summary()},
              "supervisor_conditions": {"id": "sup-1", "supervisor_id": "sup-1", "conditions": conditions()},
              "namespaces": {"id": "ns-1", "namespace_id": "ns-1", **namespace()}}
    resources = {}
    for resource, row in source.items():
        key = ("vc-a", "vcenter", resource)
        selector = supervisor.SELECTORS[resource]
        identifiers = ["ns-1" if resource == "namespaces" else "sup-1"]
        resources[key] = {"records": [row], "collected_at": "2026-10-25T12:00:00Z",
                          "collection": {"coverage": "complete", selector: identifiers, "queried_ids": identifiers[:]}}
    return {"summary": {"targets": [{"name": "vc-a", "component": "vcenter", "endpoint": "https://vc.example"}]},
            "resources": resources, "unavailable": {}}


class CollectionTests(unittest.TestCase):
    def client(self, responses, **options):
        return Mock(target={"component": "vcenter", "supervisor_ids": ["sup-1"], "namespace_ids": ["ns-1"], **options},
                    collection_metadata={}, get=Mock(side_effect=responses))

    def test_opt_in_only_and_no_mutating_operations(self):
        self.assertEqual(supervisor.DEFAULT_RESOURCES, {})
        self.assertEqual(supervisor.ALLOWED_OPERATIONS, set())
        self.assertFalse(supervisor.supports("nsx", "supervisor_summaries"))

    def test_only_explicit_ids_and_current_summary_route(self):
        client = self.client([summary(), summary()], supervisor_ids=["sup-1", "sup-2"])
        rows = supervisor.collect_resource(client, "supervisor_summaries")
        self.assertEqual([row["supervisor_id"] for row in rows], ["sup-1", "sup-2"])
        self.assertEqual([call.args[0] for call in client.get.call_args_list], [
            "/api/vcenter/namespace-management/supervisors/sup-1/summary",
            "/api/vcenter/namespace-management/supervisors/sup-2/summary"])
        self.assertEqual(client.collection_metadata["supervisor_summaries"]["supervisor_ids"], ["sup-1", "sup-2"])
        self.assertEqual(client.collection_metadata["supervisor_summaries"]["coverage"], "complete")
        client.request.assert_not_called()

    def test_selected_namespace_quota_and_policy_limits(self):
        client = self.client([namespace()])
        rows = supervisor.collect_resource(client, "namespaces")
        client.get.assert_called_once_with("/api/vcenter/namespaces/instances/ns-1")
        self.assertEqual(rows[0]["resource_spec"], {"cpu": 8, "memory": "16Gi"})
        self.assertIsNone(rows[0]["storage_specs"][1]["limit"])

    def test_sensitive_unrelated_fields_and_message_arguments_excluded(self):
        value = summary()
        value.update(apiendpoint="https://private.example", password="secret")
        value["messages"] = [{"severity": "ERROR", "details": {"id": "message-1", "args": ["password=secret"]}}]
        row = supervisor.collect_resource(self.client([value]), "supervisor_summaries")[0]
        self.assertNotIn("secret", str(row))
        self.assertNotIn("apiendpoint", row)
        self.assertEqual(row["messages"], [{"severity": "ERROR", "message_id": "message-1"}])

    def test_missing_and_bad_selectors_rejected_before_network(self):
        for identifiers in (None, [], ["sup", "sup"], ["../../escape"], [True], ["a\nb"], ["sup"] * 1001):
            client = self.client([], supervisor_ids=identifiers)
            with self.subTest(identifiers=identifiers), self.assertRaises(ApiError):
                supervisor.collect_resource(client, "supervisor_summaries")
            client.get.assert_not_called()

    def test_selector_wrong_component_and_filters_rejected(self):
        for options in ({"component": "nsx", "supervisor_ids": ["sup"]},
                        {"component": "vcenter", "namespace_ids": ["ns"], "filters": {"namespaces": {"all": True}}}):
            with self.assertRaises(ValueError):
                supervisor.validate_target(options)

    def test_namespace_selector_not_required_for_supervisor_only(self):
        supervisor.validate_target({"component": "vcenter", "resources": ["supervisor_conditions"], "supervisor_ids": ["sup"]})

    def test_mid_fanout_failure_leaves_incomplete_scope(self):
        client = self.client([summary(), ApiError("not found")], supervisor_ids=["sup-1", "sup-2"])
        with self.assertRaises(ApiError):
            supervisor.collect_resource(client, "supervisor_summaries")
        metadata = client.collection_metadata["supervisor_summaries"]
        self.assertEqual(metadata["coverage"], "incomplete")
        self.assertEqual(metadata["queried_ids"], ["sup-1"])

    def test_duplicate_condition_types_fail(self):
        client = self.client([conditions() * 2])
        with self.assertRaises(ApiError):
            supervisor.collect_resource(client, "supervisor_conditions")

    def test_empty_conditions_preserved_instead_of_healthy(self):
        row = supervisor.collect_resource(self.client([[]]), "supervisor_conditions")[0]
        self.assertEqual(row["conditions"], [])

    def test_bad_statistics_and_duplicate_storage_policy_fail(self):
        values = [namespace(), namespace(), namespace()]
        values[0]["stats"]["cpu_used"] = True
        values[1]["storage_specs"] *= 2
        values[2]["resource_spec"] = {"cpu": {"limit": 8}}
        for value in values:
            with self.subTest(value=value), self.assertRaises(ApiError):
                supervisor.collect_resource(self.client([value]), "namespaces")

    def test_required_summary_fields_fail_before_claiming_complete_contract(self):
        cases = [{"name": "Supervisor", "stats": "notobject", "config_status": {}, "kubernetes_status": []}]
        for field in ("name", "stats", "config_status", "kubernetes_status"):
            value = summary()
            del value[field]
            cases.append(value)
        for field in ("cpu_used", "cpu_capacity", "memory_used", "memory_capacity", "storage_used", "storage_capacity"):
            value = summary()
            del value["stats"][field]
            cases.append(value)
        for value in cases:
            transport = self.client([value])
            with self.subTest(value=value), self.assertRaises(ApiError):
                supervisor.collect_resource(transport, "supervisor_summaries")
            self.assertEqual(transport.collection_metadata["supervisor_summaries"]["coverage"], "incomplete")

    def test_required_namespace_fields_and_stats_fail_before_complete_contract(self):
        cases = [{"cluster": "domain-c1", "storage_specs": []}]
        for field in ("cluster", "config_status", "stats", "messages", "storage_specs"):
            value = namespace()
            del value[field]
            cases.append(value)
        for field in ("cpu_used", "memory_used", "storage_used"):
            value = namespace()
            del value["stats"][field]
            cases.append(value)
        for value in cases:
            transport = self.client([value])
            with self.subTest(value=value), self.assertRaises(ApiError):
                supervisor.collect_resource(transport, "namespaces")
            self.assertEqual(transport.collection_metadata["namespaces"]["coverage"], "incomplete")

    def test_statistics_outside_int64_range_are_rejected(self):
        for resource, document in (("supervisor_summaries", summary()), ("namespaces", namespace())):
            document["stats"]["cpu_used"] = 10**400
            transport = self.client([document])
            with self.subTest(resource=resource), self.assertRaises(ApiError):
                supervisor.collect_resource(transport, resource)
            self.assertEqual(transport.collection_metadata[resource]["coverage"], "incomplete")

    def test_valid_empty_optional_summary_messages_and_namespace_constraints(self):
        value = summary()
        value["messages"] = []
        self.assertEqual(supervisor.collect_resource(self.client([value]), "supervisor_summaries")[0]["messages"], [])
        value = namespace()
        value.update(resource_spec=None, storage_specs=[])
        row = supervisor.collect_resource(self.client([value]), "namespaces")[0]
        self.assertIsNone(row["resource_spec"])
        self.assertEqual(row["storage_specs"], [])

    def test_probe_one_id_no_discovery(self):
        plan = supervisor.probe_request({"component": "vcenter", "supervisor_ids": ["sup:1", "sup2"]}, "supervisor_conditions")
        self.assertEqual(plan[:4], ("GET", "/api/vcenter/namespace-management/supervisors/sup%3A1/conditions", None, None))
        self.assertIsNone(supervisor.probe_request({"component": "vcenter"}, "supervisor_summaries"))


class ReportTests(unittest.TestCase):
    def test_native_status_and_capacity_thresholds(self):
        report = build_supervisor_report(run())
        self.assertEqual(report["status"], "success")
        row = next(row for row in report["records"] if row["record_type"] == "supervisor")
        self.assertEqual(row["config_status"], "RUNNING")
        self.assertEqual(row["conditions"][0]["status"], "TRUE")
        self.assertEqual(row["capacity"]["cpu"]["used_percent"], 90)
        self.assertTrue(row["capacity"]["cpu"]["threshold_exceeded"])
        self.assertFalse(row["capacity"]["memory"]["threshold_exceeded"])

    def test_namespace_usage_not_divided_by_storage_policy_limit(self):
        report = build_supervisor_report(run())
        row = next(row for row in report["records"] if row["record_type"] == "namespace")
        self.assertEqual(row["resource_spec_native"], {"cpu": 8, "memory": "16Gi"})
        self.assertEqual(row["storage_specs"][0]["limit"], 100)
        self.assertNotIn("used_percent", str(row))

    def test_missing_companion_conditions_unknown(self):
        inventory = run()
        del inventory["resources"][("vc-a", "vcenter", "supervisor_conditions")]
        report = build_supervisor_report(inventory)
        self.assertEqual(report["status"], "partial")
        row = next(row for row in report["records"] if row["record_type"] == "supervisor")
        self.assertEqual(row["conditions_availability"], "unknown")
        self.assertIsNone(row["conditions"])

    def test_zero_capacity_and_missing_metric_are_unknown_not_zero_usage(self):
        inventory = run()
        stats = inventory["resources"][("vc-a", "vcenter", "supervisor_summaries")]["records"][0]["stats"]
        stats["cpu_capacity"] = 0
        del stats["storage_used"]
        report = build_supervisor_report(inventory)
        self.assertEqual(report["status"], "partial")
        row = next(row for row in report["records"] if row["record_type"] == "supervisor")
        for metric in ("cpu", "storage"):
            self.assertIsNone(row["capacity"][metric]["used_percent"])
            self.assertIsNone(row["capacity"][metric]["threshold_exceeded"])

    def test_duplicate_id_never_arbitrarily_selected(self):
        inventory = run()
        inventory["resources"][("vc-a", "vcenter", "namespaces")]["records"] *= 2
        report = build_supervisor_report(inventory)
        row = next(row for row in report["records"] if row["record_type"] == "namespace")
        self.assertEqual(row["availability"], "unknown")
        self.assertEqual(report["status"], "partial")

    def test_out_of_scope_and_malformed_identifiers_excluded(self):
        for identifier in ("other", ["bad"]):
            inventory = run()
            row = inventory["resources"][("vc-a", "vcenter", "namespaces")]["records"][0]
            row["namespace_id"] = identifier
            report = build_supervisor_report(inventory)
            self.assertEqual(report["status"], "partial")
            self.assertIsNone(next(row for row in report["records"] if row["record_type"] == "namespace")["cluster_id"])

    def test_failed_resources_and_missing_saved_scope_emit_unknown(self):
        for failure in ("failed", "scope", "queried_missing", "queried_partial", "queried_duplicate"):
            inventory = run()
            key = ("vc-a", "vcenter", "namespaces")
            if failure == "failed":
                inventory["unavailable"][key] = "403"
            elif failure == "scope":
                del inventory["resources"][key]["collection"]["namespace_ids"]
            elif failure == "queried_missing":
                del inventory["resources"][key]["collection"]["queried_ids"]
            elif failure == "queried_partial":
                inventory["resources"][key]["collection"]["queried_ids"] = []
            else:
                inventory["resources"][key]["collection"]["queried_ids"] = ["ns-1", "ns-1"]
            report = build_supervisor_report(inventory)
            self.assertEqual(report["status"], "partial")
            self.assertTrue(any(row["record_type"] == "collection" and row["availability"] == "unknown" for row in report["records"]))

    def test_empty_conditions_cannot_satisfy_complete_health_evidence(self):
        inventory = run()
        inventory["resources"][("vc-a", "vcenter", "supervisor_conditions")]["records"][0]["conditions"] = []
        self.assertEqual(build_supervisor_report(inventory)["status"], "partial")

    def test_malformed_saved_stats_or_conditions_stay_partial(self):
        for value in ("bad", [], None):
            inventory = run()
            inventory["resources"][("vc-a", "vcenter", "supervisor_summaries")]["records"][0]["stats"] = value
            self.assertEqual(build_supervisor_report(inventory)["status"], "partial")
        inventory = run()
        inventory["resources"][("vc-a", "vcenter", "supervisor_conditions")]["records"][0]["conditions"] = [None]
        self.assertEqual(build_supervisor_report(inventory)["status"], "partial")

    def test_huge_saved_usage_is_unknown_and_does_not_overflow(self):
        for resource in ("supervisor_summaries", "namespaces"):
            inventory = run()
            inventory["resources"][("vc-a", "vcenter", resource)]["records"][0]["stats"]["cpu_used"] = 10**400
            report = build_supervisor_report(inventory)
            self.assertEqual(report["status"], "partial")
            if resource == "supervisor_summaries":
                row = next(row for row in report["records"] if row["record_type"] == "supervisor")
                self.assertIsNone(row["capacity"]["cpu"]["used_native"])
                self.assertIsNone(row["capacity"]["cpu"]["used_percent"])
                self.assertIsNone(row["capacity"]["cpu"]["threshold_exceeded"])
            else:
                row = next(row for row in report["records"] if row["record_type"] == "namespace")
                self.assertEqual(row["availability"], "unknown")
                self.assertIsNone(row["stats_native"]["cpu_used"])

    def test_invalid_thresholds_rejected(self):
        for value in (-1, 101, True, float("nan")):
            with self.assertRaises(ValueError):
                build_supervisor_report(run(), value)

    def test_namespace_only_selection_is_supported(self):
        inventory = run()
        for resource in ("supervisor_summaries", "supervisor_conditions"):
            del inventory["resources"][("vc-a", "vcenter", resource)]
        self.assertEqual(build_supervisor_report(inventory)["status"], "success")

    def test_empty_run_is_partial(self):
        inventory = run()
        inventory["resources"] = {}
        self.assertEqual(build_supervisor_report(inventory)["status"], "partial")

    def test_report_does_not_change_source(self):
        inventory = run()
        original = copy.deepcopy(inventory)
        build_supervisor_report(inventory)
        self.assertEqual(inventory, original)


if __name__ == "__main__":
    unittest.main()
