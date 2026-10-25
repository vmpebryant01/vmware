"""Version scope, read boundaries and privacy tests. Author: Paul Bryant."""

import json
import unittest
from unittest.mock import Mock

from vcf_inventory.http_client import ApiError
from vcf_inventory.version_probes import HCX_VERSION_PATH, VERSION_PROBES, allow_query, probe_version


class VersionProbeTests(unittest.TestCase):
    def probe(self, component, response, numeric_only=True, **options):
        client = Mock()
        if isinstance(response, Exception):
            client.request.side_effect = response
        else:
            client.request.return_value = response
        result = probe_version(client, {"component": component, **options}, numeric_only=numeric_only)
        self.assertLessEqual(client.request.call_count, 1)
        client.authenticate.assert_not_called()
        client.close.assert_not_called()
        return result, client

    def test_original_get_probes_retain_only_documented_numeric_fields(self):
        examples = {
            "sddc_manager": {"version": "9.1.1.0.1234567"},
            "vcenter": {"version": "9.1.1.00000", "build": "1234567"},
            "nsx": {"node_version": "9.1.1.0.0.1234567", "product_version": "9.1.1.0"},
            "vcf_operations": {"major": 9, "minor": 1, "minorMinor": 1, "patch": 0, "buildNumber": 1234567},
        }
        for component, expected in examples.items():
            with self.subTest(component=component):
                result, client = self.probe(component, {**expected, "name": "PRIVATE_NAME", "releaseName": "PRIVATE_RELEASE"})
                self.assertEqual(result["status"], "reported")
                self.assertEqual(result["fields"], expected)
                client.request.assert_called_once_with("GET", VERSION_PROBES[component][0])
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_fleet_reports_system_current_version_not_inventory_or_target_versions(self):
        result, client = self.probe("vcf_fleet", {
            "currentVersion": "9.1.1.0", "targetVersion": "9.2.0.0",
            "version": "9.9.9", "availableTargetVersions": ["9.3.0"],
            "components": [{"version": "8.18.1", "fqdn": "PRIVATE_COMPONENT"}],
        })
        self.assertEqual(result["fields"], {"currentVersion": "9.1.1.0"})
        self.assertEqual(result["scope"], "fleet_lcm_system")
        client.request.assert_called_once_with("GET", "/fleet-lcm/v1/system")

    def test_fleet_missing_current_version_is_unknown(self):
        result, _ = self.probe("vcf_fleet", {"targetVersion": "9.2.0.0", "version": "9.1.0.0"})
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("fields", result)

    def test_recovery_probes_local_servers_without_pairing_discovery_or_remote_login(self):
        for component, path, scope in (
            ("live_site_recovery", "/api/rest/srm/v2/server/info", "local_site_recovery_server"),
            ("vsphere_replication", "/api/rest/vr/v2/info", "local_replication_management_server"),
        ):
            with self.subTest(component=component):
                result, client = self.probe(component, {"version": "9.0.4", "build_number": "1234567",
                                                        "vc_name": "PRIVATE_VC", "certificates": [{"version": 3}]})
                self.assertEqual(result["fields"], {"version": "9.0.4", "build_number": "1234567"})
                self.assertEqual(result["scope"], scope)
                client.request.assert_called_once_with("GET", path)
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_recovery_partial_errors_are_query_failures_even_with_version(self):
        for metadata in ({"errors": [{"message": "PRIVATE_REMOTE_ERROR"}]}, ["invalid"]):
            with self.subTest(metadata=metadata):
                result, _ = self.probe("vsphere_replication", {"version": "9.1.1", "_meta": metadata})
                self.assertEqual(result["status"], "query_failure")
                self.assertNotIn("fields", result)
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_non_v2_recovery_gateway_is_not_probed(self):
        result, client = self.probe("live_site_recovery", {}, api_version="v1")
        self.assertEqual(result["status"], "unknown")
        client.request.assert_not_called()

    def test_hcx_query_is_exact_and_local_version_only(self):
        result, client = self.probe("hcx", [{"systemName": "PRIVATE_HCX", "systemType": "HCX Cloud", "version": "9.1.1.0.1234567"}])
        self.assertEqual(result["fields"], {"version": "9.1.1.0.1234567"})
        self.assertEqual(result["scope"], "local_hcx_manager")
        client.request.assert_called_once_with("POST", HCX_VERSION_PATH,
                                               body={"action": "query", "filter": {"local": "true"}})
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_hcx_no_or_multiple_local_managers_are_unknown(self):
        for response in ([], [{"version": "9.1.1"}, {"version": "9.0.0"}]):
            with self.subTest(response=response):
                result, _ = self.probe("hcx", response)
                self.assertEqual(result["status"], "unknown")
                self.assertNotIn("fields", result)

    def test_hcx_changed_envelope_does_not_use_generic_response_version(self):
        result, _ = self.probe("hcx", {"success": True, "version": "9.1.1", "items": [{"version": "9.0.0"}]})
        self.assertEqual(result["status"], "query_failure")
        self.assertNotIn("fields", result)

    def test_hcx_unverified_sso_contract_does_not_reuse_token_for_query(self):
        result, client = self.probe("hcx", [{"version": "9.1.1"}], auth_source="vcf_sso")
        self.assertEqual(result["status"], "unknown")
        client.request.assert_not_called()

    def test_hcx_query_allowlist_excludes_remote_discovery_and_upgrade_actions(self):
        good = {"action": "query", "filter": {"local": "true"}}
        self.assertTrue(allow_query("hcx", "POST", HCX_VERSION_PATH, None, good))
        self.assertTrue(allow_query("hcx", "POST", HCX_VERSION_PATH, {}, good))
        bad = (
            ("hcx", "PUT", HCX_VERSION_PATH, None, good),
            ("vcenter", "POST", HCX_VERSION_PATH, None, good),
            ("hcx", "POST", HCX_VERSION_PATH + "/", None, good),
            ("hcx", "POST", "/hybridity/api/upgrade", {"action": "getNotifications"}, good),
            ("hcx", "POST", HCX_VERSION_PATH, {"action": "query"}, good),
            ("hcx", "POST", HCX_VERSION_PATH, None, {**good, "pageSize": 1}),
            ("hcx", "POST", HCX_VERSION_PATH, None, {"action": "start", "filter": {"local": "true"}}),
            ("hcx", "POST", HCX_VERSION_PATH, None, {"action": "query", "filter": {"local": True}}),
            ("hcx", "POST", HCX_VERSION_PATH, None, {"action": "query", "filter": {"local": "true", "remote": "true"}}),
        )
        for arguments in bad:
            with self.subTest(arguments=arguments):
                self.assertFalse(allow_query(*arguments))

    def test_vsan_uses_configured_schema_but_reports_vcenter_product_build(self):
        result, client = self.probe("vsan", {"about": {"apiType": "VirtualCenter", "version": "9.1.1.0",
                                                         "build": "1234567", "apiVersion": "9.1.1.0", "instanceUuid": "PRIVATE_UUID"}},
                                    api_version="9.0.0.0")
        client.request.assert_called_once_with("GET", "/sdk/vim25/9.0.0.0/ServiceInstance/ServiceInstance/content")
        self.assertEqual(result["scope"], "vcenter_server_for_vsan")
        self.assertEqual(result["fields"], {"version": "9.1.1.0", "build": "1234567"})
        self.assertEqual(result["server_api_version"], "9.1.1.0")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertTrue(result["limitations"])

    def test_vsan_api_version_without_product_version_is_unknown(self):
        result, _ = self.probe("vsan", {"about": {"apiType": "VirtualCenter", "apiVersion": "9.1.1.0"}})
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("fields", result)

    def test_vsan_unapproved_schema_never_reaches_transport(self):
        for schema in ("9.1.1.0/../../", "10.0.0.0", None):
            with self.subTest(schema=schema):
                result, client = self.probe("vsan", {}, api_version=schema)
                self.assertEqual(result["status"], "unknown")
                client.request.assert_not_called()

    def test_vsan_host_agent_is_not_labeled_as_vcenter(self):
        result, _ = self.probe("vsan", {"about": {"apiType": "HostAgent", "version": "9.1.1"}})
        self.assertEqual(result["status"], "query_failure")
        self.assertNotIn("fields", result)

    def test_automation_api_family_versions_and_configured_product_version_are_not_observed_builds(self):
        for family in ("all_apps", "vm_apps", "provider"):
            with self.subTest(family=family):
                result, client = self.probe("vcf_automation", {"latestApiVersion": "9.1.1", "version": "9.1.1"},
                                            api_family=family, api_version="9.1.1", version="9.1.1")
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["scope"], "automation_product_build")
                self.assertNotIn("fields", result)
                client.request.assert_not_called()

    def test_remote_version_field_text_is_not_exported(self):
        rejected = ("PRIVATE_NAME", "9.1.1 PRIVATE_TOKEN", "9.1.1\nsecret", "https://PRIVATE_HOST", "9.1.1+PRIVATE", "9" * 129)
        for value in rejected:
            with self.subTest(value=value):
                result, _ = self.probe("vcenter", {"version": value, "name": "PRIVATE_NAME", "build": value})
                self.assertEqual(result["status"], "unknown")
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_numeric_only_rejects_numbered_hyphen_build_without_free_text_fallback(self):
        result, _ = self.probe("vcenter", {"build": "9.1.1-1234567"})
        self.assertEqual(result["status"], "unknown")
        result, _ = self.probe("vcenter", {"build": "9.1.1-1234567"}, numeric_only=False)
        self.assertEqual(result["fields"], {"build": "9.1.1-1234567"})

    def test_operations_booleans_floats_numeric_strings_and_out_of_range_integers_are_not_versions(self):
        for value in (True, 9.1, "9", -1, 2 ** 63):
            with self.subTest(value=value):
                result, _ = self.probe("vcf_operations", {"major": value, "releaseName": "9.1.1"})
                self.assertEqual(result["status"], "unknown")
                self.assertNotIn("fields", result)

    def test_malformed_static_payload_is_failure_not_empty_success(self):
        for response in ([], None, "9.1.1", 9):
            with self.subTest(response=response):
                result, _ = self.probe("live_site_recovery", response)
                self.assertEqual(result["status"], "query_failure")

    def test_errors_preserve_category_without_raw_messages_or_target_values(self):
        cases = ((401, None, "access_denied"), (403, None, "access_denied"),
                 (404, None, "endpoint_not_found"), (500, None, "query_failure"),
                 (None, "tls", "tls_error"), (None, "network", "network_error"),
                 (None, "request_budget", "request_budget_exhausted"))
        for status, category, expected in cases:
            with self.subTest(status=status, category=category):
                result, _ = self.probe("vcf_fleet", ApiError("PRIVATE_CREDENTIAL", status=status, category=category),
                                        name="PRIVATE_TARGET", url="https://PRIVATE_ENDPOINT")
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["scope"], "fleet_lcm_system")
                self.assertNotIn("PRIVATE", json.dumps(result))
                if status:
                    self.assertEqual(result["http_status"], status)

    def test_unknown_component_never_copies_its_name_or_configured_version(self):
        result, client = self.probe("PRIVATE_COMPONENT", {}, version="9.1.1")
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("PRIVATE", json.dumps(result))
        client.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
