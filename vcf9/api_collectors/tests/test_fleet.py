"""Offline VCF Fleet LCM behavior tests. Author: Paul Bryant."""

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from vcf_inventory.http_client import ApiError
from vcf_inventory.products import fleet


def client(responses=(), **options):
    target = {"component": "vcf_fleet", "token_env": "FLEET_TEST_TOKEN"}
    target.update(options)
    return SimpleNamespace(target=target, headers={}, get=Mock(side_effect=list(responses)), request=Mock())


def page(key, rows, number=1, pages=1, total=None):
    metadata = {"pageNumber": number, "totalPages": pages}
    if total is not None:
        metadata["totalElements"] = total
    return {key: rows, "pageMetadata": metadata}


class FleetTests(unittest.TestCase):
    @patch.dict(os.environ, {"FLEET_TEST_TOKEN": "provided-jwt"})
    def test_bearer_authentication_and_cleanup_do_not_mutate_service(self):
        api = client()
        fleet.authenticate(api)
        self.assertEqual(api.headers["Authorization"], "Bearer provided-jwt")
        fleet.close(api)
        self.assertNotIn("Authorization", api.headers)
        api.request.assert_not_called()
        self.assertEqual(fleet.ALLOWED_OPERATIONS, set())

    def test_invalid_credential_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            fleet.validate_target({"component": "vcf_fleet"})

    def test_component_pages_use_one_based_numbers_and_sddc_page_count(self):
        # One SDDC page can contain several components. totalElements is not
        # assumed to be the number of component records in this collection.
        api = client([
            page("components", [{"id": "one"}, {"id": "two"}], number=1, pages=2, total=2),
            page("components", [{"id": "three"}], number=2, pages=2, total=2),
        ])
        rows = fleet.collect_resource(api, "components", page_size=1000)
        self.assertEqual(len(rows), 3)
        self.assertEqual([call.kwargs["params"]["pageNumber"] for call in api.get.call_args_list], [1, 2])
        self.assertTrue(all(call.kwargs["params"]["pageSize"] == 100 for call in api.get.call_args_list))
        self.assertTrue(all(call.args[0] == "/fleet-lcm/v1/components" for call in api.get.call_args_list))

    def test_component_nodes_fan_out_from_discovered_ids_and_paginate(self):
        api = client([
            page("components", [{"id": "component-1"}]),
            page("nodes", [{"id": "node-1"}], number=1, pages=2, total=2),
            page("nodes", [{"id": "node-2"}], number=2, pages=2, total=2),
        ])
        rows = fleet.collect_resource(api, "component_nodes")
        self.assertEqual([row["component_id"] for row in rows], ["component-1", "component-1"])
        self.assertEqual(api.get.call_args_list[1].args[0], "/fleet-lcm/v1/components/component-1/nodes")

    def test_component_status_preserves_service_value_and_identity(self):
        api = client([page("components", [{"id": "component-1"}]), {"id": "component-1", "status": "Running"}])
        self.assertEqual(fleet.collect_resource(api, "component_statuses"), [
            {"id": "component-1", "component_id": "component-1", "status": "Running"}])
        api.get.assert_called_with("/fleet-lcm/v1/components/component-1/status")

    def test_status_of_a_different_component_is_not_exported(self):
        api = client([page("components", [{"id": "component-1"}]), {"id": "other", "status": "Running"}])
        with self.assertRaises(ApiError):
            fleet.collect_resource(api, "component_statuses")

    def test_changed_or_repeated_component_pages_fail(self):
        for responses in (
            [page("components", [{"id": "one"}], pages=2), page("components", [{"id": "two"}], number=2, pages=3)],
            [page("components", [{"id": "one"}], pages=2), page("components", [{"id": "one"}], number=2, pages=2)],
        ):
            with self.subTest(responses=responses), self.assertRaises(ApiError):
                fleet.collect_resource(client(responses), "components")

    def test_incomplete_node_total_is_not_success(self):
        api = client([page("components", [{"id": "component-1"}]), page("nodes", [{"id": "node-1"}], total=2)])
        with self.assertRaises(ApiError):
            fleet.collect_resource(api, "component_nodes")

    def test_page_limit_and_unsafe_discovered_identifier_fail(self):
        with self.assertRaises(ApiError):
            fleet.collect_resource(client([page("components", [{"id": "one"}], pages=2)]), "components", max_pages=1)
        api = client([page("components", [{"id": "../escape"}])])
        with self.assertRaises(ApiError):
            fleet.collect_resource(api, "component_nodes")
        self.assertEqual(api.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
