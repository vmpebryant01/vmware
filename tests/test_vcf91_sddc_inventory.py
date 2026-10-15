"""Offline checks for the VCF 9.1.x SDDC inventory report. Author: Paul Bryant."""

import csv
import json
import ssl
import tempfile
import unittest
from pathlib import Path

from vcf9 import sddc_inventory as inventory


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return json.dumps(self.value).encode("utf-8")


class SddcInventoryTests(unittest.TestCase):
    def test_authentication_and_all_pages_use_expected_methods(self):
        seen = []

        def opener(request, timeout, context):
            seen.append((request.get_method(), request.full_url, request.headers, timeout, context.verify_mode))
            if request.full_url.endswith("/v1/tokens"):
                self.assertEqual(json.loads(request.data), {"username": "paul", "password": "secret"})
                return FakeResponse({"accessToken": "token"})
            page = int(request.full_url.split("pageNumber=")[1].split("&")[0])
            return FakeResponse({"elements": [{"id": str(page)}], "pageMetadata": {"totalPages": 2}})

        client = inventory.SddcClient("manager.example.com", opener=opener)
        client.authenticate("paul", "secret")
        self.assertEqual([row["id"] for row in client.get_pages("/v1/domains")], ["0", "1"])
        self.assertEqual([entry[0] for entry in seen], ["POST", "GET", "GET"])
        self.assertEqual(seen[1][2]["Authorization"], "Bearer token")
        self.assertTrue(all(entry[3] == 30 and entry[4] == ssl.CERT_REQUIRED for entry in seen))

    def test_rejects_other_product_versions_before_inventory_calls(self):
        calls = []

        def opener(request, timeout, context):
            calls.append(request.full_url)
            return FakeResponse({"role": "SddcManager", "version": "9.0.2.0"})

        client = inventory.SddcClient("manager.example.com", opener=opener)
        with self.assertRaisesRegex(RuntimeError, "Expected SDDC Manager 9.1.x"):
            inventory.collect(client)
        self.assertEqual(len(calls), 1)

    def test_exports_only_selected_fields_and_escapes_formula_text(self):
        data = {
            "appliance": {"role": "SddcManager", "version": "9.1.1.0", "dnsDomain": "example.com"},
            "domains": [{"id": "1", "name": "=HYPERLINK(1)", "status": "ACTIVE", "secret": "do not export"}],
            "clusters": [],
            "hosts": [],
        }
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            output = Path(directory)
            inventory.export_inventory(data, output)
            with (output / "domains.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["name"], "'=HYPERLINK(1)")
            self.assertNotIn("secret", rows[0])
            with (output / "hosts.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(len(list(csv.reader(stream))), 1)

    def test_rejects_unexpected_pagination_response(self):
        def opener(request, timeout, context):
            return FakeResponse({"elements": []})

        client = inventory.SddcClient("manager.example.com", opener=opener)
        with self.assertRaisesRegex(RuntimeError, "Missing pagination metadata"):
            client.get_pages("/v1/hosts")


if __name__ == "__main__":
    unittest.main()
