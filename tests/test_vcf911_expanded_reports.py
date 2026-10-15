"""Offline checks for the 30 additional reports. Author: Paul Bryant."""

import json
import unittest
from types import SimpleNamespace

from vcf9 import expanded_reports
from vcf9.protection_recovery import dr_core, reports as recovery_reports


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def get(self, path, query=None):
        self.calls.append((path, query))
        return next(self.replies)

    def get_pages(self, path):
        self.calls.append((path, None))
        return next(self.replies)

    def request_json(self, method, path):
        self.calls.append((method, path))
        return next(self.replies)


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return next(self.responses)


def dr_page(rows, total=None):
    return {"list": rows, "_meta": {"total": len(rows) if total is None else total, "errors": []}}


class ExpandedReportTests(unittest.TestCase):
    def test_manifest_has_fifteen_distinct_commands_per_half(self):
        self.assertEqual(len(expanded_reports.REPORTS), 15)
        self.assertEqual(len(recovery_reports.REPORTS), 15)
        self.assertEqual({r.target for r in expanded_reports.REPORTS.values()}, {"NSX Manager", "VCF Operations", "SDDC Manager"})
        self.assertEqual([sum(r.target == target for r in expanded_reports.REPORTS.values()) for target in
                          ("NSX Manager", "VCF Operations", "SDDC Manager")], [5, 5, 5])
        for report in (*expanded_reports.REPORTS.values(), *recovery_reports.REPORTS.values()):
            self.assertEqual(len(report.columns), len(report.fields))
            self.assertEqual(len(set(report.columns)), len(report.columns))
        self.assertEqual(len({r.path for r in recovery_reports.REPORTS.values()}), 15)

    def test_nsx_cursor_and_identifier_encoding(self):
        client = FakeClient([{"results": [{"id": "rule-1", "action": "ALLOW", "source_groups": ["secret"]}], "cursor": "next"},
                             {"results": [{"id": "rule-2", "action": "DROP"}]}])
        args = SimpleNamespace(domain_id="default", policy_id="web:policy")
        rows = expanded_reports.collect("security_rules", client, args)
        self.assertEqual([row["id"] for row in rows], ["rule-1", "rule-2"])
        self.assertNotIn("source_groups", repr(rows))
        self.assertIn("web%3Apolicy", client.calls[0][0])
        self.assertEqual(client.calls[1][1]["cursor"], "next")
        with self.assertRaises(ValueError):
            expanded_reports.collect("security_rules", client, SimpleNamespace(domain_id="../escape", policy_id="x"))

    def test_operations_paging_and_nested_projection(self):
        client = FakeClient([{"alertDefinitions": [{"id": "a", "name": "Alert A", "states": [{"secret": "omit"}]}],
                              "pageInfo": {"totalCount": 1}}])
        self.assertEqual(expanded_reports.collect("alert_definitions", client, None)[0]["name"], "Alert A")
        self.assertNotIn("secret", repr(expanded_reports.collect("custom_groups", FakeClient([
            {"groups": [{"id": "g", "resourceKey": {"name": "group"}, "membershipDefinition": {"secret": "omit"}}]}]), None)))
        self.assertEqual(client.calls[0][1]["pageSize"], 100)

    def test_sddc_single_page_fails_closed(self):
        client = FakeClient([{"elements": [{"id": "b1"}], "pageMetadata": {"totalPages": 2}}])
        with self.assertRaisesRegex(RuntimeError, "no documented page selector"):
            expanded_reports.collect("bundles", client, None)

    def test_recovery_session_and_scoped_headers(self):
        opener = FakeOpener([FakeResponse(200, {"session_id": "abc"}), FakeResponse(204),
                             FakeResponse(200, dr_page([{"id": "g1"}])), FakeResponse(204)])
        client = dr_core.DrClient("recovery.example", opener=opener)
        client.login("local", "local-password")
        client.remote_login("pair-1", "remote", "remote-password")
        rows = dr_core.dr_items(client, "/pairings/pair-1/protection-management/groups")
        self.assertEqual(rows[0]["id"], "g1")
        client.logout()
        requests = [request for request, _ in opener.requests]
        self.assertEqual([r.get_method() for r in requests], ["POST", "POST", "GET", "DELETE"])
        self.assertEqual(requests[0].full_url, "https://recovery.example/api/rest/srm/v2/session")
        self.assertEqual(requests[2].headers["X-dr-session"], "abc")
        self.assertNotIn("Authorization", requests[2].headers)
        self.assertEqual(requests[2].full_url,
                         "https://recovery.example/api/rest/srm/v2/pairings/pair-1/protection-management/groups?limit=100&offset=0")
        self.assertIsNone(client.session_id)

    def test_recovery_offset_and_redaction(self):
        client = FakeClient([dr_page([{"pairing_id": "p1", "local_vc_server": {"name": "vc1", "certificates": [{"certificate": "secret"}]}}], 2),
                             dr_page([{"pairing_id": "p2"}], 2)])
        rows = recovery_reports.collect("pairings", client, SimpleNamespace())
        self.assertEqual([row["pairing_id"] for row in rows], ["p1", "p2"])
        self.assertNotIn("secret", repr(rows))
        self.assertEqual([call[1]["offset"] for call in client.calls], [0, 1])
        with self.assertRaisesRegex(RuntimeError, "list errors"):
            dr_core.dr_items(FakeClient([{"list": [], "_meta": {"total": 0, "errors": [{"message": "error"}]}}]), "/pairings")

    def test_recovery_paths_and_id_validation(self):
        args = SimpleNamespace(pairing_id="pair-1", srm_id="srm:1")
        client = FakeClient([dr_page([{"id": "map-1", "primary_object_name": "primary", "secondary_object_name": "recovery"}])])
        row = recovery_reports.collect("storage_policy_mappings", client, args)[0]
        self.assertEqual(row["srm_id"], "srm:1")
        self.assertIn("srm%3A1", client.calls[0][0])
        with self.assertRaises(ValueError):
            dr_core.path_id("../other", "srm-id")
        with self.assertRaises(ValueError):
            dr_core.DrClient("bad/host")


if __name__ == "__main__":
    unittest.main()
