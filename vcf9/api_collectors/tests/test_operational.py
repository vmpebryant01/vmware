"""Offline operational resource and field-boundary tests. Author: Paul Bryant."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from vcf_inventory import operational
from vcf_inventory.http_client import ApiError


def page(rows, number=0, total=None, pages=None):
    metadata = {"pageNumber": number}
    if total is not None:
        metadata["totalElements"] = total
    if pages is not None:
        metadata["totalPages"] = pages
    return {"elements": rows, "pageMetadata": metadata}


class Client:
    def __init__(self, component, responses=(), **options):
        self.target = {"component": component, **options}
        self.get = Mock(side_effect=list(responses))
        self.request = Mock()
        self.headers = {"x-dr-session": "example-session"}
        self._product_state = {}


class OperationalValidationTests(unittest.TestCase):
    def test_optional_resources_preserve_defaults_and_component_boundaries(self):
        self.assertEqual(operational.DEFAULT_RESOURCES, {})
        self.assertTrue(operational.supports("sddc_manager", "certificates"))
        self.assertTrue(operational.supports("live_site_recovery", "network_mappings"))
        self.assertFalse(operational.supports("vsphere_replication", "network_mappings"))
        self.assertFalse(operational.supports("hcx", "certificates"))
        self.assertEqual(operational.ALLOWED_OPERATIONS, set())

    def test_thresholds_require_bounded_integers(self):
        for key in ("task_days", "certificate_attention_days"):
            for value in (True, 0, 3651, 1.0, "30"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    operational.validate_target({"component": "sddc_manager", key: value})

    def test_scoped_identifier_lists_are_required_and_cannot_escape_paths(self):
        invalid = (None, [], ["safe", "safe"], ["../outside"], ["id/other"], ["encoded%2Fpath"], [True], [{}])
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                operational.validate_target({"component": "nsx", "resources": ["security_rules"], "policy_ids": value})
        with self.assertRaises(ValueError):
            operational.validate_target({"component": "live_site_recovery", "resources": ["folder_mappings"], "srm_ids": ["srm-1"]})
        with self.assertRaises(ValueError):
            operational.validate_target({"component": "vcf_automation", "resources": ["catalog_items"], "api_family": "provider"})

    def test_operational_options_reject_wrong_components(self):
        for component, key, value in (
            ("hcx", "task_days", 30), ("nsx", "domain_ids", ["d1"]),
            ("sddc_manager", "policy_ids", ["p1"]), ("vsphere_replication", "srm_ids", ["s1"]),
        ):
            with self.subTest(component=component, key=key), self.assertRaises(ValueError):
                operational.validate_target({"component": component, key: value})

    def test_runtime_validation_prevents_network_for_missing_scope(self):
        client = Client("nsx")
        with self.assertRaises(ApiError):
            operational.collect_resource(client, "security_rules")
        client.get.assert_not_called()


class CertificateAndTaskTests(unittest.TestCase):
    def test_certificates_discover_domains_and_export_only_metadata(self):
        first = {"resourceName": "vcenter", "resourceType": "VCENTER", "issuedTo": "vc.example.test",
                 "numberOfDaysToExpire": 7, "isInstalled": True, "expirationStatus": "ACTIVE",
                 "pemEncoded": "DO NOT EXPORT", "caChain": [{"pemEncoded": "DO NOT EXPORT"}],
                 "autoRenewFailureMessage": "DO NOT EXPORT"}
        second = {"resourceName": "nsx", "numberOfDaysToExpire": -3, "isInstalled": False,
                  "expirationStatus": "EXPIRED"}
        client = Client("sddc_manager", [
            page([{"id": "domain-1", "name": "Management"}, {"id": "domain-2", "name": "Workload"}], total=2),
            page([first], total=1), page([second], total=1),
        ], certificate_attention_days=14)
        rows = operational.collect_resource(client, "certificates")
        self.assertEqual([row["domain_id"] for row in rows], ["domain-1", "domain-2"])
        self.assertEqual(rows[0]["domain"], "Management")
        self.assertTrue(rows[0]["attention"])
        self.assertFalse(rows[1]["attention"])
        self.assertEqual(rows[0]["attentionThresholdDays"], 14)
        self.assertNotIn("DO NOT EXPORT", str(rows))
        self.assertNotIn("pemEncoded", rows[0])
        self.assertEqual([call.args[0] for call in client.get.call_args_list], [
            "/v1/domains", "/v1/domains/domain-1/resource-certificates", "/v1/domains/domain-2/resource-certificates"])

    def test_explicit_domain_scope_skips_domain_discovery_and_boolean_days_are_unknown(self):
        client = Client("sddc_manager", [page([{"numberOfDaysToExpire": True, "isInstalled": True}], total=1)],
                        domain_ids=["domain-1"])
        row = operational.collect_resource(client, "certificates")[0]
        self.assertIsNone(row["numberOfDaysToExpire"])
        self.assertFalse(row["attention"])
        self.assertEqual(client.get.call_args.args[0], "/v1/domains/domain-1/resource-certificates")
        self.assertEqual(client.get.call_count, 1)

    def test_failed_tasks_use_fixed_millisecond_window_and_maximum_page_size_100(self):
        fixed = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
        client = Client("sddc_manager", [
            page([{"id": "t1", "status": "Failed", "name": "Task", "errors": "DO NOT EXPORT"}], total=2, pages=2),
            page([{"id": "t2", "status": "Successful"}], number=1, total=2, pages=2),
        ], task_days=7)
        with patch.object(operational, "_utc_now", return_value=fixed):
            rows = operational.collect_resource(client, "failed_tasks", page_size=1000)
        cutoff = int((fixed - timedelta(days=7)).timestamp() * 1000)
        self.assertEqual([row["id"] for row in rows], ["t1"])
        self.assertEqual(rows[0]["tasksCompletedAfterEpochMs"], cutoff)
        self.assertEqual(rows[0]["taskWindowDays"], 7)
        self.assertNotIn("DO NOT EXPORT", str(rows))
        self.assertEqual([call.kwargs["params"] for call in client.get.call_args_list], [
            {"completedAfter": cutoff, "pageNumber": 0, "pageSize": 100},
            {"completedAfter": cutoff, "pageNumber": 1, "pageSize": 100},
        ])

    def test_failure_in_any_domain_prevents_successful_partial_certificate_result(self):
        client = Client("sddc_manager", [
            page([{"resourceName": "first"}], total=1),
            {"elements": [], "pageMetadata": {"totalElements": 2}},
        ], domain_ids=["domain-1", "domain-2"])
        with self.assertRaises(ApiError):
            operational.collect_resource(client, "certificates")


class FirewallAndCatalogTests(unittest.TestCase):
    def test_firewall_rule_cursors_and_explicit_policy_scopes_preserve_selected_columns(self):
        client = Client("nsx", [
            {"results": [{"id": "r1", "action": "ALLOW", "source_groups": ["DO NOT EXPORT"]}], "cursor": "opaque+/=", "result_count": 2},
            {"results": [{"id": "r2", "action": "DROP"}]},
            {"results": [{"id": "r1", "action": "REJECT"}], "result_count": 1},
        ], domain_id="default", policy_ids=["policy-1", "policy-2"])
        rows = operational.collect_resource(client, "security_rules")
        self.assertEqual([row["policy_id"] for row in rows], ["policy-1", "policy-1", "policy-2"])
        self.assertEqual(client.get.call_args_list[1].kwargs["params"]["cursor"], "opaque+/=")
        self.assertNotIn("DO NOT EXPORT", str(rows))
        self.assertNotIn("source_groups", rows[0])
        self.assertTrue(all(call.args[0].startswith("/policy/api/v1/infra/domains/default/") for call in client.get.call_args_list))

    def test_catalog_works_for_both_tenant_families_and_omits_user_and_schema_data(self):
        for family in ("all_apps", "vm_apps"):
            client = Client("vcf_automation", [{
                "content": [{"id": "item-1", "name": "Catalog", "isRequestable": True, "global": False,
                             "projectIds": ["p1", "p2"], "schema": {"secret": "DO NOT EXPORT"},
                             "creator": {"email": "DO NOT EXPORT"}}],
                "number": 0, "totalElements": 1, "totalPages": 1, "last": True,
            }], api_family=family)
            with self.subTest(family=family):
                row = operational.collect_resource(client, "catalog_items")[0]
                self.assertEqual(row["visibleProjectCount"], 2)
                self.assertTrue(row["isRequestable"])
                self.assertFalse(row["global"])
                self.assertNotIn("DO NOT EXPORT", str(row))
                self.assertEqual(client.get.call_args.args[0], "/catalog/api/items")

    def test_missing_catalog_project_ids_are_unknown_instead_of_zero(self):
        client = Client("vcf_automation", [{"content": [{"id": "item"}], "totalElements": 1}], api_family="vm_apps")
        self.assertIsNone(operational.collect_resource(client, "catalog_items")[0]["visibleProjectCount"])

    def test_repeated_cursor_count_mismatch_and_catalog_page_repetition_fail(self):
        examples = (
            ("nsx", "security_rules", {"policy_ids": ["policy"]}, [
                {"results": [{"id": "a"}], "cursor": "same"}, {"results": [{"id": "b"}], "cursor": "same"}]),
            ("nsx", "security_rules", {"policy_ids": ["policy"]}, [
                {"results": [{"id": "a"}], "result_count": 2}]),
            ("vcf_automation", "catalog_items", {"api_family": "vm_apps"}, [
                {"content": [{"id": "a"}]}, {"content": [{"id": "a"}]}]),
        )
        for component, resource, options, responses in examples:
            with self.subTest(resource=resource), self.assertRaises(ApiError):
                operational.collect_resource(Client(component, responses, **options), resource)


class RecoveryAndCollectorTests(unittest.TestCase):
    def test_all_mapping_kinds_use_explicit_pairing_srm_and_allowlisted_fields(self):
        for resource, suffix in operational.RECOVERY_SUFFIXES.items():
            item = {"id": "m1", "primary_object_name": "source", "secondary_object_name": "target",
                    "target_network": "target", "test_network_name": "isolated", "extra": "DO NOT EXPORT"}
            client = Client("live_site_recovery", [
                {"list": [{"pairing_id": "pair-1"}], "_meta": {"total": 1}},
                {"list": [item], "_meta": {"total": 1}},
            ], auth_source="session_token", pairing_id="pair-1", srm_ids=["srm-1"])
            with self.subTest(resource=resource):
                row = operational.collect_resource(client, resource)[0]
                self.assertEqual((row["pairing_id"], row["srm_id"]), ("pair-1", "srm-1"))
                self.assertNotIn("DO NOT EXPORT", str(row))
                self.assertEqual(client.get.call_args.args[0], f"/api/rest/srm/v2/pairings/pair-1/srms/srm-1/inventory-mappings/{suffix}")
                client.request.assert_not_called()

    @patch.dict("os.environ", {"REMOTE_USERNAME": "reader", "REMOTE_PASSWORD": "example-password"})
    def test_mapping_remote_login_reuses_current_session_and_paginates_offsets(self):
        client = Client("live_site_recovery", [
            {"list": [{"pairing_id": "pair-1"}], "_meta": {"total": 1}},
            {"list": [{"id": "m1"}], "_meta": {"offset": 0, "total": 2}},
            {"list": [{"id": "m2"}], "_meta": {"offset": 1, "total": 2}},
        ], pairing_id="pair-1", srm_ids=["srm-1"], remote_username_env="REMOTE_USERNAME", remote_password_env="REMOTE_PASSWORD")
        rows = operational.collect_resource(client, "folder_mappings")
        self.assertEqual(len(rows), 2)
        self.assertEqual([call.kwargs["params"]["offset"] for call in client.get.call_args_list[1:]], [0, 1])
        client.request.assert_called_once()
        self.assertEqual(client.request.call_args.args, ("POST", "/api/rest/srm/v2/pairings/pair-1/remote-session"))

    def test_recovery_partial_errors_and_wrong_scope_are_not_exported(self):
        for response in (
            {"list": [{"id": "m"}], "_meta": {"total": 1, "errors": [{"message": "error"}]}},
            {"list": [{"id": "m", "pairing_id": "other"}], "_meta": {"total": 1}},
            {"list": [{"id": "m", "srm_id": "other"}], "_meta": {"total": 1}},
        ):
            client = Client("live_site_recovery", [
                {"list": [{"pairing_id": "pair-1"}], "_meta": {"total": 1}}, response,
            ], pairing_id="pair-1", srm_ids=["srm-1"])
            with self.subTest(response=response), self.assertRaises(ApiError):
                operational.collect_resource(client, "folder_mappings")

    def test_operations_collectors_export_status_without_adapter_inventory(self):
        client = Client("vcf_operations", [{"collector": [
            {"id": "1", "name": "Local", "state": "UP", "local": True, "adapterInstanceIds": ["DO NOT EXPORT"]}
        ]}])
        row = operational.collect_resource(client, "collectors")[0]
        self.assertEqual(row["state"], "UP")
        self.assertNotIn("DO NOT EXPORT", str(row))
        client.get.assert_called_once_with("/suite-api/api/collectors")


if __name__ == "__main__":
    unittest.main()
