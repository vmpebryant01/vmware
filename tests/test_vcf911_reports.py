"""Offline contract checks for VCF 9.1.1 reports. Author: Paul Bryant."""

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from vcf9 import report_core
from vcf9.automation import catalog, deployments
from vcf9.fleet import depot_sync, management_components, services
from vcf9.nsx import gateways, security_policies
from vcf9.operations import adapters, alerts, resources
from vcf9.sddc_inventory import write_csv


class FakeReadClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path, query=None):
        self.calls.append((path, query))
        return self.responses[len(self.calls) - 1]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self):
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return FakeResponse({"items": []})


class FakeSddcClient:
    def __init__(self, responses=None, pages=None):
        self.responses = responses or {}
        self.pages = pages or {}
        self.calls = []

    def request_json(self, method, path):
        self.calls.append((method, path))
        return self.responses[path]

    def get_pages(self, path):
        self.calls.append(("GET", path))
        return self.pages[path]


class Vcf911ReportTests(unittest.TestCase):
    def test_fleet_shapes_and_no_error_payload(self):
        client = FakeSddcClient({
            "/v1/vcf-management-components": {
                "vcfOperations": {"nodes": [{"fqdn": "ops-1.example", "type": "master"}],
                                  "loadBalancerFqdn": "ops.example", "deploymentStatus": "SUCCEEDED"},
                "vcfAutomation": {"fqdn": "automation.example", "deploymentStatus": "FAILED"},
                "fleetLcm": {"deploymentStatus": "SUCCEEDED"}},
            "/v1/system/settings/depot/depot-sync-info": {"syncStatus": "FAILED", "errorMessage": "sensitive URL"}},
            {"/v1/vcf-services": [{"id": "1", "name": "svc", "version": "9.1.1", "status": "ACTIVE"}]})
        components = management_components.collect(client, None)
        self.assertEqual(len(components), 4)
        self.assertEqual({row["endpoint"] for row in components}, {"master", "loadBalancer", "appliance", ""})
        self.assertEqual(services.collect(client, None)[0]["name"], "svc")
        self.assertEqual(depot_sync.collect(client, None)[0]["hasError"], True)
        self.assertNotIn("sensitive URL", repr(depot_sync.collect(client, None)))
        self.assertTrue(all(method == "GET" for method, _ in client.calls))

    def test_operations_pages_and_selected_adapter_fields(self):
        client = FakeReadClient([
            {"alerts": [{"alertId": "a1"}], "pageInfo": {"totalCount": 2}},
            {"alerts": [{"alertId": "a2"}], "pageInfo": {"totalCount": 2}},
        ])
        self.assertEqual([row["alertId"] for row in alerts.collect(client, None)], ["a1", "a2"])
        self.assertEqual([call[1]["page"] for call in client.calls], [0, 1])
        client = FakeReadClient([{"adapterInstancesInfoDto": [{"id": "1", "resourceKey": {"name": "vCenter", "adapterKindKey": "VMWARE"}, "credentialInstanceId": "secret-id"}]}])
        rows = adapters.collect(client, None)
        self.assertEqual(rows[0]["name"], "vCenter")
        self.assertNotIn("credentialInstanceId", rows[0])
        client = FakeReadClient([{"resourceList": [{"identifier": "vm-1", "resourceKey": {"name": "VM1", "resourceKindKey": "VirtualMachine"}}], "pageInfo": {"totalCount": 1}}])
        self.assertEqual(resources.collect(client, SimpleNamespace(resource_kind="VirtualMachine"))[0]["name"], "VM1")
        self.assertEqual(client.calls[0][1]["resourceKind"], "VirtualMachine")

    def test_automation_pagination_and_secret_reduction(self):
        client = FakeReadClient([
            {"content": [{"id": "d1", "name": "deploy", "inputs": {"password": "secret"}, "lastRequest": {"status": "SUCCESSFUL"}}], "totalPages": 2},
            {"content": [{"id": "d2", "lastRequest": {"status": "FAILED"}}], "totalPages": 2},
        ])
        rows = deployments.collect(client, None)
        self.assertEqual([row["id"] for row in rows], ["d1", "d2"])
        self.assertEqual(rows[1]["lastRequestStatus"], "FAILED")
        self.assertNotIn("secret", repr(rows))
        client = FakeReadClient([{"content": [{"id": "c1", "name": "Item", "projectIds": ["p1", "p2"], "schema": {"default": "secret"}}], "totalPages": 1}])
        rows = catalog.collect(client, None)
        self.assertEqual(rows[0]["visibleProjectCount"], 2)
        self.assertNotIn("schema", rows[0])

    def test_nsx_cursor_pages_and_domain_validation(self):
        client = FakeReadClient([
            {"results": [{"id": "t0"}], "cursor": "next token"},
            {"results": [{"id": "t0b"}]},
            {"results": [{"id": "t1"}]},
        ])
        rows = gateways.collect(client, None)
        self.assertEqual([(row["tier"], row["id"]) for row in rows], [("0", "t0"), ("0", "t0b"), ("1", "t1")])
        self.assertEqual(client.calls[1][1]["cursor"], "next token")
        client = FakeReadClient([{"results": [{"id": "p1", "rule_count": 3}]}])
        rows = security_policies.collect(client, SimpleNamespace(domain_id="default"))
        self.assertEqual(rows[0]["rule_count"], 3)
        self.assertEqual(client.calls[0][1]["include_rule_count"], "true")
        with self.assertRaises(ValueError):
            security_policies.collect(client, SimpleNamespace(domain_id="../bad"))

    def test_failure_boundaries_and_csv_safety(self):
        client = FakeReadClient([{"alerts": [{}], "pageInfo": {"totalCount": 2}}, {"alerts": [{}], "pageInfo": {"totalCount": 2}}])
        self.assertEqual(len(report_core.page_items(client, "/suite-api/api/alerts", "alerts", "ops")), 2)
        client = FakeReadClient([{"results": [], "cursor": "repeat"}, {"results": [], "cursor": "repeat"}])
        with self.assertRaisesRegex(RuntimeError, "repeated cursor"):
            report_core.cursor_items(client, "/policy/api/v1/infra/tier-0s")
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / "report.csv"
            write_csv(path, ("name",), [{"name": "=danger", "secret": "do not export"}])
            with path.open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(list(csv.DictReader(stream)), [{"name": "'=danger"}])

    def test_credentials_and_version_gate(self):
        with patch.dict("os.environ", {"VCF_OPS_TOKEN": "example-token"}):
            client = report_core.client_for(SimpleNamespace(host="ops.example", ca_bundle=None, token_scheme="OpsToken"), "VCF Operations")
            self.assertEqual(client.authorization, "OpsToken example-token")
            client = report_core.client_for(SimpleNamespace(host="ops.example", ca_bundle=None, token_scheme="Bearer"), "VCF Operations")
            self.assertEqual(client.authorization, "Bearer example-token")
        with patch.dict("os.environ", {"VCF_AUTOMATION_TOKEN": "example-token"}):
            client = report_core.client_for(SimpleNamespace(host="auto.example", ca_bundle=None), "VCF Automation")
            self.assertEqual(client.authorization, "Bearer example-token")
        with patch("vcf9.report_core.SddcClient") as cls, patch("vcf9.report_core.getpass.getpass", return_value="password"), patch("vcf9.report_core.ensure_vcf91", return_value={"version": "9.1.0.0"}):
            with self.assertRaisesRegex(RuntimeError, "9.1.1"):
                report_core.client_for(SimpleNamespace(host="sddc.example", username="paul", ca_bundle=None), "SDDC Manager")
            cls.return_value.authenticate.assert_called_once_with("paul", "password")
        with patch("vcf9.report_core.SddcClient"), patch("vcf9.report_core.getpass.getpass", return_value="password"), patch("vcf9.report_core.ensure_vcf91", return_value={"version": "9.1.10.0"}):
            with self.assertRaisesRegex(RuntimeError, "9.1.1"):
                report_core.client_for(SimpleNamespace(host="sddc.example", username="paul", ca_bundle=None), "SDDC Manager")

    def test_transport_stays_on_named_host_and_get_method(self):
        opener = FakeOpener()
        client = report_core.ReadClient("nsx.example", "Basic example", opener=opener)
        self.assertEqual(client.get("/policy/api/v1/infra/tier-0s", {"cursor": "a+b"}), {"items": []})
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, "https://nsx.example/policy/api/v1/infra/tier-0s?cursor=a%2Bb")
        self.assertEqual(request.headers["Authorization"], "Basic example")
        self.assertEqual(timeout, 30)
        with self.assertRaises(ValueError):
            client.get("//another-host/path")
        with self.assertRaises(ValueError):
            report_core.ReadClient("bad/host", "token", opener=opener)


if __name__ == "__main__":
    unittest.main()
