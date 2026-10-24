"""Offline behavioral tests for the inventory toolkit.

Author: Paul Bryant
"""

import base64
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request

from vcf_inventory.collectors import collect_resource
from vcf_inventory.config import ConfigError, load_config
from vcf_inventory.exports import sanitize, write_resource
from vcf_inventory.http_client import ApiError, HttpClient


class JsonResponse:
    """Minimal local response compatible with urllib's response interface."""

    def __init__(self, value, status=200):
        self.body = json.dumps(value).encode("utf-8")
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    def read(self, amount=-1):
        return self.body

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def target(component="sddc_manager", **overrides):
    value = {
        "component": component,
        "name": "test-target",
        "url": "https://inventory.example.test",
        "username_env": "TEST_INVENTORY_USERNAME",
        "password_env": "TEST_INVENTORY_PASSWORD",
    }
    value.update(overrides)
    return value


def normalized_headers(request):
    return {key.lower(): value for key, value in request.header_items()}


class TransportTests(unittest.TestCase):
    def client(self, component="sddc_manager", responses=()):
        client = HttpClient(target(component), retries=0)
        client.opener = Mock()
        client.opener.open.side_effect = [JsonResponse(value) for value in responses]
        return client

    def test_get_encodes_query_without_changing_origin(self):
        client = self.client(responses=[{"elements": []}])
        result = client.get("/v1/domains", params={"pageNumber": 0, "pageSize": 25})
        self.assertEqual(result, {"elements": []})
        request = client.opener.open.call_args.args[0]
        url = urlsplit(request.full_url)
        self.assertEqual((url.scheme, url.netloc, url.path),
                         ("https", "inventory.example.test", "/v1/domains"))
        self.assertEqual(parse_qs(url.query), {"pageNumber": ["0"], "pageSize": ["25"]})
        self.assertEqual(request.get_method(), "GET")

    def test_inventory_rejects_mutating_methods(self):
        client = self.client()
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method), self.assertRaises((ApiError, ValueError)):
                client.request(method, "/v1/hosts")
        client.opener.open.assert_not_called()

    def test_post_is_restricted_to_session_creation(self):
        client = self.client()
        with self.assertRaises((ApiError, ValueError)):
            client.request("POST", "/v1/hosts", body={"name": "unexpected"})
        client.opener.open.assert_not_called()

    def test_absolute_or_network_path_cannot_send_credentials_off_origin(self):
        client = self.client()
        client.headers["Authorization"] = "Bearer example-secret"
        for path in ("https://other.example.test/v1/hosts", "//other.example.test/v1/hosts"):
            with self.subTest(path=path), self.assertRaises((ApiError, ValueError)):
                client.get(path)
        client.opener.open.assert_not_called()

    def test_http_failure_is_not_an_empty_inventory(self):
        client = self.client()
        client.opener.open.side_effect = HTTPError(
            "https://inventory.example.test/v1/hosts", 403, "Forbidden", {},
            io.BytesIO(b'{"message":"access denied"}'))
        with self.assertRaises(ApiError) as caught:
            client.get("/v1/hosts")
        self.assertEqual(caught.exception.status, 403)

    @patch.dict(os.environ, {"https_proxy": "http://proxy.example.test:8080", "HTTPS_PROXY": "http://proxy.example.test:8080"})
    def test_proxy_handler_does_not_inherit_environment_proxies(self):
        client = HttpClient(target(), retries=0)
        handlers = [handler for handler in client.opener.handlers if isinstance(handler, ProxyHandler)]
        # urllib may omit an empty ProxyHandler from the final opener entirely.
        self.assertTrue(all(not handler.proxies for handler in handlers))

    def test_redirect_handler_refuses_to_forward_authenticated_requests(self):
        client = HttpClient(target(), retries=0)
        handlers = [handler for handler in client.opener.handlers if isinstance(handler, HTTPRedirectHandler)]
        self.assertEqual(len(handlers), 1)
        request = Request("https://inventory.example.test/v1/hosts", headers={"Authorization": "Bearer example-token"})
        try:
            redirected = handlers[0].redirect_request(
                request, None, 302, "Found", {}, "https://other.example.test/v1/hosts")
        except HTTPError:
            redirected = None
        self.assertIsNone(redirected)

    @patch.dict(os.environ, {"TEST_INVENTORY_USERNAME": "reader", "TEST_INVENTORY_PASSWORD": "p:a ss"})
    def test_sddc_authentication_uses_access_token(self):
        client = self.client(responses=[{"accessToken": "example-token"}, {"elements": []}])
        client.authenticate()
        auth_request = client.opener.open.call_args.args[0]
        self.assertEqual(urlsplit(auth_request.full_url).path, "/v1/tokens")
        self.assertEqual(auth_request.get_method(), "POST")
        self.assertEqual(json.loads(auth_request.data), {"username": "reader", "password": "p:a ss"})
        client.get("/v1/domains")
        request = client.opener.open.call_args.args[0]
        self.assertEqual(normalized_headers(request)["authorization"], "Bearer example-token")

    @patch.dict(os.environ, {"TEST_INVENTORY_USERNAME": "reader", "TEST_INVENTORY_PASSWORD": "p:a ss"})
    def test_vcenter_authentication_uses_session_header(self):
        client = self.client(component="vcenter", responses=["example-session", []])
        client.authenticate()
        auth_request = client.opener.open.call_args.args[0]
        self.assertEqual(urlsplit(auth_request.full_url).path, "/api/session")
        client.get("/api/vcenter/cluster")
        request = client.opener.open.call_args.args[0]
        headers = normalized_headers(request)
        self.assertEqual(headers["vmware-api-session-id"], "example-session")
        self.assertNotIn("authorization", headers)

    @patch.dict(os.environ, {"TEST_INVENTORY_USERNAME": "reader", "TEST_INVENTORY_PASSWORD": "p:a ss"})
    def test_nsx_basic_authentication_does_not_create_a_session(self):
        client = self.client(component="nsx", responses=[{"results": []}])
        client.authenticate()
        client.opener.open.assert_not_called()
        client.get("/policy/api/v1/infra/segments")
        request = client.opener.open.call_args.args[0]
        expected = "Basic " + base64.b64encode(b"reader:p:a ss").decode("ascii")
        self.assertEqual(normalized_headers(request)["authorization"], expected)


class CollectorTests(unittest.TestCase):
    def client(self, component, responses):
        client = Mock()
        client.target = target(component)
        client.get.side_effect = responses
        return client

    def test_sddc_uses_page_metadata_to_continue_after_short_page(self):
        client = self.client("sddc_manager", [
            {"elements": [{"id": "host-1"}],
             "pageMetadata": {"pageNumber": 0, "pageSize": 100, "totalElements": 2, "totalPages": 2}},
            {"elements": [{"id": "host-2"}],
             "pageMetadata": {"pageNumber": 1, "pageSize": 100, "totalElements": 2, "totalPages": 2}},
        ])
        rows = collect_resource(client, "hosts", page_size=100)
        self.assertEqual([row["id"] for row in rows], ["host-1", "host-2"])
        self.assertEqual(client.get.call_count, 2)
        queries = [call.kwargs.get("params", {}) for call in client.get.call_args_list]
        self.assertEqual([query["pageNumber"] for query in queries], [0, 1])

    def test_sddc_network_pools_does_not_send_undocumented_page_parameters(self):
        client = self.client("sddc_manager", [{"elements": [{"id": "pool-1"}]}])
        self.assertEqual(collect_resource(client, "network_pools"), [{"id": "pool-1"}])
        self.assertFalse(client.get.call_args.kwargs.get("params"))

    def test_nsx_follows_opaque_cursor_even_when_page_is_short(self):
        client = self.client("nsx", [
            {"results": [{"id": "segment-1"}], "cursor": "opaque+/=next", "result_count": 2},
            {"results": [{"id": "segment-2"}]},
        ])
        rows = collect_resource(client, "segments", page_size=100)
        self.assertEqual([row["id"] for row in rows], ["segment-1", "segment-2"])
        self.assertEqual(client.get.call_args_list[1].kwargs["params"]["cursor"], "opaque+/=next")

    def test_nsx_repeated_cursor_fails_instead_of_looping(self):
        client = self.client("nsx", [
            {"results": [{"id": "a"}], "cursor": "unchanged"},
            {"results": [{"id": "b"}], "cursor": "unchanged"},
        ])
        with self.assertRaises(ApiError):
            collect_resource(client, "segments", max_pages=5)
        self.assertLessEqual(client.get.call_count, 2)

    def test_malformed_collection_is_not_reported_as_empty(self):
        for component, resource, response in (
            ("sddc_manager", "hosts", {"unexpected": []}),
            ("nsx", "segments", {"unexpected": []}),
            ("vcenter", "clusters", {"unexpected": []}),
        ):
            with self.subTest(component=component), self.assertRaises(ApiError):
                collect_resource(self.client(component, [response]), resource)

    def test_sddc_and_nsx_require_collection_envelopes(self):
        for component, resource in (("sddc_manager", "hosts"), ("nsx", "segments")):
            with self.subTest(component=component), self.assertRaises(ApiError):
                collect_resource(self.client(component, [[{"id": "unexpected-envelope"}]]), resource)

    def test_nsx_single_page_cannot_claim_completeness_below_result_count(self):
        client = self.client("nsx", [{"results": [{"id": "segment-1"}], "result_count": 2}])
        with self.assertRaises(ApiError):
            collect_resource(client, "segments")

    def test_sddc_retains_previous_total_when_later_metadata_is_missing(self):
        client = self.client("sddc_manager", [
            {"elements": [{"id": "host-1"}],
             "pageMetadata": {"pageNumber": 0, "totalElements": 3}},
            {"elements": [{"id": "host-2"}]},
            {"elements": []},
        ])
        with self.assertRaises(ApiError):
            collect_resource(client, "hosts")

    def test_maximum_page_limit_is_an_error(self):
        client = self.client("nsx", [{"results": [{"id": "segment-1"}], "cursor": "next"}])
        with self.assertRaises(ApiError):
            collect_resource(client, "segments", max_pages=1)

    def test_sddc_final_page_retains_total_when_only_total_pages_is_present(self):
        client = self.client("sddc_manager", [
            {"elements": [{"id": "a"}],
             "pageMetadata": {"pageNumber": 0, "totalElements": 3, "totalPages": 2}},
            {"elements": [{"id": "b"}],
             "pageMetadata": {"pageNumber": 1, "totalPages": 2}},
        ])
        with self.assertRaises(ApiError):
            collect_resource(client, "hosts")

    def test_vcenter_vm_limit_is_an_explicit_error(self):
        client = self.client("vcenter", [[{"vm": "vm-%s" % i} for i in range(4000)]])
        with self.assertRaises(ApiError):
            collect_resource(client, "vms")

    def test_collection_error_propagates(self):
        client = self.client("nsx", [])
        client.get.side_effect = ApiError("access denied", status=403)
        with self.assertRaises(ApiError):
            collect_resource(client, "segments")


class ExportTests(unittest.TestCase):
    def test_redaction_is_recursive_case_insensitive_and_preserves_inventory(self):
        value = {"id": "host-1", "Password": "never-export", "details": [
            {"accessToken": "never-export", "display_name": "server-1"},
            {"credentials": {"username": "reader", "password": "never-export"}},
        ]}
        redacted = sanitize(value)
        rendered = json.dumps(redacted)
        self.assertNotIn("never-export", rendered)
        self.assertEqual(redacted["id"], "host-1")
        self.assertEqual(redacted["details"][0]["display_name"], "server-1")
        self.assertIn("[REDACTED]", rendered)
        self.assertEqual(value["Password"], "never-export")

    def test_saved_json_redacts_and_csv_neutralizes_spreadsheet_formulas(self):
        records = [
            {"id": "1", "name": "=HYPERLINK(\"https://example.test\")", "password": "never-export"},
            {"id": "2", "name": "+SUM(1,2)", "password": "never-export"},
            {"id": "3", "name": "@SUM(1,2)", "password": "never-export"},
            {"id": "4", "name": "-1+1", "password": "never-export"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            write_resource(Path(directory), "hosts", records, {"target": "test-target"}, write_csv=True)
            files = list(Path(directory).iterdir())
            json_files = [path for path in files if path.suffix == ".json"]
            csv_files = [path for path in files if path.suffix == ".csv"]
            self.assertTrue(json_files)
            self.assertTrue(csv_files)
            for path in files:
                self.assertNotIn("never-export", path.read_text(encoding="utf-8-sig"))
            with csv_files[0].open(encoding="utf-8-sig", newline="") as stream:
                saved_rows = list(csv.DictReader(stream))
            self.assertEqual(len(saved_rows), 4)
            self.assertTrue(all(row["name"].startswith("'") for row in saved_rows))


class ConfigurationTests(unittest.TestCase):
    def load(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_config(path)

    def test_origin_validation_rejects_plaintext_or_embedded_credentials(self):
        for url in ("http://inventory.example.test", "https://reader:password@inventory.example.test",
                    "https://inventory.example.test/api", "https://inventory.example.test?password=secret"):
            with self.subTest(url=url), self.assertRaises(ConfigError):
                self.load({"targets": [target(url=url)]})

    def test_insecure_tls_is_rejected(self):
        with self.assertRaises(ConfigError):
            self.load({"targets": [target(verify_tls=False)]})

    def test_duplicate_target_names_are_case_insensitive(self):
        with self.assertRaises(ConfigError):
            self.load({"targets": [target(name="Management"), target(name="management")]})

    def test_target_names_cannot_escape_output_directory(self):
        for name in ("../outside", "..", "CON", "nested/target"):
            with self.subTest(name=name), self.assertRaises(ConfigError):
                self.load({"targets": [target(name=name)]})


class SessionCleanupTests(unittest.TestCase):
    def test_vcenter_session_is_closed_if_export_fails_or_user_interrupts(self):
        from vcf_inventory import cli

        config = {"targets": [target("vcenter", resources=["clusters"])],
                  "timeout_seconds": 30, "retries": 0, "page_size": 100, "max_pages": 5}
        for failure, expected_status in ((OSError("disk unavailable"), 1), (KeyboardInterrupt(), 130)):
            with self.subTest(failure=type(failure).__name__):
                client = Mock()
                with patch.object(cli, "load_config", return_value=config), \
                        patch.object(cli, "HttpClient", return_value=client), \
                        patch.object(cli, "collect_resource", return_value=[]), \
                        patch.object(cli, "write_resource", side_effect=failure), \
                        patch.object(cli, "write_json"), \
                        patch.object(cli.Path, "mkdir"), \
                        patch("sys.stdout", new_callable=io.StringIO), \
                        patch("sys.stderr", new_callable=io.StringIO):
                    status = cli.main(["--config", "config.json"])
                self.assertEqual(status, expected_status)
                client.close.assert_called_once_with()


class CommandTests(unittest.TestCase):
    def config(self):
        return {"targets": [target("vcenter", resources=["clusters", "hosts"])],
                "timeout_seconds": 30, "retries": 0, "page_size": 100, "max_pages": 5}

    def test_partial_failure_exports_successful_resource_and_marks_summary_incomplete(self):
        from vcf_inventory import cli

        snapshots = []
        client = Mock()

        def capture(path, data):
            snapshots.append(json.loads(json.dumps(data)))

        with patch.object(cli, "load_config", return_value=self.config()), \
                patch.object(cli, "HttpClient", return_value=client), \
                patch.object(cli, "collect_resource", side_effect=[[{"cluster": "domain-c1"}], ApiError("access denied", 403)]), \
                patch.object(cli, "write_resource") as write_resource_mock, \
                patch.object(cli, "write_json", side_effect=capture), \
                patch.object(cli.Path, "mkdir"), \
                patch("sys.stdout", new_callable=io.StringIO), \
                patch("sys.stderr", new_callable=io.StringIO):
            status = cli.main(["--config", "config.json", "--csv"])
        self.assertEqual(status, 2)
        write_resource_mock.assert_called_once()
        self.assertEqual(write_resource_mock.call_args.args[1], "clusters")
        self.assertEqual(write_resource_mock.call_args.args[2], [{"cluster": "domain-c1"}])
        self.assertTrue(write_resource_mock.call_args.kwargs["write_csv"])
        final = snapshots[-1]
        self.assertEqual(final["status"], "incomplete")
        self.assertEqual(final["targets"][0]["status"], "error")
        results = final["targets"][0]["resources"]
        self.assertEqual([row["status"] for row in results], ["success", "error"])
        self.assertEqual(results[0]["record_count"], 1)
        self.assertNotIn("record_count", results[1])
        client.close.assert_called_once_with()

    def test_authentication_failure_never_becomes_empty_success(self):
        from vcf_inventory import cli

        snapshots = []
        client = Mock()
        client.authenticate.side_effect = ApiError("Required credentials are missing.")

        def capture(path, data):
            snapshots.append(json.loads(json.dumps(data)))

        with patch.object(cli, "load_config", return_value=self.config()), \
                patch.object(cli, "HttpClient", return_value=client), \
                patch.object(cli, "collect_resource") as collect_mock, \
                patch.object(cli, "write_resource") as export_mock, \
                patch.object(cli, "write_json", side_effect=capture), \
                patch.object(cli.Path, "mkdir"), \
                patch("sys.stdout", new_callable=io.StringIO), \
                patch("sys.stderr", new_callable=io.StringIO):
            status = cli.main(["--config", "config.json"])
        self.assertEqual(status, 2)
        collect_mock.assert_not_called()
        export_mock.assert_not_called()
        final = snapshots[-1]
        self.assertEqual(final["status"], "incomplete")
        self.assertTrue(all(row["status"] == "error" for row in final["targets"][0]["resources"]))
        client.close.assert_called_once_with()

    def test_config_validation_never_opens_a_network_client(self):
        from vcf_inventory import cli

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(self.config()), encoding="utf-8")
            with patch.object(cli, "HttpClient") as client_factory, \
                    patch.object(cli, "write_resource") as export_mock, \
                    patch("sys.stdout", new_callable=io.StringIO):
                status = cli.main(["--config", str(path), "--validate-config"])
            self.assertEqual(status, 0)
            client_factory.assert_not_called()
            export_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
