"""Offline assurance contract and evidence-boundary tests. Author: Paul Bryant."""

import copy
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from urllib.error import HTTPError

from vcf_inventory import assurance
from vcf_inventory.assurance_reports import build_access_report, build_backup_report
from vcf_inventory.http_client import ApiError, HttpClient


NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


class Client:
    def __init__(self, component="vcenter", get_responses=(), request_responses=(), **options):
        self.target = {"component": component, **options}
        self.get = Mock(side_effect=list(get_responses))
        self.request = Mock(side_effect=list(request_responses))
        self.collection_metadata = {}


def role_item(identifier="role-1", privileges=None):
    return {"role": identifier, "info": {"name": "Operators", "description": "Inventory access",
                                         "privileges": privileges or ["System.Read"], "system": False}}


def permission_item(identifier="permission-1", role="role-1"):
    return {"permission": identifier, "info": {
        "principal": {"type": "USER", "name": "operator", "domain": "example.local"},
        "object": {"type": "GlobalAcl", "id": "GlobalAcl"}, "role": role, "propagating": True}}


def normalized_role(identifier="role-1", privileges=None):
    return {"id": identifier, "role_id": identifier, "name": "Operators", "system": False,
            "privileges": ["System.Read"] if privileges is None else privileges}


def normalized_permission(identifier="permission-1", **values):
    return {"id": identifier, "permission_id": identifier, "role_id": "role-1", "principal_type": "USER",
            "principal_name": "operator", "principal_domain": "example.local", "object_type": "GlobalAcl",
            "object_id": "GlobalAcl", "propagating": True, **values}


def make_run(component="vcenter", **resources):
    target = {"name": "target-a", "component": component, "endpoint": "https://appliance.example", "resources": []}
    documents = {}
    for resource, rows in resources.items():
        document = {"target": target["name"], "component": component, "endpoint": target["endpoint"],
                    "resource": resource, "records": rows, "record_count": len(rows), "collected_at": NOW.isoformat(),
                    "collection": {"coverage": "complete"}}
        documents[(target["name"], component, resource)] = document
    return {"summary": {"status": "success", "completed_at": NOW.isoformat(), "targets": [target]},
            "resources": documents, "unavailable": {}}


def baseline_entry(**changes):
    permission = normalized_permission()
    return {"target": "target-a", "endpoint": "https://appliance.example",
            **{field: permission[field] for field in ("principal_type", "principal_name", "principal_domain", "role_id",
                                                       "object_type", "object_id", "propagating")}, **changes}


class QueryBoundaryTests(unittest.TestCase):
    def test_resources_are_optional_and_component_scoped(self):
        self.assertEqual(assurance.DEFAULT_RESOURCES, {})
        self.assertEqual(assurance.ALLOWED_OPERATIONS, set())
        self.assertTrue(assurance.supports("vcenter", "backup_jobs"))
        self.assertTrue(assurance.supports("nsx", "backup_history"))
        self.assertFalse(assurance.supports("nsx", "authorization_permissions"))

    def test_exact_read_query_shape_is_allowed(self):
        path = "/api/vcenter/authorization/permissions"
        for iterate in ({"page_size": 1}, {"page_size": 1000, "marker": "opaque:cursor"}):
            self.assertTrue(assurance.allow_query("vcenter", "POST", path, {"action": "list"}, {"iterate": iterate}))

    def test_mutations_and_extra_query_body_fields_are_denied(self):
        path, params, body = "/api/vcenter/authorization/permissions", {"action": "list"}, {"iterate": {"page_size": 100}}
        cases = [
            ("nsx", "POST", path, params, body), ("vcenter", "DELETE", path, params, body),
            ("vcenter", "POST", path + "/permission-1", params, body),
            ("vcenter", "POST", path, None, body), ("vcenter", "POST", path, {"action": "create"}, body),
            ("vcenter", "POST", path, {"action": ["list"]}, body),
            ("vcenter", "POST", path, {"action": "list", "other": "x"}, body),
            ("vcenter", "POST", path, params, {"object": {}, "principal": {}, "role": "x", "propagating": True}),
            ("vcenter", "POST", path, params, {**body, "filter": {"roles": ["x"]}}),
            ("vcenter", "POST", path, params, {"iterate": {"page_size": True}}),
            ("vcenter", "POST", path, params, {"iterate": {"page_size": 1001}}),
            ("vcenter", "POST", path, params, {"iterate": {"page_size": 1, "marker": ""}}),
            ("vcenter", "POST", path, params, {"iterate": {"page_size": 1, "marker": "a\nb"}}),
            ("vcenter", "POST", path, params, {"iterate": {"page_size": 1, "marker": "x", "role": "x"}}),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertFalse(assurance.allow_query(*case))

    def test_probe_is_bounded_and_uses_same_query_guard(self):
        method, path, params, body, scope = assurance.probe_request({"component": "vcenter"}, "authorization_permissions")
        self.assertEqual(body, {"iterate": {"page_size": 1}})
        self.assertTrue(assurance.allow_query("vcenter", method, path, params, body))
        self.assertIn("One page", scope)
        self.assertIsNone(assurance.probe_request({"component": "hcx"}, "backup_jobs"))

    def test_runtime_rejects_unsupported_filters_before_requests(self):
        client = Client(filters={"backup_jobs": {"jobs": ["job-1"]}})
        with self.assertRaises(ApiError):
            assurance.collect_resource(client, "backup_jobs")
        client.get.assert_not_called()

    def test_actual_transport_allows_query_but_rejects_create_same_path(self):
        client = HttpClient({"component": "vcenter", "url": "https://example.invalid"})
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.headers = {}
        response.read.return_value = b'{"items": []}'
        client.opener = Mock()
        client.opener.open.return_value = response
        path = "/api/vcenter/authorization/permissions"
        result = client.request("POST", path, params={"action": "list"}, body={"iterate": {"page_size": 1}})
        self.assertEqual(result, {"items": []})
        sent = client.opener.open.call_args.args[0]
        self.assertEqual(sent.full_url, "https://example.invalid" + path + "?action=list")
        self.assertEqual(json.loads(sent.data), {"iterate": {"page_size": 1}})
        for params in (None, {"action": "list"}):
            with self.subTest(params=params), self.assertRaises(ApiError):
                client.request("POST", path, params=params, body={"role": "admin", "object": {}, "principal": {}, "propagating": True})
        self.assertEqual(client.opener.open.call_count, 1)

    def test_permission_query_is_never_automatically_retried(self):
        client = HttpClient({"component": "vcenter", "url": "https://example.invalid"}, retries=3)
        client.opener = Mock()
        client.opener.open.side_effect = HTTPError("https://example.invalid", 503, "temporary", {}, io.BytesIO(b"private response"))
        with self.assertRaises(ApiError):
            client.request("POST", "/api/vcenter/authorization/permissions", params={"action": "list"}, body={"iterate": {"page_size": 1}})
        self.assertEqual(client.opener.open.call_count, 1)


class ResourceTests(unittest.TestCase):
    def test_permissions_follow_opaque_markers_and_project_fields(self):
        first = permission_item()
        first["info"]["password"] = "must-not-export"
        client = Client(request_responses=[{"items": [first], "marker": "opaque"},
                                           {"items": [permission_item("permission-2")]}])
        rows = assurance.collect_resource(client, "authorization_permissions", page_size=2)
        self.assertEqual([row["id"] for row in rows], ["permission-1", "permission-2"])
        self.assertNotIn("password", repr(rows))
        self.assertEqual(client.request.call_args_list[1].kwargs["body"], {"iterate": {"page_size": 2, "marker": "opaque"}})
        self.assertEqual(client.collection_metadata["authorization_permissions"]["coverage"], "complete")

    def test_permissions_repeated_cursor_ids_and_page_limit_fail_coverage(self):
        cases = [
            ([{"items": [], "marker": "same"}, {"items": [], "marker": "same"}], 3),
            ([{"items": [permission_item()], "marker": "more"}, {"items": [permission_item()]}], 3),
            ([{"items": [], "marker": "more"}], 1),
        ]
        for responses, max_pages in cases:
            client = Client(request_responses=responses)
            with self.subTest(responses=responses), self.assertRaises(ApiError):
                assurance.collect_resource(client, "authorization_permissions", max_pages=max_pages)
            self.assertEqual(client.collection_metadata["authorization_permissions"]["coverage"], "incomplete")

    def test_permission_malformed_items_cannot_be_exported_as_complete(self):
        bad = permission_item()
        bad["info"]["propagating"] = "true"
        client = Client(request_responses=[{"items": [bad]}])
        with self.assertRaises(ApiError):
            assurance.collect_resource(client, "authorization_permissions")

    def test_roles_are_complete_only_without_marker(self):
        client = Client(get_responses=[{"items": [role_item()], "marker": None}])
        rows = assurance.collect_resource(client, "authorization_roles")
        self.assertEqual(rows[0]["role_id"], "role-1")
        client.get.assert_called_once_with("/api/vcenter/authorization/roles")
        truncated = Client(get_responses=[{"items": [role_item()], "marker": "more"}])
        with self.assertRaisesRegex(ApiError, "continuation"):
            assurance.collect_resource(truncated, "authorization_roles")
        self.assertEqual(truncated.collection_metadata["authorization_roles"]["coverage"], "incomplete")

    def test_backup_projection_excludes_destinations_users_and_errors(self):
        info = {"status": "SUCCEEDED", "end_time": NOW.isoformat(), "location": "sftp://private", "location_user": "private",
                "user": "private", "messages": [{"text": "secret"}], "error": {"password": "private"}}
        client = Client(get_responses=[{"job-1": info}])
        rows = assurance.collect_resource(client, "backup_jobs")
        self.assertEqual(rows, [{"id": "job-1", "status": "SUCCEEDED", "end_time": NOW.isoformat()}])
        schedule = Client(get_responses=[{"schedule-1": {"enable": False, "location": "private", "location_user": "private",
                                                              "recurrence_info": {"minute": 0, "hour": 2, "days": ["MONDAY"], "secret": "private"},
                                                              "retention_info": {"max_count": 7}}}])
        rows = assurance.collect_resource(schedule, "backup_schedules")
        self.assertEqual(rows[0]["recurrence_info"], {"minute": 0, "hour": 2, "days": ["MONDAY"]})
        self.assertNotIn("private", repr(rows))

    def test_nsx_history_keeps_kinds_separate_and_excludes_error_text(self):
        row = {"backup_id": "same-id", "success": True, "end_time": int(NOW.timestamp() * 1000), "error_message": "private"}
        client = Client("nsx", get_responses=[{"cluster_backup_statuses": [row], "inventory_backup_statuses": [row], "overall_backup_status": "SUCCESS"}])
        rows = assurance.collect_resource(client, "backup_history")
        self.assertEqual({row["id"] for row in rows}, {"cluster:same-id", "inventory:same-id"})
        self.assertNotIn("private", repr(rows))
        self.assertEqual(client.collection_metadata["backup_history"]["overall_backup_status"], "SUCCESS")

    def test_nsx_bad_history_shape_and_duplicate_ids_fail(self):
        for document in ({}, {"cluster_backup_statuses": {}}, {"node_backup_statuses": [{"backup_id": "x", "success": "true"}]},
                         {"cluster_backup_statuses": [{"backup_id": "x"}, {"backup_id": "x"}]}):
            with self.subTest(document=document), self.assertRaises(ApiError):
                assurance.collect_resource(Client("nsx", get_responses=[document]), "backup_history")


class BackupReportTests(unittest.TestCase):
    def test_fresh_success_newer_failure_and_disabled_schedule(self):
        run = make_run(backup_jobs=[{"id": "success", "status": "SUCCEEDED", "end_time": (NOW - timedelta(hours=2)).isoformat()},
                                    {"id": "failure", "status": "FAILED", "end_time": (NOW - timedelta(hours=1)).isoformat()}],
                       backup_schedules=[{"id": "schedule", "enable": False}])
        report = build_backup_report(run, now=NOW)
        history, schedule = report["records"]
        self.assertEqual(report["status"], "success")
        self.assertEqual(history["observation"], "fresh")
        self.assertEqual(history["last_success_age_hours"], 2)
        self.assertTrue(history["failure_after_latest_dated_success"])
        self.assertEqual(schedule["observation"], "schedule_disabled")

    def test_stale_is_conclusive_review_and_missing_timestamps_remain_unknown(self):
        for timestamp, expected in (((NOW - timedelta(hours=25)).isoformat(), "stale"),
                                    (None, "freshness_unknown"), ((NOW + timedelta(hours=1)).isoformat(), "freshness_unknown"),
                                    ("2026-10-25T11:00:00", "freshness_unknown")):
            run = make_run(backup_jobs=[{"status": "SUCCEEDED", "end_time": timestamp}], backup_schedules=[])
            report = build_backup_report(run, now=NOW)
            with self.subTest(timestamp=timestamp):
                self.assertEqual(report["records"][0]["observation"], expected)
                if expected != "stale":
                    self.assertIsNone(report["records"][0]["last_success_age_hours"])
                    self.assertEqual(report["status"], "partial")

    def test_unknown_success_prevents_using_older_success_as_last_success(self):
        run = make_run(backup_jobs=[{"status": "SUCCEEDED", "end_time": NOW.isoformat()}, {"status": "SUCCEEDED"}], backup_schedules=[])
        report = build_backup_report(run, now=NOW)
        self.assertEqual(report["records"][0]["observation"], "freshness_unknown")
        self.assertIsNone(report["records"][0]["last_success_at"])

    def test_missing_failed_and_empty_history_are_not_fresh(self):
        for run in (make_run(), make_run(backup_jobs=[], backup_schedules=[])):
            report = build_backup_report(run, now=NOW)
            self.assertEqual(report["status"], "partial")
            self.assertTrue(report["records"])
            self.assertNotEqual(report["records"][0]["observation"], "fresh")
        run = make_run(backup_jobs=[{"status": "SUCCEEDED", "end_time": NOW.isoformat()}], backup_schedules=[])
        run["unavailable"][("target-a", "vcenter", "backup_jobs")] = "failed"
        self.assertEqual(build_backup_report(run, now=NOW)["records"][0]["observation"], "resource_unavailable")

    def test_nsx_epoch_milliseconds_and_separate_history_kinds(self):
        rows = [{"id": kind, "backup_kind": kind, "success": True, "end_time": int((NOW - timedelta(hours=age)).timestamp() * 1000)}
                for kind, age in (("cluster", 1), ("node", 25), ("inventory", 2))]
        run = make_run("nsx", backup_history=rows)
        report = build_backup_report(run, now=NOW, nsx_time_unit="milliseconds")
        observed = {row["backup_kind"]: row["observation"] for row in report["records"]}
        self.assertEqual(observed, {"cluster": "fresh", "node": "stale", "inventory": "fresh"})
        default = build_backup_report(run, now=NOW)
        self.assertEqual(default["status"], "partial")
        self.assertTrue(all(row["observation"] == "freshness_unknown" for row in default["records"]))
        self.assertTrue(all(row["timestamp_basis"] == "not_verified" for row in default["records"]))
        self.assertEqual(default["records"][0]["success_count"], 1)

    def test_old_snapshot_is_evaluated_at_collection_time(self):
        run = make_run(backup_jobs=[{"status": "SUCCEEDED", "end_time": (NOW - timedelta(hours=1)).isoformat()}], backup_schedules=[])
        report = build_backup_report(run, now=NOW + timedelta(days=10))
        self.assertEqual(report["records"][0]["observation"], "fresh")
        self.assertEqual(report["records"][0]["last_success_age_hours"], 1)
        self.assertEqual(report["records"][0]["source_age_hours"], 240)
        self.assertEqual(report["records"][0]["observed_at"], NOW.isoformat(timespec="seconds"))

    def test_missing_invalid_and_future_observation_times(self):
        for value in (None, "bad", (NOW + timedelta(hours=1)).isoformat()):
            run = make_run(backup_jobs=[{"status": "SUCCEEDED", "end_time": (NOW - timedelta(hours=1)).isoformat()}], backup_schedules=[])
            document = run["resources"][("target-a", "vcenter", "backup_jobs")]
            document["collected_at"] = value
            with self.subTest(value=value):
                row = build_backup_report(run, now=NOW)["records"][0]
                self.assertEqual(row["observation"], "freshness_unknown")
                self.assertIsNone(row["observed_at"])
        del document["collected_at"]
        self.assertEqual(build_backup_report(run, now=NOW)["records"][0]["observation"], "fresh")

    def test_no_eligible_target_and_invalid_arguments(self):
        self.assertEqual(build_backup_report(make_run("hcx"), now=NOW)["status"], "partial")
        for threshold in (True, 0, -1, float("nan"), float("inf")):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                build_backup_report(make_run(), max_age_hours=threshold, now=NOW)
        with self.assertRaises(ValueError):
            build_backup_report(make_run(), now=NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            build_backup_report(make_run(), now=NOW, nsx_time_unit="seconds")


class AccessReportTests(unittest.TestCase):
    def test_explicit_scope_principal_role_and_propagation_are_preserved(self):
        run = make_run(authorization_roles=[normalized_role(privileges=["Read", "Write", "Read"])],
                       authorization_permissions=[normalized_permission()])
        report = build_access_report(run, broad_privilege_threshold=2)
        permission = next(row for row in report["records"] if row["record_type"] == "permission")
        self.assertEqual(permission["role_privilege_count"], 2)
        self.assertTrue(permission["broad_role"])
        self.assertTrue(permission["global_scope"])
        self.assertTrue(permission["propagating"])
        self.assertEqual(permission["principal_domain"], "example.local")
        self.assertEqual(permission["baseline_status"], "not_supplied")
        self.assertEqual(report["status"], "success")

    def test_exact_baseline_distinguishes_scope_and_propagation(self):
        run = make_run(authorization_roles=[normalized_role()], authorization_permissions=[normalized_permission()])
        exact = build_access_report(run, baseline={"author": "Environment Owner", "permissions": [baseline_entry()]})
        permission = next(row for row in exact["records"] if row["record_type"] == "permission")
        self.assertEqual(permission["baseline_status"], "observed")
        changed = build_access_report(run, baseline={"permissions": [baseline_entry(propagating=False)]})
        self.assertTrue(any(row.get("baseline_status") == "not_in_baseline" for row in changed["records"]))
        self.assertTrue(any(row["observation"] == "baseline_assignment_not_observed" for row in changed["records"]))

    def test_baseline_endpoint_mismatch_and_missing_inventory_remain_unknown(self):
        run = make_run(authorization_roles=[], authorization_permissions=[])
        report = build_access_report(run, baseline={"permissions": [baseline_entry(endpoint="https://different.example")]})
        self.assertTrue(any(row["observation"] == "baseline_scope_not_observed" for row in report["records"]))
        missing = build_access_report(make_run(), baseline={"permissions": [baseline_entry()]})
        self.assertEqual(missing["status"], "partial")
        self.assertFalse(any(row["observation"] == "baseline_assignment_not_observed" for row in missing["records"]))

    def test_missing_role_and_duplicate_role_ids_do_not_arbitrarily_resolve(self):
        for roles in ([], [normalized_role(), normalized_role(privileges=["Other"])]):
            report = build_access_report(make_run(authorization_roles=roles, authorization_permissions=[normalized_permission()]))
            permission = next(row for row in report["records"] if row["record_type"] == "permission")
            self.assertIsNone(permission["role_privilege_count"])
            self.assertEqual(permission["status"], "unknown")
            self.assertEqual(report["status"], "partial")

    def test_duplicate_permissions_prevent_false_baseline_absence(self):
        permissions = [normalized_permission(), normalized_permission(role_id="other")]
        report = build_access_report(make_run(authorization_roles=[normalized_role()], authorization_permissions=permissions),
                                     baseline={"permissions": [baseline_entry()]})
        self.assertFalse(any(row["observation"] == "baseline_assignment_not_observed" for row in report["records"]))
        self.assertTrue(any(row["observation"] == "baseline_scope_not_observed" for row in report["records"]))

    def test_empty_complete_assignments_and_missing_resources_differ(self):
        complete = build_access_report(make_run(authorization_roles=[], authorization_permissions=[]))
        self.assertEqual(complete["status"], "success")
        self.assertEqual(complete["records"][0]["observation"], "no_assignments_in_visible_inventory")
        self.assertEqual(build_access_report(make_run())["status"], "partial")

    def test_baseline_schema_and_threshold_are_validated(self):
        cases = [{}, {"permissions": "x"}, {"permissions": [baseline_entry(), baseline_entry()]},
                 {"permissions": [baseline_entry(propagating="true")]},
                 {"permissions": [baseline_entry(endpoint="https://user:password@appliance.example")]},
                 {"permissions": [baseline_entry(endpoint="https://appliance.example/api")]},
                 {"permissions": [baseline_entry(password="secret")]}]
        for baseline in cases:
            with self.subTest(baseline=baseline), self.assertRaises(ValueError):
                build_access_report(make_run(), baseline=baseline)
        for threshold in (True, 0, 1.5, 100001):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                build_access_report(make_run(), broad_privilege_threshold=threshold)

    def test_input_run_is_not_modified(self):
        run = make_run(authorization_roles=[normalized_role()], authorization_permissions=[normalized_permission()])
        original = copy.deepcopy(run)
        build_access_report(run)
        self.assertEqual(run, original)


if __name__ == "__main__":
    unittest.main()
