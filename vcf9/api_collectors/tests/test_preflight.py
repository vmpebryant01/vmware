"""Offline preflight scope, failure, and data-boundary tests. Author: Paul Bryant."""

import json
import unittest
from unittest.mock import Mock

from vcf_inventory.http_client import ApiError
from vcf_inventory.preflight import run_preflight


def target(component="nsx", resources=None, **options):
    result = {"name": "test-target", "component": component, "url": "https://inventory.example.test"}
    if resources is not None:
        result["resources"] = resources
    result.update(options)
    return result


def client(responses=(), auth_error=None, cleanup_error=None):
    value = Mock()
    value.headers = {}
    value._product_state = {}
    value.request.side_effect = list(responses)
    if auth_error:
        value.authenticate.side_effect = auth_error
    if cleanup_error:
        value.close.side_effect = cleanup_error
    return value


def categorized_error(category):
    value = ApiError("Sensitive detail must not be exported")
    value.category = category
    return value


class PreflightTests(unittest.TestCase):
    def run_probe(self, configured, value):
        return run_preflight([configured], {"timeout_seconds": 9, "retries": 0}, client_factory=Mock(return_value=value))

    def test_public_nsx_version_does_not_prove_authentication(self):
        value = client([{"node_version": "9.1.1", "product_version": "9.1.1", "credentials": "DO NOT EXPORT"}])
        result = self.run_probe(target(resources=[]), value)["targets"][0]
        self.assertEqual(result["version"]["fields"], {"node_version": "9.1.1", "product_version": "9.1.1"})
        self.assertEqual(result["authentication"]["status"], "configured")
        self.assertEqual(result["tls"], "verified")
        self.assertNotIn("DO NOT EXPORT", json.dumps(result))
        value.request.assert_called_once_with("GET", "/api/v1/node")
        value.close.assert_called_once_with()

    def test_protected_nsx_probe_verifies_auth_and_requests_only_first_page(self):
        value = client([{"node_version": "9.1.1"}, {"results": [{"password": "DO NOT EXPORT"}]}])
        result = self.run_probe(target(resources=["segments"]), value)["targets"][0]
        self.assertEqual(result["authentication"]["status"], "verified")
        self.assertEqual(result["capabilities"][0]["status"], "accessible")
        self.assertEqual(value.request.call_args.args, ("GET", "/policy/api/v1/infra/segments"))
        self.assertEqual(value.request.call_args.kwargs["params"], {"page_size": 1})
        self.assertNotIn("DO NOT EXPORT", json.dumps(result))

    def test_version_access_error_does_not_block_protected_resource_probe(self):
        value = client([ApiError("Denied", status=403), []])
        result = self.run_probe(target("vcenter", ["clusters"]), value)
        row = result["targets"][0]
        self.assertEqual(row["version"]["status"], "access_denied")
        self.assertEqual(row["capabilities"][0]["status"], "accessible")
        self.assertEqual(row["authentication"]["status"], "verified")
        self.assertEqual(result["status"], "incomplete")

    def test_404_is_endpoint_not_found_instead_of_unsupported(self):
        value = client([{"node_version": "9.1.1"}, ApiError("Missing", status=404)])
        row = self.run_probe(target(resources=["segments"]), value)["targets"][0]
        self.assertEqual(row["capabilities"][0]["status"], "endpoint_not_found")
        self.assertNotIn("unsupported", json.dumps(row))

    def test_tls_and_network_error_categories_are_distinct_and_not_raw_messages(self):
        for category, expected, field in (("tls", "tls_error", "tls"), ("network", "network_error", "connectivity")):
            factory = Mock(side_effect=categorized_error(category))
            with self.subTest(category=category):
                report = run_preflight([target(resources=["segments"])], {}, client_factory=factory)
                row = report["targets"][0]
                self.assertEqual(row["authentication"]["status"], expected)
                self.assertEqual(row[field], "error")
                self.assertNotIn("Sensitive detail", json.dumps(report))

    def test_authentication_failure_leaves_capability_not_probed_and_still_closes_client(self):
        value = client([{"node_version": "9.1.1"}], auth_error=ApiError("Denied", status=401))
        row = self.run_probe(target(resources=["segments"]), value)["targets"][0]
        self.assertEqual(row["authentication"]["status"], "access_denied")
        self.assertEqual(row["capabilities"][0]["status"], "not_probed")
        self.assertEqual(value.request.call_count, 1)
        value.close.assert_called_once_with()

    def test_missing_certificate_scope_is_not_discovered(self):
        value = client([{"version": "9.1.1"}])
        row = self.run_probe(target("sddc_manager", ["certificates"]), value)["targets"][0]
        self.assertEqual(row["capabilities"][0]["status"], "not_probed")
        self.assertEqual(value.request.call_count, 1)
        self.assertTrue(row["scope_limits"])
        self.assertEqual(row["status"], "partial")

    def test_fleet_components_are_protected_first_page_without_node_discovery(self):
        value = client([{"components": []}])
        row = self.run_probe(target("vcf_fleet", ["components", "component_nodes"], token_env="TOKEN", version="operator-entry"), value)["targets"][0]
        self.assertEqual(row["authentication"]["status"], "verified")
        self.assertEqual(row["configured_version"], "operator-entry")
        self.assertEqual(row["version"]["status"], "not_probed")
        self.assertEqual(row["status"], "partial")
        self.assertEqual(value.request.call_count, 1)
        self.assertEqual(value.request.call_args.args, ("GET", "/fleet-lcm/v1/components"))
        self.assertEqual(value.request.call_args.kwargs["params"], {
            "pageNumber": 1, "pageSize": 1, "includeConsumptionVsp": "true", "includeVcdMigrator": "true"})

    def test_version_endpoint_alone_does_not_verify_external_token(self):
        value = client([{"major": 9, "minor": 1, "minorMinor": 1}])
        report = self.run_probe(target("vcf_operations", [], token_env="TOKEN"), value)
        self.assertEqual(report["targets"][0]["authentication"]["status"], "configured")
        self.assertTrue(report["started_at"].endswith("Z"))
        self.assertTrue(report["completed_at"].endswith("Z"))

    def test_explicit_policy_scope_probes_only_first_policy(self):
        value = client([{"node_version": "9.1.1"}, {}])
        row = self.run_probe(target(resources=["security_rules"], domain_id="default", policy_ids=["p1", "p2"]), value)["targets"][0]
        self.assertEqual(row["capabilities"][0]["status"], "accessible")
        self.assertEqual(value.request.call_args.args[1], "/policy/api/v1/infra/domains/default/security-policies/p1/rules")
        self.assertEqual(value.request.call_count, 2)

    def test_external_automation_provider_uses_one_based_probe_and_unknown_product_version(self):
        value = client([{"values": []}])
        configured = target("vcf_automation", ["organizations"], api_family="provider", api_version="9.1.1", token_env="TOKEN")
        row = self.run_probe(configured, value)["targets"][0]
        self.assertEqual(row["version"]["status"], "not_probed")
        self.assertEqual(value.request.call_args.kwargs["params"], {"page": 1, "pageSize": 1})
        self.assertEqual(value.request.call_count, 1)

    def test_metrics_probe_uses_one_explicit_resource_and_key(self):
        value = client([{"major": 9, "minor": 1, "minorMinor": 1, "releaseName": "VCF Operations"}, {}])
        row = self.run_probe(target("vcf_operations", ["latest_metrics"], token_env="TOKEN", resource_ids=["a", "b"], stat_keys=["cpu|usage", "mem|usage"]), value)["targets"][0]
        self.assertEqual(row["capabilities"][0]["status"], "accessible")
        self.assertEqual(value.request.call_args.kwargs["params"], {"resourceId": ["a"], "statKey": ["cpu|usage"], "maxSamples": 1})
        self.assertEqual(value.request.call_count, 2)

    def test_missing_pairing_scope_is_not_discovered(self):
        value = client()
        row = self.run_probe(target("live_site_recovery", ["recovery_plans"], auth_source="session_token"), value)["targets"][0]
        self.assertEqual(row["capabilities"][0]["status"], "not_probed")
        value.request.assert_not_called()

    def test_cleanup_error_is_reported_without_response_or_exception_details(self):
        value = client([{"node_version": "9.1.1"}], cleanup_error=ApiError("Sensitive detail", status=403))
        report = self.run_probe(target(resources=[]), value)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["targets"][0]["session_cleanup"]["status"], "access_denied")
        self.assertNotIn("Sensitive detail", json.dumps(report))

    def test_factory_receives_timeout_and_retry_configuration(self):
        value = client()
        factory = Mock(return_value=value)
        configured = target("hcx", ["compute_profiles"], auth_source="session_token")
        value.request.side_effect = [{}]
        report = run_preflight([configured], {"timeout_seconds": 9, "retries": 0}, client_factory=factory)
        factory.assert_called_once_with(configured, timeout=9, retries=0)
        self.assertEqual(report["author"], "Paul Bryant")
        self.assertIn("multiple records", report["targets"][0]["capabilities"][0]["scope_limit"])


if __name__ == "__main__":
    unittest.main()
