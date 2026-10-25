"""Offline transport, configuration, and CLI integration tests. Author: Paul Bryant."""

import io
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

from vcf_inventory import cli
from vcf_inventory.collectors import collect_resource, resources_for
from vcf_inventory.config import ConfigError, load_config
from vcf_inventory.http_client import ApiError, HttpClient


class Response:
    def __init__(self, value=None, headers=None, empty=False):
        self.body = b"" if empty else json.dumps(value).encode("utf-8")
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self, maximum):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def target(component, **options):
    result = {"name": component, "component": component, "url": "https://inventory.example.test"}
    if component == "vcf_automation":
        result.update(api_family="all_apps", token_env="TEST_ACCESS_TOKEN")
    else:
        result.update(username_env="TEST_USERNAME", password_env="TEST_PASSWORD")
    result.update(options)
    return result


def request_details(client):
    return [(call.args[0].get_method(), urlsplit(call.args[0].full_url).path)
            for call in client.opener.open.call_args_list]


def headers(request):
    return {key.lower(): value for key, value in request.header_items()}


def failure(status):
    return HTTPError("https://inventory.example.test/inventory", status, "Simulated failure", {}, io.BytesIO(b""))


class ActualTransportIntegrationTests(unittest.TestCase):
    def client(self, component, responses=(), **options):
        client = HttpClient(target(component, **options), retries=0)
        client.opener = Mock()
        client.opener.open.side_effect = responses
        return client

    @patch.dict(os.environ, {"TEST_USERNAME": "reader", "TEST_PASSWORD": "example-password"})
    def test_hcx_auth_uses_lowercased_response_header_even_with_empty_body(self):
        client = self.client("hcx", [
            Response(empty=True, headers={"X-HM-Authorization": "example-session", "Content-Type": "application/json"}),
            Response({"items": [{"id": "profile-1"}]}),
        ])
        client.authenticate()
        self.assertEqual(collect_resource(client, "compute_profiles"), [{"id": "profile-1"}])
        self.assertEqual(request_details(client), [
            ("POST", "/hybridity/api/sessions"),
            ("GET", "/hybridity/api/interconnect/computeProfiles"),
        ])
        auth_request, inventory_request = [call.args[0] for call in client.opener.open.call_args_list]
        self.assertEqual(json.loads(auth_request.data), {"username": "reader", "password": "example-password"})
        self.assertEqual(headers(inventory_request)["x-hm-authorization"], "example-session")
        self.assertNotIn("authorization", headers(inventory_request))
        client.close()
        self.assertEqual(client.headers, {})
        self.assertEqual(len(request_details(client)), 2)

    def test_include_headers_preserves_json_payload_and_normalizes_header_names(self):
        client = self.client("hcx", [Response({"success": True}, {"X-HM-Authorization": "session", "X-Extra": "value"})])
        document, returned_headers = client.request("POST", "/hybridity/api/sessions", include_headers=True)
        self.assertEqual(document, {"success": True})
        self.assertEqual(returned_headers, {"x-hm-authorization": "session", "x-extra": "value"})

    def test_each_product_denies_non_inventory_mutations_and_other_products_auth(self):
        forbidden = {
            "hcx": [("POST", "/hybridity/api/cloudConfigs"), ("DELETE", "/hybridity/api/interconnect/serviceMesh"),
                    ("POST", "/suite-api/api/auth/token/acquire")],
            "vcf_operations": [("POST", "/suite-api/api/resources"), ("DELETE", "/suite-api/api/policies"),
                               ("POST", "/hybridity/api/sessions")],
            "vcf_automation": [("POST", "/blueprint/api/blueprints"), ("DELETE", "/deployment/api/deployments"),
                               ("POST", "/api/session")],
            "live_site_recovery": [("POST", "/api/rest/srm/v2/pairings/pair-1/recovery-management/plans"),
                                   ("DELETE", "/api/rest/srm/v2/pairings/pair-1/protection-management/groups"),
                                   ("POST", "/api/rest/vr/v2/session")],
            "vsphere_replication": [("POST", "/api/rest/vr/v2/pairings/pair-1/replications"),
                                    ("DELETE", "/api/rest/vr/v2/pairings/pair-1/replications"),
                                    ("POST", "/api/rest/srm/v2/session")],
        }
        for component, operations in forbidden.items():
            client = self.client(component)
            for method, path in operations:
                with self.subTest(component=component, method=method, path=path), self.assertRaises(ApiError):
                    client.request(method, path)
            client.opener.open.assert_not_called()

    def test_recovery_remote_login_allowlist_cannot_expand_to_path_or_encoding_variants(self):
        client = self.client("live_site_recovery")
        for path in (
            "/api/rest/srm/v2/pairings/a%2Fb/remote-session",
            "/api/rest/srm/v2/pairings/a%252Fb/remote-session",
            "/api/rest/srm/v2/pairings/../remote-session",
            "/api/rest/srm/v2/pairings/a/remote-session/extra",
            "/api/rest/srm/v2/pairings/a/remote-session?other=value",
        ):
            with self.subTest(path=path), self.assertRaises(ApiError):
                client.request("POST", path)
        client.opener.open.assert_not_called()

    @patch.dict(os.environ, {
        "TEST_USERNAME": "reader", "TEST_PASSWORD": "local-password",
        "TEST_REMOTE_USERNAME": "remote-reader", "TEST_REMOTE_PASSWORD": "remote-password",
    })
    def test_pair_scoped_401_fails_without_reauthenticating_or_losing_cleanup_session(self):
        client = self.client("live_site_recovery", [
            Response({"session_id": "owned-session"}),
            Response({"list": [{"pairing_id": "pair-1"}], "_meta": {"total": 1}}),
            Response(empty=True),
            failure(401),
            Response(empty=True),
        ], resources=["protection_groups"], pairing_id="pair-1",
            remote_username_env="TEST_REMOTE_USERNAME", remote_password_env="TEST_REMOTE_PASSWORD")
        client.authenticate()
        with self.assertRaises(ApiError) as caught:
            collect_resource(client, "protection_groups")
        self.assertEqual(caught.exception.status, 401)
        client.close()
        self.assertEqual(request_details(client), [
            ("POST", "/api/rest/srm/v2/session"),
            ("GET", "/api/rest/srm/v2/pairings"),
            ("POST", "/api/rest/srm/v2/pairings/pair-1/remote-session"),
            ("GET", "/api/rest/srm/v2/pairings/pair-1/protection-management/groups"),
            ("DELETE", "/api/rest/srm/v2/session"),
        ])
        self.assertEqual(headers(client.opener.open.call_args.args[0])["x-dr-session"], "owned-session")
        self.assertEqual(client.headers, {})
        self.assertEqual(client._product_state, {})

    @patch.dict(os.environ, {"TEST_ACCESS_TOKEN": "example-token"})
    def test_external_automation_token_401_does_not_attempt_exchange_or_second_get(self):
        client = self.client("vcf_automation", [failure(401)])
        client.authenticate()
        with self.assertRaises(ApiError):
            collect_resource(client, "projects")
        client.close()
        self.assertEqual(request_details(client), [("GET", "/project-service/api/projects")])
        self.assertEqual(client.headers, {})

    @patch.dict(os.environ, {"TEST_ACCESS_TOKEN": "example-token"})
    def test_external_operations_token_is_not_released(self):
        client = self.client("vcf_operations", token_env="TEST_ACCESS_TOKEN", token_scheme="Bearer")
        client.target.pop("username_env")
        client.target.pop("password_env")
        client.authenticate()
        self.assertEqual(client.headers["Authorization"], "Bearer example-token")
        client.close()
        client.opener.open.assert_not_called()
        self.assertEqual(client._product_state, {})

    @patch.dict(os.environ, {"TEST_USERNAME": "reader", "TEST_PASSWORD": "example-password"})
    def test_owned_operations_token_is_released_and_cleared_even_if_release_fails(self):
        client = self.client("vcf_operations", [Response({"token": "owned-token"}), failure(403)])
        client.authenticate()
        with self.assertRaises(ApiError):
            client.close()
        self.assertEqual(request_details(client), [
            ("POST", "/suite-api/api/auth/token/acquire"),
            ("POST", "/suite-api/api/auth/token/release"),
        ])
        self.assertEqual(client.headers, {})
        self.assertEqual(client._product_state, {})


class ConfigurationAndScopeIntegrationTests(unittest.TestCase):
    def load(self, targets):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"author": "Paul Bryant", "targets": targets}), encoding="utf-8")
            return load_config(path)

    def test_all_external_token_configs_validate_without_credentials_or_network(self):
        targets = [
            target("hcx", auth_source="session_token", token_env="TEST_ACCESS_TOKEN"),
            target("vcf_operations", token_env="TEST_ACCESS_TOKEN", token_scheme="Bearer"),
            target("vcf_automation"),
            target("live_site_recovery", auth_source="session_token", token_env="TEST_ACCESS_TOKEN"),
            target("vsphere_replication", auth_source="session_token", token_env="TEST_ACCESS_TOKEN"),
        ]
        for item in targets:
            item.pop("username_env", None)
            item.pop("password_env", None)
        with patch.dict(os.environ, {}, clear=True), patch("vcf_inventory.http_client.build_opener") as opener:
            parsed = self.load(targets)
        self.assertEqual(len(parsed["targets"]), 5)
        opener.assert_not_called()

    def test_automation_provider_selection_uses_provider_defaults_and_rejects_vm_app_resources(self):
        provider = target("vcf_automation", api_family="provider", api_version="9.1.1")
        parsed = self.load([provider])["targets"][0]
        self.assertEqual(resources_for(parsed), [
            "organizations", "regions", "provider_zones", "supervisor_namespaces", "virtual_private_clouds"])
        provider["resources"] = ["cloud_accounts"]
        with self.assertRaises(ConfigError):
            self.load([provider])
        with self.assertRaises(ConfigError):
            self.load([target("vcf_automation", api_family="provider")])

    def test_product_options_cannot_be_silently_applied_to_other_components(self):
        for item in (
            target("hcx", api_family="provider"),
            target("vcf_operations", org_id="organization"),
            target("sddc_manager", api_version="9.1.1"),
            target("nsx", token_env="TOKEN"),
        ):
            with self.subTest(component=item["component"]), self.assertRaises(ConfigError):
                self.load([item])

    def test_scoped_cli_collects_only_in_scope_targets_and_uses_family_defaults(self):
        configured = [target("hcx"), target("vcf_automation", api_family="provider", api_version="9.1.1")]
        client = Mock()
        snapshots = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"author": "Paul Bryant", "targets": configured}), encoding="utf-8")
            with patch.object(cli, "HttpClient", return_value=client) as factory, \
                    patch.object(cli, "collect_resource", return_value=[]) as collect, \
                    patch.object(cli, "write_resource") as export, \
                    patch.object(cli, "write_json", side_effect=lambda path, data: snapshots.append(json.loads(json.dumps(data)))), \
                    patch.object(cli.Path, "mkdir"), \
                    patch("sys.stdout", new_callable=io.StringIO), \
                    patch("sys.stderr", new_callable=io.StringIO):
                status = cli.main(["--config", str(path)], component_scope=("vcf_automation",))
        self.assertEqual(status, 0)
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args[0]["component"], "vcf_automation")
        self.assertEqual([call.args[1] for call in collect.call_args_list], [
            "organizations", "regions", "provider_zones", "supervisor_namespaces", "virtual_private_clouds"])
        self.assertEqual(export.call_count, 5)
        self.assertEqual(export.call_args.args[3]["api_family"], "provider")
        self.assertEqual(export.call_args.args[3]["api_version"], "9.1.1")
        self.assertEqual([item["component"] for item in snapshots[-1]["targets"]], ["vcf_automation"])
        client.close.assert_called_once_with()

    def test_scoped_cli_rejects_outside_component_before_creating_client(self):
        with patch.object(cli, "HttpClient") as factory, patch("sys.stderr", new_callable=io.StringIO):
            status = cli.main(["--config", "unused.json", "--component", "vcf_automation"], component_scope=("hcx",))
        self.assertEqual(status, 1)
        factory.assert_not_called()

    def test_scoped_list_resources_needs_no_configuration_or_client(self):
        with patch.object(cli, "HttpClient") as factory, patch("sys.stdout", new_callable=io.StringIO) as output:
            status = cli.main(["--list-resources"], component_scope=("live_site_recovery", "vsphere_replication"))
        self.assertEqual(status, 0)
        self.assertEqual(set(json.loads(output.getvalue())), {"live_site_recovery", "vsphere_replication"})
        factory.assert_not_called()

    def test_product_wrapper_entrypoints_pass_the_expected_scope(self):
        expected = {
            "collect_hcx.py": ("hcx",),
            "collect_nsx.py": ("nsx",),
            "collect_vcf.py": ("sddc_manager", "vcenter"),
            "collect_vcf_operations.py": ("vcf_operations",),
            "collect_vcf_automation.py": ("vcf_automation",),
            "collect_vcf_protection_recovery.py": ("live_site_recovery", "vsphere_replication"),
        }
        for filename, scope in expected.items():
            with self.subTest(filename=filename), patch.object(cli, "main", return_value=0) as entry:
                with self.assertRaises(SystemExit) as result:
                    runpy.run_path(str(Path(__file__).resolve().parents[1] / filename), run_name="__main__")
                self.assertEqual(result.exception.code, 0)
                entry.assert_called_once_with(component_scope=scope)


if __name__ == "__main__":
    unittest.main()
