"""Offline VCF Operations behavior tests. Author: Paul Bryant."""

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from vcf_inventory.http_client import ApiError
from vcf_inventory.products import operations


def client(responses=(), **target_options):
    target = {"component": "vcf_operations", "name": "operations-test",
              "url": "https://operations.example.test", "username_env": "OPS_TEST_USERNAME",
              "password_env": "OPS_TEST_PASSWORD"}
    target.update(target_options)
    return SimpleNamespace(target=target, headers={}, _product_state={},
                           get=Mock(side_effect=list(responses)), request=Mock())


class AuthenticationTests(unittest.TestCase):
    @patch.dict(os.environ, {"OPS_TEST_USERNAME": "reader", "OPS_TEST_PASSWORD": "test-password"})
    def test_local_login_uses_documented_body_and_opstoken_header(self):
        current = client(auth_source="Local Directory")
        current.request.return_value = {"token": "example-token", "validity": 123456789}
        operations.authenticate(current)
        current.request.assert_called_once_with(
            "POST", "/suite-api/api/auth/token/acquire",
            body={"username": "reader", "password": "test-password", "authSource": "Local Directory"})
        self.assertEqual(current.headers["Authorization"], "OpsToken example-token")
        self.assertTrue(current._product_state["operations_owned_token"])

    @patch.dict(os.environ, {"OPS_TEST_TOKEN": "example-token"})
    def test_supplied_api_token_defaults_to_opstoken(self):
        current = client(token_env="OPS_TEST_TOKEN")
        operations.authenticate(current)
        current.request.assert_not_called()
        self.assertEqual(current.headers["Authorization"], "OpsToken example-token")
        operations.close(current)
        current.request.assert_not_called()
        self.assertNotIn("Authorization", current.headers)

    @patch.dict(os.environ, {"OPS_TEST_TOKEN": "example-jwt"})
    def test_supplied_identity_token_can_use_bearer(self):
        current = client(token_env="OPS_TEST_TOKEN", token_scheme="Bearer")
        operations.authenticate(current)
        self.assertEqual(current.headers["Authorization"], "Bearer example-jwt")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_credentials_are_an_explicit_failure(self):
        current = client()
        with self.assertRaises(ApiError):
            operations.authenticate(current)
        current.request.assert_not_called()

    @patch.dict(os.environ, {"OPS_TEST_USERNAME": "reader", "OPS_TEST_PASSWORD": "test-password"})
    def test_bad_authentication_response_cannot_become_authenticated(self):
        for response in ({"token": ""}, {"accessToken": "wrong-schema"}, [], {"token": "bad\r\nheader"}):
            with self.subTest(response=response):
                current = client()
                current.request.return_value = response
                with self.assertRaises(ApiError):
                    operations.authenticate(current)
                self.assertNotIn("Authorization", current.headers)
                self.assertFalse(current._product_state["operations_owned_token"])

    def test_owned_token_is_released_and_removed_after_cleanup_failure(self):
        current = client()
        current.headers["Authorization"] = "OpsToken example-token"
        current._product_state["operations_owned_token"] = True
        current.request.side_effect = ApiError("Connection failed.")
        with self.assertRaises(ApiError):
            operations.close(current)
        current.request.assert_called_once_with("POST", "/suite-api/api/auth/token/release")
        self.assertNotIn("Authorization", current.headers)
        self.assertFalse(current._product_state["operations_owned_token"])


class CollectionTests(unittest.TestCase):
    def test_resources_follow_total_count_after_short_page(self):
        current = client([
            {"resourceList": [{"identifier": "resource-1"}], "pageInfo": {"page": 0, "pageSize": 1, "totalCount": 2}},
            {"resourceList": [{"identifier": "resource-2"}], "pageInfo": {"page": 1, "pageSize": 1, "totalCount": 2}},
        ], filters={"resources": {"adapterKind": ["VMWARE"], "resourceKind": ["VirtualMachine"]}})
        rows = operations.collect_resource(current, "resources", page_size=100)
        self.assertEqual([row["identifier"] for row in rows], ["resource-1", "resource-2"])
        self.assertEqual(current.get.call_count, 2)
        current.get.assert_called_with("/suite-api/api/resources", params={
            "adapterKind": ["VMWARE"], "resourceKind": ["VirtualMachine"], "page": 1, "pageSize": 100})

    def test_alerts_use_documented_array_and_zero_based_page_parameters(self):
        current = client([{"alerts": [{"alertId": "alert-1"}], "pageInfo": {"page": 0, "totalCount": 1}}])
        self.assertEqual(operations.collect_resource(current, "alerts"), [{"alertId": "alert-1"}])
        current.get.assert_called_once_with("/suite-api/api/alerts", params={"page": 0, "pageSize": 100})

    def test_without_total_count_short_pages_continue_until_empty(self):
        current = client([{"resourceList": [{"identifier": "resource-1"}]},
                          {"resourceList": [{"identifier": "resource-2"}]}, {"resourceList": []}])
        rows = operations.collect_resource(current, "resources", page_size=100)
        self.assertEqual(len(rows), 2)
        self.assertEqual(current.get.call_count, 3)

    def test_explicit_zero_total_allows_omitted_optional_array(self):
        current = client([{"pageInfo": {"page": 0, "totalCount": 0}}])
        self.assertEqual(operations.collect_resource(current, "resources"), [])

    def test_missing_collection_without_zero_total_is_an_error(self):
        for response in ({}, {"message": "unexpected"}, [], {"resourceList": ["wrong-row"]}):
            with self.subTest(response=response), self.assertRaises(ApiError):
                operations.collect_resource(client([response]), "resources")

    def test_count_change_or_premature_empty_page_is_an_error(self):
        first = {"resourceList": [{"identifier": "resource-1"}], "pageInfo": {"page": 0, "totalCount": 3}}
        for second in ({"resourceList": [], "pageInfo": {"page": 1, "totalCount": 3}},
                       {"resourceList": [{"identifier": "resource-2"}], "pageInfo": {"page": 1, "totalCount": 2}}):
            with self.subTest(response=second), self.assertRaises(ApiError):
                operations.collect_resource(client([first, second]), "resources")

    def test_repeated_identifiers_are_an_error(self):
        current = client([
            {"resourceList": [{"identifier": "resource-1"}], "pageInfo": {"page": 0, "totalCount": 2}},
            {"resourceList": [{"identifier": "resource-1", "description": "changed"}], "pageInfo": {"page": 1, "totalCount": 2}},
        ])
        with self.assertRaises(ApiError):
            operations.collect_resource(current, "resources")

    def test_unexpected_page_number_or_invalid_total_is_an_error(self):
        for page_info in ({"page": 1}, {"page": False}, {"totalCount": -1}, {"totalCount": True}, {"pageSize": 0}):
            with self.subTest(page_info=page_info), self.assertRaises(ApiError):
                operations.collect_resource(client([{"alerts": [], "pageInfo": page_info}]), "alerts")

    def test_maximum_pages_stops_without_returning_partial_inventory(self):
        current = client([{"alerts": [{"alertId": "alert-1"}]}])
        with self.assertRaises(ApiError):
            operations.collect_resource(current, "alerts", max_pages=1)

    def test_adapters_do_not_send_undocumented_page_parameters(self):
        current = client([{"adapterInstancesInfoDto": [{"id": "adapter-1"}]}],
                         filters={"adapters": {"adapterKindKey": "VMWARE"}})
        self.assertEqual(operations.collect_resource(current, "adapters"), [{"id": "adapter-1"}])
        current.get.assert_called_once_with("/suite-api/api/adapters", params={"adapterKindKey": "VMWARE"})

    def test_policies_use_lowercase_boolean_filter_without_pagination(self):
        current = client([{"policySummaries": [{"id": "policy-1"}]}], filters={"policies": {"activesOnly": True}})
        self.assertEqual(operations.collect_resource(current, "policies"), [{"id": "policy-1"}])
        current.get.assert_called_once_with("/suite-api/api/policies", params={"activesOnly": "true"})

    def test_http_error_propagates_without_empty_success(self):
        current = client()
        current.get.side_effect = ApiError("Forbidden.", status=403)
        with self.assertRaises(ApiError):
            operations.collect_resource(current, "resources")


class ConfigurationTests(unittest.TestCase):
    def test_unknown_filter_or_user_controlled_pagination_is_rejected(self):
        for filters in ({"resources": {"page": 2}}, {"alerts": {"pageSize": 2}},
                        {"policies": {"unexpected": "value"}}, {"missing": {}}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                operations.validate_target(client(filters=filters).target)

    def test_documented_filters_and_token_scheme_are_accepted(self):
        operations.validate_target(client(token_env="OPS_TEST_TOKEN", token_scheme="Bearer", filters={
            "resources": {"adapterKind": ["VMWARE"]}, "alerts": {"resourceId": ["resource-1"]},
            "adapters": {"adapterKindKey": "VMWARE"}, "policies": {"activesOnly": True}}).target)

    def test_invalid_or_inapplicable_token_scheme_is_rejected(self):
        for options in ({"token_env": "OPS_TEST_TOKEN", "token_scheme": "Basic"}, {"token_scheme": "Bearer"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                operations.validate_target(client(**options).target)


if __name__ == "__main__":
    unittest.main()
