"""Live-validation budgets, fixture boundaries and evidence. Author: Paul Bryant."""

import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vcf_inventory.http_client import ApiError, HttpClient
from vcf_inventory.live_validation import main, matrix_csv, response_shape, run_live_validation, shape_matches


def target(component="nsx", resources=None):
    return {"name": "private-manager-name", "component": component, "url": "https://private.example.test",
            "username_env": "TEST_USER", "password_env": "TEST_PASSWORD", "verify_tls": True,
            "resources": resources if resources is not None else ["segments"]}


class FakeClient:
    def __init__(self, configured, responses, session=False):
        self.target = configured
        self.responses = iter(responses)
        self.headers = {}
        self._product_state = {}
        self.collection_metadata = {}
        self.calls = []
        self.session = session

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/api/session":
            return "sensitive-authentication-token"
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def authenticate(self):
        if self.session:
            self.request("POST", "/api/session", body={"password": "sensitive-password"})

    def close(self):
        if self.session:
            self.request("DELETE", "/api/session")


class OfflineResponse:
    def __init__(self, document):
        self.document = document
        self.headers = {}

    def read(self, limit):
        return json.dumps(self.document).encode("utf-8")[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class LiveValidationTests(unittest.TestCase):
    def validate(self, configured, responses, **options):
        value = FakeClient(configured, responses, session=configured["component"] == "vcenter")
        factory = Mock(return_value=value)
        report = run_live_validation([configured], {"page_size": 1}, client_factory=factory, **options)
        self.assertEqual(factory.call_args.kwargs["retries"], 0)
        return report, value

    def test_real_nsx_pagination_and_numeric_build_evidence(self):
        report, value = self.validate(target(), [
            {"node_version": "9.1.0.0", "product_version": "9.1.0", "password": "private-value"},
            {"results": [{"id": "private-id"}], "result_count": 2, "cursor": "private-marker"},
            {"results": [{"id": "another-private-id"}]}], capture_fixtures=True)
        row = report["targets"][0]
        self.assertEqual(report["status"], "success")
        self.assertEqual(row["resources"][0]["observed_record_count"], 2)
        self.assertEqual(row["request_count"], 3)
        self.assertEqual(value.calls[-1][2]["params"]["cursor"], "private-marker")
        text = json.dumps(report)
        for private in ("private-id", "private-marker", "private-value", "private-manager-name", "private.example.test"):
            self.assertNotIn(private, text)
        self.assertEqual(len(report["fixtures"]), 2)
        self.assertIn("9.1.0", matrix_csv(report))

    def test_request_budget_stops_queries_but_still_closes_owned_session(self):
        configured = target("vcenter", ["clusters"])
        report, value = self.validate(configured, [{"version": "9.0.1", "build": "123456"}], max_requests=2)
        row = report["targets"][0]
        self.assertEqual(row["resources"][0]["status"], "request_budget_exhausted")
        self.assertEqual(row["request_count"], 2)
        self.assertEqual(row["cleanup_request_count"], 1)
        self.assertEqual(value.calls[-1][:2], ("DELETE", "/api/session"))
        self.assertEqual(report["status"], "partial")

    def test_page_limit_and_repeated_cursor_do_not_claim_complete_contract(self):
        for pages, responses in ((1, [{"results": [{"id": "x"}], "cursor": "same"}]),
                                 (3, [{"results": [{"id": "x"}], "cursor": "same"},
                                      {"results": [{"id": "y"}], "cursor": "same"}])):
            with self.subTest(pages=pages):
                report, _ = self.validate(target(), [{"node_version": "9.1"}] + responses, max_pages=pages)
                self.assertEqual(report["targets"][0]["resources"][0]["status"], "query_failure")
                self.assertEqual(report["status"], "partial")

    def test_version_failure_does_not_discard_valid_read(self):
        report, _ = self.validate(target(), [ApiError("private detail", status=403), {"results": []}])
        row = report["targets"][0]
        self.assertEqual(row["version"]["status"], "access_denied")
        self.assertEqual(row["resources"][0]["status"], "contract_validated")
        self.assertEqual(report["status"], "partial")
        self.assertNotIn("private detail", json.dumps(report))

    def test_configured_version_is_not_observed_build_evidence(self):
        configured = target()
        configured["version"] = "9.1"
        report, _ = self.validate(configured, [{"node_version": "private-hostname", "product_version": "secret"}, {"results": []}])
        self.assertEqual(report["targets"][0]["version"]["status"], "unknown")
        self.assertNotIn("private-hostname", json.dumps(report))

    def test_returned_partial_collector_metadata_cannot_validate_contract(self):
        def read(client, resource, **kwargs):
            client.get("/policy/api/v1/infra/segments")
            client.collection_metadata[resource] = {"coverage": "incomplete"}
            return []

        with patch("vcf_inventory.collectors.collect_resource", side_effect=read):
            report, _ = self.validate(target(), [{"node_version": "9.1"}, {"results": []}])
        self.assertEqual(report["targets"][0]["resources"][0]["status"], "query_failure")
        self.assertEqual(report["status"], "partial")

    def test_authorization_read_is_not_mistaken_for_authentication(self):
        configured = target("vcenter", ["authorization_permissions"])

        def read(client, resource, **kwargs):
            client.request("POST", "/api/vcenter/authorization/permissions", params={"action": "list"}, body={"iterate": {"page_size": 1}})
            return []

        with patch("vcf_inventory.collectors.collect_resource", side_effect=read):
            report, _ = self.validate(configured, [{"version": "9.1"}, {"permissions": [], "marker": None}], capture_fixtures=True)
        self.assertEqual(report["status"], "success")
        self.assertEqual(len(report["fixtures"]), 1)
        self.assertNotIn("sensitive-authentication-token", json.dumps(report))

    def test_hcx_version_read_uses_transport_allowlist_and_is_not_an_inventory_fixture(self):
        configured = target("hcx", ["appliances"])
        configured.update(auth_source="session_token", token_env="TEST_HCX_TOKEN")
        with patch.dict(os.environ, {"TEST_HCX_TOKEN": "private-hcx-session"}), \
                patch("vcf_inventory.http_client.build_opener") as opener:
            opener.return_value.open.side_effect = [
                OfflineResponse([{"systemName": "private-hcx-name", "version": "9.1.1.0.1234567"}]),
                OfflineResponse({"items": [{"applianceId": "private-appliance-id"}]}),
            ]
            report = run_live_validation([configured], {}, capture_fixtures=True)
            requests = [call.args[0] for call in opener.return_value.open.call_args_list]
        row = report["targets"][0]
        self.assertEqual(report["status"], "success")
        self.assertEqual(row["version"]["scope"], "local_hcx_manager")
        self.assertEqual(row["request_count"], 2)
        self.assertEqual(requests[0].method, "POST")
        self.assertEqual(requests[0].full_url, configured["url"] + "/hybridity/api/hcspAppliances")
        self.assertEqual(json.loads(requests[0].data), {"action": "query", "filter": {"local": "true"}})
        self.assertEqual(requests[1].method, "GET")
        self.assertEqual(len(report["fixtures"]), 1)
        self.assertEqual(report["fixtures"][0]["resource"], "appliances")
        self.assertEqual(report["fixtures"][0]["shape"]["kind"], "object")
        for private in ("private-hcx-session", "private-hcx-name", "private-appliance-id", "private.example.test"):
            self.assertNotIn(private, json.dumps(report))

    def test_hcx_version_transport_refuses_widened_queries_before_connection(self):
        configured = target("hcx", ["appliances"])
        good_body = {"action": "query", "filter": {"local": "true"}}
        forbidden = (
            ("POST", "/hybridity/api/hcspAppliances", None, {"action": "query", "filter": {"local": "true", "remote": "true"}}),
            ("POST", "/hybridity/api/hcspAppliances", None, {"action": "query", "filter": {"local": True}}),
            ("POST", "/hybridity/api/hcspAppliances", {"action": "query"}, good_body),
            ("POST", "/hybridity/api/upgrade", {"action": "getNotifications"}, {}),
            ("POST", "/hybridity/api/upgrade", {"action": "start"}, {}),
            ("PUT", "/hybridity/api/hcspAppliances", None, good_body),
        )
        with patch("vcf_inventory.http_client.build_opener") as opener:
            value = HttpClient(configured, retries=0)
            for method, path, params, body in forbidden:
                with self.subTest(method=method, path=path, params=params, body=body), self.assertRaises(ApiError):
                    value.request(method, path, params=params, body=body)
            opener.return_value.open.assert_not_called()

    def test_vsan_matrix_identifies_vcenter_build_separately_from_configured_schema(self):
        configured = target("vsan", ["health_summary"])
        configured.pop("username_env")
        configured.pop("password_env")
        configured.update(token_env="TEST_VSAN_TOKEN", api_version="9.0.0.0", cluster_ids=["domain-c123"])
        content = {"about": {"apiType": "VirtualCenter", "apiVersion": "9.1.1.0", "version": "9.1.1.0", "build": "1234567"},
                   "sessionManager": {"type": "SessionManager", "value": "SessionManager"}}
        with patch.dict(os.environ, {"TEST_VSAN_TOKEN": "private-vsan-session"}), \
                patch("vcf_inventory.http_client.build_opener") as opener:
            opener.return_value.open.side_effect = [OfflineResponse(content), OfflineResponse(content),
                                                    OfflineResponse({"overallHealth": "green", "overallHealthDescription": "Healthy"})]
            report = run_live_validation([configured], {})
            requests = [call.args[0] for call in opener.return_value.open.call_args_list]
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["targets"][0]["request_count"], 3)
        self.assertEqual(requests[1].full_url, configured["url"] + "/sdk/vim25/9.0.0.0/ServiceInstance/ServiceInstance/content")
        matrix, = csv.DictReader(io.StringIO(matrix_csv(report)))
        self.assertEqual(matrix["version_scope"], "vcenter_server_for_vsan")
        self.assertEqual(matrix["server_api_version"], "9.1.1.0")
        self.assertEqual(matrix["numeric_version_fields"], "build=1234567; version=9.1.1.0")
        self.assertNotIn("9.0.0.0", matrix["numeric_version_fields"])
        self.assertNotIn("private-vsan-session", json.dumps(report))

    def test_fleet_matrix_uses_system_current_version_and_validates_inventory_separately(self):
        configured = target("vcf_fleet", ["components"])
        configured.update(token_env="TEST_FLEET_TOKEN")
        with patch.dict(os.environ, {"TEST_FLEET_TOKEN": "private-fleet-token"}), \
                patch("vcf_inventory.http_client.build_opener") as opener:
            opener.return_value.open.side_effect = [
                OfflineResponse({"currentVersion": "9.1.1.0", "targetVersion": "9.2.0.0"}),
                OfflineResponse({"components": [], "pageMetadata": {"pageNumber": 1, "totalPages": 1, "totalElements": 0}}),
            ]
            report = run_live_validation([configured], {}, capture_fixtures=True)
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["targets"][0]["resources"][0]["status"], "contract_validated")
        self.assertEqual(len(report["fixtures"]), 1)
        matrix, = csv.DictReader(io.StringIO(matrix_csv(report)))
        self.assertEqual(matrix["version_scope"], "fleet_lcm_system")
        self.assertEqual(matrix["numeric_version_fields"], "currentVersion=9.1.1.0")
        self.assertEqual(matrix["server_api_version"], "")
        self.assertNotIn("9.2.0.0", matrix_csv(report))
        self.assertNotIn("private-fleet-token", json.dumps(report))

    def test_missing_explicit_scope_or_bad_limits_fail_before_connection(self):
        for options in ({"targets": [target(resources=[])]}, {"max_requests": 1}, {"max_pages": 0}):
            factory = Mock()
            arguments = {"targets": [target()], "config": {}, "client_factory": factory}
            arguments.update(options)
            with self.subTest(options=options), self.assertRaises(ValueError):
                run_live_validation(**arguments)
            factory.assert_not_called()

    def test_setup_failure_is_sanitized_and_matrix_records_not_checked(self):
        report = run_live_validation([target()], {}, client_factory=Mock(side_effect=ApiError("secret detail", category="tls")))
        self.assertEqual(report["targets"][0]["authentication"]["status"], "tls_error")
        self.assertNotIn("secret detail", json.dumps(report))
        self.assertIn("not_checked", matrix_csv(report))

    def test_shape_fixture_removes_dynamic_keys_and_all_scalar_values(self):
        payload = {"items": [{"name": "sensitive-name", "id": "sensitive-id", "port": 8443}],
                   "sensitive-address": {"token": "sensitive-token", "enabled": True}}
        fixture = response_shape(payload)
        saved = json.dumps(fixture)
        for sensitive in ("sensitive-name", "sensitive-id", "8443", "sensitive-address", "sensitive-token", "token"):
            self.assertNotIn(sensitive, saved)
        self.assertTrue(shape_matches(payload, fixture))
        self.assertTrue(shape_matches({"items": [{"name": "other", "id": "other", "port": 443}]}, fixture))
        self.assertFalse(shape_matches({"items": [{"name": 123, "id": "other", "port": 443}]}, fixture))
        self.assertLess(len(json.dumps(response_shape([payload] * 100, max_nodes=5))), 2000)

    def test_validate_config_is_offline_and_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text(json.dumps({"author": "Paul Bryant", "targets": [target()]}), encoding="utf-8")
            with patch("vcf_inventory.live_validation.run_live_validation") as run:
                code = main(["--config", str(config), "--output", str(root / "output"), "--validate-config"])
            self.assertEqual(code, 0)
            run.assert_not_called()
            self.assertFalse((root / "output").exists())

    def test_cli_writes_actual_inspectable_fixture_and_version_matrix(self):
        report, _ = self.validate(target(), [{"node_version": "9.1"}, {"results": [{"id": "sensitive-id"}]}], capture_fixtures=True)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text(json.dumps({"author": "Paul Bryant", "targets": [target()]}), encoding="utf-8")
            with patch("vcf_inventory.live_validation.run_live_validation", return_value=report):
                code = main(["--config", str(config), "--output", str(root / "output"), "--capture-fixtures"])
            self.assertEqual(code, 0)
            directory, = (root / "output").iterdir()
            saved = json.loads((directory / "validation.json").read_text(encoding="utf-8"))
            fixtures = json.loads((directory / "structural_fixtures.json").read_text(encoding="utf-8"))
            matrix = (directory / "tested_versions.csv").read_text(encoding="utf-8-sig")
            self.assertEqual(saved["status"], "success")
            self.assertNotIn("fixtures", saved)
            self.assertEqual(fixtures["author"], "Paul Bryant")
            self.assertEqual(len(fixtures["fixtures"]), 1)
            self.assertIn("node_version=9.1", matrix)
            for path in directory.iterdir():
                text = path.read_text(encoding="utf-8-sig")
                for sensitive in ("sensitive-id", "private-manager-name", "private.example.test", "TEST_PASSWORD"):
                    self.assertNotIn(sensitive, text)


if __name__ == "__main__":
    unittest.main()
