"""Offline tests for VCF Automation inventory. Author: Paul Bryant."""

import unittest
from unittest.mock import patch

from vcf_inventory.http_client import ApiError
from vcf_inventory.products import automation


def target(family="all_apps", **overrides):
    value = {"component": "vcf_automation", "api_family": family, "token_env": "VCFA_ACCESS_TOKEN"}
    if family == "provider":
        value["api_version"] = "9.1.1"
    value.update(overrides)
    return value


class FakeClient:
    def __init__(self, responses=(), family="all_apps", **options):
        self.target = target(family, **options)
        self.headers = {"Accept": "application/json"}
        self._product_state = {}
        self.responses = list(responses)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if not self.responses:
            raise AssertionError("Unexpected request after simulated responses were exhausted")
        return self.responses.pop(0)


class ConfigurationAndAuthenticationTests(unittest.TestCase):
    def test_family_defaults_are_separate(self):
        self.assertEqual(automation.default_resources(target()), ["projects", "blueprints", "deployments"])
        self.assertIn("fabric_networks", automation.default_resources(target("vm_apps")))
        self.assertNotIn("projects", automation.default_resources(target("provider")))

    def test_invalid_family_and_cross_family_resource_rejected(self):
        for options in ({"api_family": "aria"}, {"resources": ["cloud_zones"]}, {"resources": ["projects", "projects"]}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                automation.validate_target(target(**options))

    def test_provider_requires_numeric_version_and_org_context_is_provider_only(self):
        for value in (None, "latest", "8.18", "9.1.1\r\nOther: value"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                automation.validate_target(target("provider", api_version=value))
        with self.assertRaises(ValueError):
            automation.validate_target(target(org_id="organization-id"))
        with self.assertRaises(ValueError):
            automation.validate_target(target(api_version="2019-01-15"))

    def test_validation_does_not_read_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            automation.validate_target(target())
        with self.assertRaises(ValueError):
            automation.validate_target(target(token_env="not a variable"))

    def test_provider_authentication_uses_access_token_and_negotiated_version(self):
        client = FakeClient(family="provider", org_id="urn:vcloud:org:example")
        with patch.dict("os.environ", {"VCFA_ACCESS_TOKEN": "example.jwt.value"}, clear=True):
            automation.authenticate(client)
        self.assertEqual(client.headers["Authorization"], "Bearer example.jwt.value")
        self.assertEqual(client.headers["Accept"], "application/json;version=9.1.1")
        self.assertEqual(client.headers["X-VMWARE-VCLOUD-TENANT-CONTEXT"], "urn:vcloud:org:example")
        self.assertEqual(client.calls, [])
        automation.close(client)
        self.assertNotIn("Authorization", client.headers)
        self.assertNotIn("X-VMWARE-VCLOUD-TENANT-CONTEXT", client.headers)
        self.assertEqual(client.calls, [])

    def test_missing_prefixed_or_control_character_token_is_rejected(self):
        for token in ("", "Bearer token", "token\nInjected", "token\x00"):
            with self.subTest(token=repr(token)), patch.object(automation.os, "environ", {"VCFA_ACCESS_TOKEN": token}):
                with self.assertRaises(ApiError):
                    automation.authenticate(FakeClient())

    def test_no_mutating_requests_are_allowed(self):
        self.assertEqual(automation.ALLOWED_OPERATIONS, set())


class PaginationTests(unittest.TestCase):
    def test_project_pages_include_viewers_and_supervisors(self):
        client = FakeClient([
            {"content": [{"id": "a"}, {"id": "b"}], "number": 0, "totalElements": 3, "totalPages": 2, "last": False},
            {"content": [{"id": "c"}], "number": 1, "totalElements": 3, "totalPages": 2, "last": True},
        ])
        rows = automation.collect_resource(client, "projects", page_size=2)
        self.assertEqual([row["id"] for row in rows], ["a", "b", "c"])
        self.assertEqual(client.calls[0], ("/project-service/api/projects", {
            "page": 0, "size": 2, "excludeSupervisor": "false", "excludeViewer": "false"}))
        self.assertEqual(client.calls[1][1]["page"], 1)

    def test_short_page_without_metadata_is_not_assumed_complete(self):
        client = FakeClient([{"content": [{"id": "a"}]}, {"content": [{"id": "b"}]}, {"content": []}])
        self.assertEqual(len(automation.collect_resource(client, "deployments", page_size=100)), 2)
        self.assertEqual([params["page"] for _, params in client.calls], [0, 1, 2])

    def test_iaas_uses_top_skip_instead_of_spring_page_parameters(self):
        client = FakeClient([
            {"content": [{"id": "a"}, {"id": "b"}], "totalElements": 3, "numberOfElements": 2},
            {"content": [{"id": "c"}], "totalElements": 3, "numberOfElements": 1},
        ], family="vm_apps")
        self.assertEqual(len(automation.collect_resource(client, "fabric_networks", page_size=2)), 3)
        self.assertEqual(client.calls[0], ("/iaas/api/fabric-networks", {"$top": 2, "$skip": 0, "$count": "true"}))
        self.assertEqual(client.calls[1][1]["$skip"], 2)

    def test_iaas_offset_advances_by_actual_records_when_server_caps_page(self):
        client = FakeClient([{"content": [{"id": "a"}]}, {"content": [{"id": "b"}]}, {"content": []}], family="vm_apps")
        self.assertEqual(len(automation.collect_resource(client, "cloud_zones", page_size=100)), 2)
        self.assertEqual([params["$skip"] for _, params in client.calls], [0, 1, 2])
        self.assertNotIn("$count", client.calls[0][1])

    def test_provider_uses_one_based_pages_and_maximum_128_records(self):
        client = FakeClient([
            {"values": [{"id": "a"}], "page": 1, "resultTotal": 2, "pageCount": 2},
            {"values": [{"id": "b"}], "page": 2, "resultTotal": 2, "pageCount": 2},
        ], family="provider")
        self.assertEqual(len(automation.collect_resource(client, "organizations", page_size=1000)), 2)
        self.assertEqual(client.calls[0], ("/cloudapi/1.0.0/orgs", {"page": 1, "pageSize": 128}))
        self.assertEqual(client.calls[1][1]["page"], 2)

    def test_cross_family_resource_fails_before_network(self):
        client = FakeClient()
        with self.assertRaises(ApiError):
            automation.collect_resource(client, "cloud_accounts")
        self.assertEqual(client.calls, [])

    def test_repeated_page_and_duplicate_identity_fail(self):
        fixtures = (
            [{"content": [{"id": "a"}]}, {"content": [{"id": "a"}]}],
            [{"content": [{"id": "a", "name": "old"}]}, {"content": [{"id": "a", "name": "new"}]}],
        )
        for responses in fixtures:
            with self.subTest(responses=responses), self.assertRaises(ApiError):
                automation.collect_resource(FakeClient(responses), "blueprints")

    def test_changing_total_and_empty_early_page_fail(self):
        fixtures = (
            [{"content": [{"id": "a"}], "totalElements": 3}, {"content": [{"id": "b"}], "totalElements": 4}],
            [{"content": [{"id": "a"}], "totalElements": 2}, {"content": [], "totalElements": 2}],
        )
        for responses in fixtures:
            with self.subTest(responses=responses), self.assertRaises(ApiError):
                automation.collect_resource(FakeClient(responses), "blueprints")

    def test_invalid_metadata_and_response_structures_fail(self):
        for response in (
            [], {"content": ["wrong"]}, {"content": [], "totalElements": -1},
            {"content": [], "totalElements": True}, {"content": [], "last": "true"},
            {"content": [{"id": "a"}], "numberOfElements": 2},
            {"content": [{"id": "a"}], "totalElements": 0},
            {"content": [{"id": "a"}], "number": 1},
        ):
            with self.subTest(response=response), self.assertRaises(ApiError):
                automation.collect_resource(FakeClient([response]), "deployments")

    def test_provider_page_number_mismatch_fails(self):
        with self.assertRaises(ApiError):
            automation.collect_resource(FakeClient([{"values": [], "page": 0}], family="provider"), "regions")

    def test_max_pages_stops_before_exporting_incomplete_resource(self):
        with self.assertRaisesRegex(ApiError, "max_pages"):
            automation.collect_resource(FakeClient([{"content": [{"id": "a"}]}]), "blueprints", max_pages=1)

    def test_conflicting_end_markers_fail(self):
        for response in (
            {"content": [{"id": "a"}], "totalElements": 1, "last": False},
            {"content": [], "last": False},
            {"content": [{"id": "a"}], "totalElements": 1, "totalPages": 2, "last": True},
        ):
            with self.subTest(response=response), self.assertRaises(ApiError):
                automation.collect_resource(FakeClient([response]), "blueprints")


if __name__ == "__main__":
    unittest.main()
