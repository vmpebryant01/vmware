"""Offline HCX and recovery contract tests. Author: Paul Bryant."""

import base64
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from vcf_inventory.http_client import ApiError
from vcf_inventory.products import hcx, protection_recovery as recovery


def client(component="hcx", **options):
    target = {"component": component, "username_env": "INVENTORY_USER", "password_env": "INVENTORY_PASS"}
    target.update(options)
    return SimpleNamespace(target=target, headers={}, get=Mock(), request=Mock(), _product_state={})


def page(rows, total=None, offset=0, **extra):
    meta = {"offset": offset, **extra}
    if total is not None:
        meta["total"] = total
    return {"list": rows, "_meta": meta}


class HcxTests(unittest.TestCase):
    @patch.dict(os.environ, {"INVENTORY_USER": "reader@example.test", "INVENTORY_PASS": "secret"})
    def test_login_uses_response_header_and_json_credentials(self):
        api = client()
        api.request.return_value = (None, {"x-hm-authorization": "session-value"})
        hcx.authenticate(api)
        self.assertEqual(api.headers, {"x-hm-authorization": "session-value"})
        api.request.assert_called_once_with(
            "POST", "/hybridity/api/sessions",
            body={"username": "reader@example.test", "password": "secret"}, include_headers=True,
        )

    @patch.dict(os.environ, {"INVENTORY_USER": "reader", "INVENTORY_PASS": "secret"})
    def test_login_does_not_guess_a_token_from_the_body(self):
        api = client()
        api.request.return_value = ({"token": "wrong-location"}, {})
        with self.assertRaises(ApiError):
            hcx.authenticate(api)

    @patch.dict(os.environ, {"HCX_TOKEN": "provided-token"})
    def test_external_tokens_make_no_login_request(self):
        for source, header, expected in (
            ("session_token", "x-hm-authorization", "provided-token"),
            ("vcf_sso", "Authorization", "Bearer provided-token"),
        ):
            with self.subTest(source=source):
                api = client(auth_source=source, token_env="HCX_TOKEN")
                hcx.authenticate(api)
                self.assertEqual(api.headers[header], expected)
                api.request.assert_not_called()

    def test_inventory_uses_documented_collection_envelopes(self):
        api = client()
        api.get.return_value = {"success": True, "data": {"items": [{"endpointId": "site-1"}]}}
        self.assertEqual(hcx.collect_resource(api, "site_pairings"), [{"endpointId": "site-1"}])
        api.get.assert_called_with("/hybridity/api/cloudConfigs")
        api.get.return_value = {"items": [{"serviceMeshId": "mesh-1"}]}
        self.assertEqual(hcx.collect_resource(api, "service_meshes"), [{"serviceMeshId": "mesh-1"}])
        api.get.assert_called_with("/hybridity/api/interconnect/serviceMesh")

    def test_partial_failed_and_unrecognized_responses_fail(self):
        api = client()
        for payload in (
            {"items": [], "success": False},
            {"items": [], "completed": False},
            {"items": [], "errors": [{"code": "unavailable"}]},
            {"items": [{"id": "partial"}], "paging": {"totalSize": 200}},
            {"results": []},
        ):
            with self.subTest(payload=payload), self.assertRaises(ApiError):
                api.get.return_value = payload
                hcx.collect_resource(api, "appliances")

    def test_close_does_not_invent_an_undocumented_logout_endpoint(self):
        api = client()
        api.headers["x-hm-authorization"] = "session"
        hcx.close(api)
        self.assertNotIn("x-hm-authorization", api.headers)
        api.request.assert_not_called()


class RecoveryTests(unittest.TestCase):
    def test_remote_credentials_require_an_explicit_pairing_scope(self):
        for options in (
            {"remote_username_env": "REMOTE_USER", "remote_password_env": "REMOTE_PASS"},
            {"pairing_id": "pair-1", "remote_username_env": "REMOTE_USER"},
            {"pairing_id": "../pair-1", "remote_username_env": "REMOTE_USER", "remote_password_env": "REMOTE_PASS"},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                recovery.validate_target(client("live_site_recovery", resources=["pairings"], **options).target)

    def test_local_discovery_is_valid_without_remote_credentials(self):
        recovery.validate_target(client("live_site_recovery", resources=["pairings"]).target)

    def test_credentials_mode_requires_remote_login_for_pair_inventory(self):
        with self.assertRaises(ValueError):
            recovery.validate_target(client("live_site_recovery", resources=["protection_groups"]).target)

    @patch.dict(os.environ, {"INVENTORY_USER": "reader", "INVENTORY_PASS": "p:a ss"})
    def test_local_login_and_logout_use_only_the_matching_gateway(self):
        for component, base in recovery.BASE_PATHS.items():
            with self.subTest(component=component):
                api = client(component, resources=["pairings"])
                api.request.return_value = {"session_id": "owned-session"}
                recovery.authenticate(api)
                expected = "Basic " + base64.b64encode(b"reader:p:a ss").decode("ascii")
                api.request.assert_called_once_with("POST", base + "/session", headers={"Authorization": expected})
                self.assertEqual(api.headers, {"x-dr-session": "owned-session"})
                recovery.close(api)
                api.request.assert_called_with("DELETE", base + "/session")
                self.assertNotIn("x-dr-session", api.headers)

    @patch.dict(os.environ, {"RECOVERY_TOKEN": "external-session"})
    def test_external_session_is_never_logged_out_by_collector(self):
        api = client("live_site_recovery", auth_source="session_token", token_env="RECOVERY_TOKEN")
        recovery.authenticate(api)
        recovery.close(api)
        api.request.assert_not_called()

    def test_short_pages_continue_using_object_offsets(self):
        api = client("live_site_recovery", resources=["pairings"])
        api.get.side_effect = [page([{"pairing_id": "a"}], total=2), page([{"pairing_id": "b"}], total=2, offset=1)]
        self.assertEqual(len(recovery.collect_resource(api, "pairings", page_size=100)), 2)
        self.assertEqual(api.get.call_args_list[1].kwargs["params"], {"limit": 100, "offset": 1})

    def test_pagination_does_not_follow_server_urls(self):
        api = client("live_site_recovery", resources=["pairings"])
        api.get.side_effect = [
            page([{"pairing_id": "a"}], total=2, links={"next": {"href": "https://other.example.test/steal"}}),
            page([{"pairing_id": "b"}], total=2, offset=1),
        ]
        recovery.collect_resource(api, "pairings")
        self.assertTrue(all(call.args[0] == "/api/rest/srm/v2/pairings" for call in api.get.call_args_list))

    def test_partial_errors_and_changed_totals_fail(self):
        for responses in (
            [page([], total=0, errors=[{"code": "remote-unavailable"}])],
            [page([{"pairing_id": "a"}], total=2), page([{"pairing_id": "b"}], total=3, offset=1)],
            [page([{"pairing_id": "a"}], total=2), page([], offset=1)],
        ):
            api = client("live_site_recovery", resources=["pairings"])
            api.get.side_effect = responses
            with self.subTest(responses=responses), self.assertRaises(ApiError):
                recovery.collect_resource(api, "pairings")

    def test_missing_totals_continue_until_empty_and_repeated_pages_fail(self):
        api = client("live_site_recovery", resources=["pairings"])
        api.get.side_effect = [{"list": [{"pairing_id": "a"}]}, {"list": []}]
        self.assertEqual(recovery.collect_resource(api, "pairings"), [{"pairing_id": "a"}])
        api.get.side_effect = [{"list": [{"pairing_id": "a"}]}] * 2
        with self.assertRaises(ApiError):
            recovery.collect_resource(api, "pairings", max_pages=3)

    @patch.dict(os.environ, {"REMOTE_USER": "remote-reader", "REMOTE_PASS": "remote-password"})
    def test_remote_login_is_scoped_and_replication_status_is_requested(self):
        api = client("vsphere_replication", pairing_id="pair-1", remote_username_env="REMOTE_USER",
                     remote_password_env="REMOTE_PASS", source_vc_guid="source-vc")
        api.headers["x-dr-session"] = "local-session"
        api.get.side_effect = [
            page([{"pairing_id": "pair-1"}, {"pairing_id": "other-pair"}], total=2),
            page([{"id": "replication-1"}], total=1),
        ]
        rows = recovery.collect_resource(api, "replications")
        self.assertEqual(rows, [{"id": "replication-1", "pairing_id": "pair-1"}])
        self.assertEqual(api.request.call_args.args, ("POST", "/api/rest/vr/v2/pairings/pair-1/remote-session"))
        params = api.get.call_args.kwargs["params"]
        self.assertEqual(params["extended_info"], "true")
        self.assertEqual(params["source_vc_guid"], "source-vc")
        self.assertNotIn("Authorization", api.headers)

    def test_an_unseen_configured_pairing_fails(self):
        api = client("live_site_recovery", resources=["pairings"], pairing_id="missing")
        api.get.return_value = page([{"pairing_id": "visible"}], total=1)
        with self.assertRaises(ApiError):
            recovery.collect_resource(api, "pairings")

    def test_remote_login_allowlist_excludes_recovery_actions(self):
        allowed = "/api/rest/srm/v2/pairings/pair-1/remote-session"
        self.assertTrue(recovery.allow_request("live_site_recovery", "POST", allowed))
        for method, path in (
            ("DELETE", allowed),
            ("POST", "/api/rest/srm/v2/pairings/../remote-session"),
            ("POST", "/api/rest/srm/v2/pairings/a%2F..%2Fother/remote-session"),
            ("POST", "/api/rest/srm/v2/pairings/a%252Fother/remote-session"),
            ("POST", "/api/rest/srm/v2/pairings/pair-1/recovery-management/plans/plan-1/actions/recovery"),
            ("POST", "https://other.example.test" + allowed),
        ):
            with self.subTest(method=method, path=path):
                self.assertFalse(recovery.allow_request("live_site_recovery", method, path))


if __name__ == "__main__":
    unittest.main()
