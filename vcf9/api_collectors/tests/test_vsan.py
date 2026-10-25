"""Documented vSAN query and saved-report contracts. Author: Paul Bryant."""

import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from vcf_inventory.http_client import ApiError, HttpClient
from vcf_inventory.products import vsan
from vcf_inventory.vsan_report import build_vsan_report


def client(**options):
    target = {"name": "storage", "component": "vsan", "endpoint": "https://vc.example.test",
              "cluster_ids": ["domain-c123"], "username_env": "VSAN_TEST_USER", "password_env": "VSAN_TEST_PASSWORD"}
    target.update(options)
    return SimpleNamespace(target=target, headers={}, get=Mock(return_value={
        "about": {"apiType": "VirtualCenter", "apiVersion": "9.1.1.0"},
        "sessionManager": {"type": "SessionManager", "value": "session-manager-7"}}), request=Mock())


def authenticated_client(**options):
    current = client(**options)
    current.headers["vmware-api-session-id"] = "example-json-session"
    current._product_state = {"vsan_api_version": current.target.get("api_version", "9.0.0.0"),
                              "vsan_server_api_version": "9.1.1.0", "vsan_session_manager": "session-manager-7",
                              "vsan_owned_session": False}
    return current


def health(cluster="domain-c123", **fields):
    result = {"cluster": {"type": "ClusterComputeResource", "value": cluster},
              "timestamp": "2026-10-24T12:00:00Z", "overallHealth": "yellow", "overallHealthDescription": "Disk warning",
              "healthScore": 85, "objectHealth": {"objectHealthDetail": [{"health": "healthy", "numObjects": 8},
                                                                         {"health": "inaccessible", "numObjects": 2}]},
              "physicalDisksHealth": [{"hostname": "host.example.test", "overallHealth": "yellow", "disks": [
                  {"name": "naa.example", "uuid": "disk-1", "operationalHealth": "yellow", "capacity": 1000, "usedCapacity": 500}]}],
              "diskBalance": {"varianceThreshold": 30, "disks": [{"uuid": "disk-1", "fullness": 50}]}}
    result.update(fields)
    return result


def run(health_records=None, space_records=None, target="storage", unavailable=None):
    resources = {}
    if health_records is not None:
        resources[(target, "vsan", "health_summary")] = {"collected_at": "2026-10-25T12:00:00Z", "records": health_records}
    if space_records is not None:
        resources[(target, "vsan", "space_usage")] = {"collected_at": "2026-10-25T12:01:00Z", "records": space_records}
    return {"summary": {"status": "success"}, "resources": resources, "unavailable": unavailable or {}}


class AuthenticationTests(unittest.TestCase):
    def test_json_login_uses_discovered_manager_and_response_header(self):
        current = client()
        current.request.return_value = ({"key": "different-user-session-key", "userName": "reader"},
                                        {"vmware-api-session-id": "example-json-session"})
        with patch.dict(os.environ, {"VSAN_TEST_USER": "reader", "VSAN_TEST_PASSWORD": "example-password"}):
            vsan.authenticate(current)
        current.get.assert_called_once_with("/sdk/vim25/9.0.0.0/ServiceInstance/ServiceInstance/content")
        current.request.assert_called_once_with("POST", "/sdk/vim25/9.0.0.0/SessionManager/session-manager-7/Login",
                                                body={"userName": "reader", "password": "example-password"}, include_headers=True)
        self.assertEqual(current.headers["vmware-api-session-id"], "example-json-session")
        self.assertTrue(current._product_state["vsan_owned_session"])

    def test_user_session_key_is_not_substituted_for_missing_header(self):
        current = client()
        current.request.return_value = ({"key": "not-a-header"}, {})
        with patch.dict(os.environ, {"VSAN_TEST_USER": "reader", "VSAN_TEST_PASSWORD": "example-password"}), self.assertRaises(ApiError):
            vsan.authenticate(current)
        self.assertNotIn("vmware-api-session-id", current.headers)

    def test_supplied_json_session_is_never_revoked(self):
        current = client(token_env="VSAN_TEST_SESSION")
        current.target.pop("username_env")
        current.target.pop("password_env")
        with patch.dict(os.environ, {"VSAN_TEST_SESSION": "example-supplied-session"}):
            vsan.authenticate(current)
        self.assertEqual(current.headers["vmware-api-session-id"], "example-supplied-session")
        vsan.close(current)
        current.request.assert_not_called()
        self.assertNotIn("vmware-api-session-id", current.headers)

    def test_wrong_product_or_schema_fails_before_credentials_are_sent(self):
        for about in ({"apiType": "HostAgent", "apiVersion": "9.0.0.0"},
                      {"apiType": "VirtualCenter", "apiVersion": "8.0.3.0"},
                      {"apiType": "VirtualCenter", "apiVersion": "9.0"},
                      {"apiType": "VirtualCenter", "apiVersion": "10.0.0.0"}):
            current = client()
            current.get.return_value["about"] = about
            with self.subTest(about=about), self.assertRaises(ApiError):
                vsan.authenticate(current)
            current.request.assert_not_called()

    def test_newer_configured_schema_than_server_is_rejected(self):
        current = client(api_version="9.1.1.0")
        current.get.return_value["about"]["apiVersion"] = "9.0.0.0"
        with self.assertRaises(ApiError):
            vsan.authenticate(current)
        current.request.assert_not_called()

    def test_logout_clears_owned_session_even_if_request_fails(self):
        current = authenticated_client()
        current._product_state["vsan_owned_session"] = True
        current.request.side_effect = ApiError("Connection failed.")
        with self.assertRaises(ApiError):
            vsan.close(current)
        current.request.assert_called_once_with("POST", "/sdk/vim25/9.0.0.0/SessionManager/session-manager-7/Logout")
        self.assertNotIn("vmware-api-session-id", current.headers)
        self.assertFalse(current._product_state["vsan_owned_session"])


class QueryTests(unittest.TestCase):
    def test_each_explicit_cluster_uses_only_cached_query_and_preserves_timestamp(self):
        current = authenticated_client(cluster_ids=["domain-c123", "domain-c456"])
        current.request.side_effect = [health(), health("domain-c456")]
        rows = vsan.collect_resource(current, "health_summary")
        self.assertEqual([row["cluster_id"] for row in rows], ["domain-c123", "domain-c456"])
        self.assertEqual(rows[0]["timestamp"], "2026-10-24T12:00:00Z")
        for call in current.request.call_args_list:
            self.assertTrue(call.kwargs["body"]["fetchFromCache"])
            self.assertIs(call.kwargs["body"]["includeObjUuids"], False)
            self.assertEqual(call.kwargs["body"]["fields"], list(vsan.HEALTH_FIELDS))
            self.assertTrue(call.args[1].endswith("/VsanQueryVcClusterHealthSummary"))

    def test_space_query_returns_native_byte_capacity_without_pagination(self):
        current = authenticated_client()
        current.request.return_value = {"totalCapacityB": 1000, "freeCapacityB": 100, "spaceOverview": {"physicalUsedB": 900}}
        rows = vsan.collect_resource(current, "space_usage", page_size=10, max_pages=1)
        self.assertEqual(rows[0]["totalCapacityB"], 1000)
        current.request.assert_called_once_with("POST", "/sdk/vim25/9.0.0.0/vsan/VsanSpaceReportSystem/vsan-cluster-space-report-system/VsanQuerySpaceUsage",
                                                body={"cluster": {"type": "ClusterComputeResource", "value": "domain-c123"}, "whatifCapacityOnly": False})

    def test_read_allowlist_rejects_active_tests_extra_options_and_unsafe_cluster_ids(self):
        path = vsan.RESOURCE_PATHS["vsan"]["health_summary"].format(api_version="9.0.0.0")
        body = {"cluster": {"type": "ClusterComputeResource", "value": "domain-c123"},
                "fetchFromCache": True, "includeObjUuids": False, "fields": list(vsan.HEALTH_FIELDS)}
        self.assertTrue(vsan.allow_query("vsan", "POST", path, None, body))
        for modified in (dict(body, fetchFromCache=False), dict(body, includeObjUuids=True), dict(body, spec={}),
                         dict(body, cluster={"type": "ClusterComputeResource", "value": "../domain-c123"}),
                         dict(body, cluster={"type": "HostSystem", "value": "domain-c123"})):
            with self.subTest(body=modified):
                self.assertFalse(vsan.allow_query("vsan", "POST", path, None, modified))
        self.assertFalse(vsan.allow_query("vsan", "POST", path + "Task", None, body))
        self.assertFalse(vsan.allow_query("vsan", "POST", path, {"unexpected": True}, body))
        self.assertFalse(vsan.allow_request("vsan", "POST", path))
        self.assertFalse(vsan.allow_request("vsan", "POST", "/sdk/vim25/9.0.0.0/SessionManager/../Logout"))

    def test_invalid_cluster_scope_or_api_release_is_rejected_without_requests(self):
        for options in ({"cluster_ids": []}, {"cluster_ids": ["domain-c123", "domain-c123"]},
                        {"cluster_ids": ["Cluster display name"]}, {"cluster_ids": ["../domain-c123"]},
                        {"api_version": "9.9.9.9"}, {"token_env": "VSAN_TEST_TOKEN"}):
            current = client(**options)
            with self.subTest(options=options), self.assertRaises(ValueError):
                vsan.validate_target(current.target)
            current.get.assert_not_called()
            current.request.assert_not_called()

    def test_other_cluster_fault_envelopes_and_impossible_capacity_fail(self):
        for resource, payload in (("health_summary", health("domain-c999")), ("health_summary", {"_typeName": "VsanFault"}),
                                  ("space_usage", {"totalCapacityB": 100, "freeCapacityB": 200}),
                                  ("space_usage", {"totalCapacityB": True}), ("space_usage", [])):
            current = authenticated_client()
            current.request.return_value = payload
            with self.subTest(resource=resource, payload=payload), self.assertRaises(ApiError):
                vsan.collect_resource(current, resource)

    def test_optional_sections_can_be_absent_without_fabricating_them(self):
        current = authenticated_client()
        current.request.return_value = {"overallHealth": "unknown", "overallHealthDescription": "No cached details"}
        row = vsan.collect_resource(current, "health_summary")[0]
        self.assertNotIn("objectHealth", row)
        self.assertNotIn("physicalDisksHealth", row)

    def test_preflight_scope_is_first_cluster_and_cached_health_only(self):
        current = client(cluster_ids=["domain-c123", "domain-c456"])
        method, path, params, body, note = vsan.probe_request(current.target, "health_summary")
        self.assertEqual(body["cluster"]["value"], "domain-c123")
        self.assertTrue(body["fetchFromCache"])
        self.assertTrue(vsan.allow_query("vsan", method, path, params, body))
        self.assertIn("remaining clusters are not probed", note)


class TransportContractTests(unittest.TestCase):
    def test_real_transport_dispatches_only_verified_session_and_cached_query_contracts(self):
        target = dict(client().target, url="https://vc.example.test")
        current = HttpClient(target, retries=0)

        def response(payload, headers=None):
            result = MagicMock()
            result.__enter__.return_value = result
            result.read.return_value = b"" if payload is None else json.dumps(payload).encode("utf-8")
            result.headers = headers or {}
            return result

        current.opener = Mock()
        current.opener.open.side_effect = [
            response(client().get.return_value),
            response({"key": "different-body-session-key"}, {"vmware-api-session-id": "example-json-session"}),
            response(health()), response(None),
        ]
        with patch.dict(os.environ, {"VSAN_TEST_USER": "reader", "VSAN_TEST_PASSWORD": "example-password"}):
            current.authenticate()
        rows = vsan.collect_resource(current, "health_summary")
        query_request = current.opener.open.call_args.args[0]
        self.assertEqual(query_request.get_header("Vmware-api-session-id"), "example-json-session")
        self.assertIs(json.loads(query_request.data)["fetchFromCache"], True)
        with self.assertRaises(ApiError):
            current.request("POST", query_request.selector + "Task", body={"cluster": {"type": "ClusterComputeResource", "value": "domain-c123"}})
        current.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(current.opener.open.call_count, 4)
        self.assertNotIn("vmware-api-session-id", current.headers)


class ReportTests(unittest.TestCase):
    def test_report_preserves_observation_time_and_native_states_and_calculates_capacity(self):
        source = run([dict(health(), cluster_id="domain-c123")], [{"cluster_id": "domain-c123", "totalCapacityB": 1000, "freeCapacityB": 100}])
        original = copy.deepcopy(source)
        report = build_vsan_report(source, max_used_percent=80)
        row = report["records"][0]
        self.assertEqual(report["status"], "success")
        self.assertEqual(row["overall_health"], "yellow")
        self.assertEqual(row["health_observed_at"], "2026-10-24T12:00:00Z")
        self.assertEqual(row["health_collected_at"], "2026-10-25T12:00:00Z")
        self.assertEqual(row["object_health"]["total_objects"], 10)
        self.assertEqual(row["physical_disks"]["returned_disk_count"], 1)
        self.assertEqual(row["capacity"]["used_capacity_bytes"], 900)
        self.assertEqual(row["capacity"]["used_percent"], 90)
        self.assertTrue(row["capacity"]["threshold_exceeded"])
        self.assertEqual(source, original)

    def test_missing_or_host_failed_sections_remain_unknown_and_report_partial(self):
        summary = {"cluster_id": "domain-c123", "overallHealth": "green", "physicalDisksHealth": [{"hostname": "host.example.test", "overallHealth": "green", "error": {"fault": "unavailable"}}]}
        report = build_vsan_report(run([summary], [{"cluster_id": "domain-c123", "totalCapacityB": 1000}]))
        row = report["records"][0]
        self.assertEqual(report["status"], "partial")
        self.assertIsNone(row["object_health"]["total_objects"])
        self.assertIsNone(row["physical_disks"]["returned_disk_count"])
        self.assertEqual(row["physical_disks"]["hosts"][0]["availability"], "collection_error")
        self.assertIsNone(row["capacity"]["used_capacity_bytes"])
        self.assertIsNone(row["capacity"]["threshold_exceeded"])

    def test_duplicate_cluster_summaries_are_ambiguous_and_targets_are_separate(self):
        first = dict(health(), cluster_id="domain-c123")
        source = run([first, first], [{"cluster_id": "domain-c123", "totalCapacityB": 1000, "freeCapacityB": 500}])
        source["resources"].update(run([first], None, target="other")["resources"])
        report = build_vsan_report(source)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(len(report["records"]), 2)
        storage = next(row for row in report["records"] if row["target"] == "storage")
        self.assertEqual(storage["health_availability"], "ambiguous")
        self.assertIsNone(storage["overall_health"])

    def test_zero_capacity_and_failed_resources_do_not_become_zero_percent_healthy(self):
        report = build_vsan_report(run([dict(health(), cluster_id="domain-c123")], [{"cluster_id": "domain-c123", "totalCapacityB": 0, "freeCapacityB": 0}],
                                      unavailable={("storage", "vsan", "health_summary"): "Unavailable."}))
        self.assertEqual(report["status"], "partial")
        self.assertIsNone(report["records"][0]["capacity"]["used_percent"])
        self.assertIsNone(report["records"][0]["capacity"]["threshold_exceeded"])
        empty = build_vsan_report(run(None, None, unavailable={("storage", "vsan", "health_summary"): "Unavailable."}))
        self.assertEqual(empty["status"], "partial")
        self.assertEqual(empty["records"], [])

    def test_invalid_thresholds_are_rejected(self):
        for threshold in (True, -1, 101, float("nan"), float("inf"), "80"):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                build_vsan_report(run(), max_used_percent=threshold)

    def test_saved_cluster_scope_exposes_missing_clusters_and_excludes_unrequested_rows(self):
        source = run([dict(health(), cluster_id="domain-c123"), dict(health("domain-c999"), cluster_id="domain-c999")],
                     [{"cluster_id": "domain-c123", "totalCapacityB": 1000, "freeCapacityB": 500}])
        for document in source["resources"].values():
            document["cluster_ids"] = ["domain-c123", "domain-c456"]
        report = build_vsan_report(source)
        self.assertEqual(report["status"], "partial")
        self.assertEqual([row["cluster_id"] for row in report["records"]], ["domain-c123", "domain-c456"])
        missing = report["records"][1]
        self.assertEqual(missing["health_availability"], "not_collected")
        self.assertEqual(missing["capacity"]["availability"], "not_collected")
        self.assertIsNone(missing["overall_health"])
        self.assertIsNone(missing["capacity"]["used_percent"])


if __name__ == "__main__":
    unittest.main()
