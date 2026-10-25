"""Offline activity collection and evidence tests. Author: Paul Bryant."""

import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from vcf_inventory import activity
from vcf_inventory.activity_reports import build_automation_report, build_hcx_report, build_nsx_usage_report
from vcf_inventory.http_client import ApiError, HttpClient


def client(component, replies=(), **scope):
    result = Mock(target={"component": component, **scope})
    result.collection_metadata = {}
    result.get.side_effect = iter(replies)
    result.request.side_effect = iter(replies)
    return result


def document(component, resource, records, collection, time="2026-10-25T01:00:00Z"):
    return {"target": "target", "component": component, "resource": resource,
            "endpoint": "https://inventory.example.com", "collected_at": time,
            "scope_filters": {}, "records": records, "collection": collection}


def run(doc):
    key = (doc["target"], doc["component"], doc["resource"])
    return {"summary": {"status": "success"}, "resources": {key: doc}, "unavailable": {}}


def hcx_row(**changes):
    row = {"id": "migration-record", "migrationId": "migration", "state": "TRANSFER",
           "progress_isDone": False, "progress_state_isDone": False,
           "progress_state_isTransferProgress": 1, "progress_transfer_progress": 12,
           "progress_transfer_completed": 5}
    row.update(changes)
    return row


def nsx_scope(rules=None):
    return {"coverage": "complete", "domain_id": "default", "policy_ids": ["policy"],
            "enforcement_point_path": "/infra/sites/default/enforcement-points/default",
            "resolved_rule_ids": {"policy": ["rule"] if rules is None else rules}}


def nsx_row(**changes):
    row = {"domain_id": "default", "policy_id": "policy", "rule_id": "rule",
           "enforcement_point": "/infra/sites/default/enforcement-points/default",
           "container_cluster_path": None, "internal_rule_id": "realized-rule", "lr_path": None,
           "segment_path": None, "rule": "/infra/domains/default/security-policies/policy/rules/rule",
           "byte_count": 100, "packet_count": 1, "hit_count": 0}
    row.update(changes)
    return row


class ActivityCollectionTests(unittest.TestCase):
    def test_shared_transport_allows_exact_query_and_refuses_actions_before_network(self):
        with patch("vcf_inventory.http_client.build_opener") as opener:
            transport = HttpClient({"component": "hcx", "url": "https://hcx.example.com"})
        response = Mock()
        response.read.return_value = b'{"data":{"items":[]}}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener.return_value.open.return_value = response
        self.assertEqual(transport.request("POST", "/hybridity/api/migrations", params={"action": "query"},
                                           body=activity._hcx_body(1)), {"data": {"items": []}})
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://hcx.example.com/hybridity/api/migrations?action=query")
        self.assertEqual(json.loads(request.data), activity._hcx_body(1))
        for params, body in (({"action": "start"}, activity._hcx_body(1)),
                             ({"action": "query"}, {"items": [{"migrationId": "migration"}]}),
                             (None, activity._hcx_body(1))):
            with self.subTest(params=params), self.assertRaises(ApiError):
                transport.request("POST", "/hybridity/api/migrations", params=params, body=body)
        self.assertEqual(opener.return_value.open.call_count, 1)

    def test_hcx_allows_only_exact_readonly_query(self):
        args = ["hcx", "POST", "/hybridity/api/migrations", {"action": "query"}, activity._hcx_body(100)]
        self.assertTrue(activity.allow_query(*args))
        unsafe = [
            ["nsx", *args[1:]], ["hcx", "PUT", *args[2:]],
            [*args[:2], "/hybridity/api/migrations?action=query", *args[3:]],
            [*args[:3], None, args[4]], [*args[:3], {"action": "start"}, args[4]],
            [*args[:3], {"action": "query", "async": "true"}, args[4]],
            [*args[:4], {**args[4], "items": []}],
            [*args[:4], {"filter": {"includeArchived": 1}, "paging": {"pageSize": 10, "offset": 0}}],
            [*args[:4], activity._hcx_body(True)], [*args[:4], activity._hcx_body(1, -1)],
            [*args[:4], activity._hcx_body(1001)],
        ]
        for candidate in unsafe:
            with self.subTest(candidate=candidate[:4]):
                self.assertFalse(activity.allow_query(*candidate))
        self.assertEqual(activity.ALLOWED_OPERATIONS, set())
        self.assertEqual(activity.DEFAULT_RESOURCES, {})

    def test_hcx_continues_short_pages_and_omits_sensitive_configuration(self):
        c = client("hcx", [{"data": {"items": [{"id": "one", "username": "private-user",
                    "transferParams": {"password": "secret"}, "progress": {"message": "secret",
                    "transfer": {"progress": 23}}}]}}, {"data": {"items": [{"id": "two"}]}},
                    {"data": {"items": []}}])
        rows = activity.collect_resource(c, "migrations", page_size=100)
        self.assertEqual([row["id"] for row in rows], ["one", "two"])
        self.assertEqual([call.kwargs["body"]["paging"]["offset"] for call in c.request.call_args_list], [0, 1, 2])
        self.assertEqual(rows[0]["progress_transfer_progress"], 23)
        self.assertNotIn("secret", json.dumps(rows))
        self.assertNotIn("private-user", json.dumps(rows))
        self.assertEqual(c.collection_metadata["migrations"]["coverage"], "complete")
        self.assertTrue(c.collection_metadata["migrations"]["include_archived"])

    def test_hcx_repeated_page_is_an_error_with_incomplete_evidence(self):
        c = client("hcx", [{"data": {"items": [{"id": "one"}]}}, {"data": {"items": [{"id": "one"}]}}])
        with self.assertRaises(ApiError):
            activity.collect_resource(c, "migrations")
        self.assertEqual(c.collection_metadata["migrations"]["coverage"], "incomplete")

    def test_hcx_error_envelope_does_not_become_empty_success_or_leak_error(self):
        for payload in ({"errors": [{"message": "secret"}]}, {"data": {"items": "secret"}}, {"rows": []}):
            c = client("hcx", [payload])
            with self.subTest(payload=payload), self.assertRaises(ApiError) as caught:
                activity.collect_resource(c, "migrations")
            self.assertNotIn("secret", str(caught.exception))
            self.assertEqual(c.collection_metadata["migrations"]["coverage"], "incomplete")

    def test_empty_hcx_still_records_archive_scope(self):
        c = client("hcx", [{"data": {"items": []}}])
        self.assertEqual(activity.collect_resource(c, "migrations"), [])
        self.assertEqual(c.collection_metadata["migrations"], {
            "coverage": "complete", "request_count": 1, "strategy": "offset_query",
            "include_archived": True, "terminal_empty_page": True, "record_count": 0})

    def test_nsx_requires_explicit_safe_policy_scope(self):
        for scope in ({}, {"policy_ids": []}, {"policy_ids": ["../policy"]},
                      {"policy_ids": ["policy"], "rule_ids": {"other": ["rule"]}},
                      {"policy_ids": ["policy"], "rule_ids": {"policy": ["rule", "rule"]}}):
            c = client("nsx", **scope)
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                activity.collect_resource(c, "rule_statistics")
            c.get.assert_not_called()

    def test_nsx_cursor_rule_discovery_and_nested_native_counters(self):
        ep = "/infra/sites/default/enforcement-points/default"
        c = client("nsx", [
            {"results": [{"id": "one"}], "cursor": "next", "result_count": 2},
            {"results": [{"id": "two"}]},
            {"results": [{"enforcement_point": ep, "statistics": {"internal_rule_id": "mp-one", "hit_count": 5}}]},
            {"results": []}], policy_ids=["policy"])
        rows = activity.collect_resource(c, "rule_statistics", page_size=100)
        self.assertEqual(c.get.call_args_list[1].kwargs["params"], {"page_size": 100, "cursor": "next"})
        self.assertEqual(c.get.call_args_list[2].kwargs["params"], {"enforcement_point_path": ep})
        self.assertEqual(rows[0]["hit_count"], 5)
        self.assertIsNone(rows[0]["packet_count"])
        self.assertEqual(rows[0]["internal_rule_id"], "mp-one")
        self.assertEqual(c.collection_metadata["rule_statistics"]["resolved_rule_ids"], {"policy": ["one", "two"]})

    def test_nsx_explicit_ids_preserve_rule_and_realized_context(self):
        c = client("nsx", [{"results": [
            {"statistics": {"internal_rule_id": "one", "byte_count": 1}},
            {"statistics": {"internal_rule_id": "two", "byte_count": 2}}]}],
            policy_ids=["policy"], rule_ids={"policy": ["rule"]})
        rows = activity.collect_resource(c, "rule_statistics")
        self.assertEqual([row["byte_count"] for row in rows], [1, 2])
        self.assertEqual(c.get.call_count, 1)
        self.assertTrue(c.get.call_args.args[0].endswith("/rules/rule/statistics"))

    def test_nsx_empty_discovery_records_resolved_empty_scope(self):
        c = client("nsx", [{"results": [], "result_count": 0}], policy_ids=["policy"])
        self.assertEqual(activity.collect_resource(c, "rule_statistics"), [])
        details = c.collection_metadata["rule_statistics"]
        self.assertEqual(details["resolved_rule_ids"], {"policy": []})
        self.assertEqual(details["coverage"], "complete")

    def test_nsx_statistics_cannot_invent_paging_or_merge_ambiguous_results(self):
        for payload in ({"results": [], "result_count": 1}, {"results": [], "cursor": "next"},
                        {"results": [{"statistics": {"hit_count": -1}}]},
                        {"results": [{"statistics": {}}, {"statistics": {}}]},
                        {"results": [{"enforcement_point": "/different", "statistics": {}}]}):
            c = client("nsx", [payload], policy_ids=["policy"], rule_ids={"policy": ["rule"]})
            with self.subTest(payload=payload), self.assertRaises(ApiError):
                activity.collect_resource(c, "rule_statistics")
            self.assertEqual(c.get.call_count, 1)
            self.assertEqual(c.collection_metadata["rule_statistics"]["coverage"], "incomplete")

    def test_global_budget_includes_discovery_and_statistics(self):
        c = client("nsx", [{"results": [{"id": "one"}, {"id": "two"}]}], policy_ids=["policy"])
        with self.assertRaises(ApiError):
            activity.collect_resource(c, "rule_statistics", max_pages=1)
        self.assertEqual(c.get.call_count, 1)
        self.assertEqual(c.collection_metadata["rule_statistics"]["request_count"], 1)

    def test_automation_requires_supported_family_and_explicit_deployments(self):
        for scope in ({"api_family": "provider", "deployment_ids": ["deployment"]},
                      {"api_family": "all_apps"}, {"api_family": "vm_apps", "deployment_ids": ["../bad"]}):
            c = client("vcf_automation", **scope)
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                activity.collect_resource(c, "deployment_requests")
            c.get.assert_not_called()

    def test_automation_pages_each_scope_and_discards_inputs_outputs_and_errors(self):
        c = client("vcf_automation", [
            {"content": [{"id": "one", "deploymentId": "a", "status": "FAILED", "details": "secret",
                          "inputs": {"password": "secret"}, "outputs": {"token": "secret"}}],
             "number": 0, "totalPages": 2, "totalElements": 2, "last": False},
            {"content": [{"id": "two"}], "number": 1, "totalPages": 2, "totalElements": 2, "last": True},
            {"content": [], "totalElements": 0, "totalPages": 0, "last": True}],
            api_family="all_apps", deployment_ids=["a", "b"])
        rows = activity.collect_resource(c, "deployment_requests")
        self.assertEqual([row["deploymentId"] for row in rows], ["a", "a"])
        self.assertNotIn("secret", json.dumps(rows))
        self.assertEqual(c.collection_metadata["deployment_requests"]["queried_deployment_ids"], ["a", "b"])
        self.assertEqual(c.get.call_args_list[1].kwargs["params"], {"page": 1, "size": 100})

    def test_automation_conflicting_totals_or_foreign_deployment_fail(self):
        for replies in ([{"content": [], "totalElements": 1, "last": True}],
                        [{"content": [{"id": "one", "deploymentId": "other"}]}],
                        [{"content": [{"id": "one"}], "last": False},
                         {"content": [{"id": "one"}], "last": True}]):
            c = client("vcf_automation", replies, api_family="vm_apps", deployment_ids=["a"])
            with self.subTest(replies=replies), self.assertRaises(ApiError):
                activity.collect_resource(c, "deployment_requests")
            self.assertEqual(c.collection_metadata["deployment_requests"]["coverage"], "incomplete")

    def test_probes_are_bounded_and_match_query_authorization(self):
        method, path, params, body, _ = activity.probe_request({"component": "hcx"}, "migrations")
        self.assertTrue(activity.allow_query("hcx", method, path, params, body))
        self.assertEqual(body["paging"]["pageSize"], 1)
        nsx = {"component": "nsx", "policy_ids": ["policy"], "rule_ids": {"policy": ["rule"]}}
        method, path, params, body, _ = activity.probe_request(nsx, "rule_statistics")
        self.assertEqual(method, "GET")
        self.assertTrue(path.endswith("/rules/rule/statistics"))
        self.assertEqual(params, {"enforcement_point_path": "/infra/sites/default/enforcement-points/default"})
        self.assertIsNone(activity.probe_request({"component": "nsx"}, "other"))


class ActivityReportTests(unittest.TestCase):
    def hcx(self, row=None, time="2026-10-25T01:00:00Z"):
        return document("hcx", "migrations", [hcx_row() if row is None else row],
                        {"coverage": "complete", "include_archived": True}, time)

    def test_hcx_one_snapshot_cannot_establish_stall(self):
        result = build_hcx_report(run(self.hcx()))
        self.assertEqual(result["author"], "Paul Bryant")
        self.assertEqual(result["schema_version"], "1.0")
        self.assertIsNone(result["records"][0]["possible_stall"])
        self.assertEqual(result["records"][0]["assessment"], "interval_unknown")

    def test_hcx_unchanged_active_progress_needs_sufficient_interval(self):
        old = run(self.hcx(time="2026-10-25T00:00:00Z"))
        result = build_hcx_report(run(self.hcx()), old)
        self.assertTrue(result["records"][0]["possible_stall"])
        self.assertEqual(result["records"][0]["comparison_minutes"], 60)
        short = build_hcx_report(run(self.hcx(time="2026-10-25T00:10:00Z")), old)
        self.assertIsNone(short["records"][0]["possible_stall"])

    def test_hcx_progress_restart_and_completed_are_distinct(self):
        old = run(self.hcx(time="2026-10-25T00:00:00Z"))
        for changes, expected in (({"progress_transfer_progress": 13}, "progress_or_state_change_observed"),
                                  ({"progress_transfer_progress": 1}, "restart_or_counter_decrease_possible"),
                                  ({"progress_isDone": True}, "completed_observation"),
                                  ({"progress_state_isTransferProgress": 0}, "active_transfer_not_established")):
            with self.subTest(changes=changes):
                row = build_hcx_report(run(self.hcx(hcx_row(**changes))), old)["records"][0]
                self.assertEqual(row["assessment"], expected)
                self.assertIsNot(row["possible_stall"], True)

    def test_hcx_missing_progress_field_prevents_stall_and_numeric_times_stay_raw(self):
        old = run(self.hcx(time="2026-10-25T00:00:00Z"))
        row = hcx_row(progress_transfer_progress=None, progress_startTime=1234567890, progress_endTime=1234567990)
        result = build_hcx_report(run(self.hcx(row)), old)["records"][0]
        self.assertEqual(result["assessment"], "comparable_active_progress_not_available")
        self.assertIsNone(result["possible_stall"])
        self.assertEqual(result["progress_startTime"], 1234567890)
        self.assertNotIn("elapsed_minutes", result)
        self.assertIsNone(result["duration_seconds"])
        self.assertEqual(result["timestamp_basis"], "unit_not_verified")

    def test_hcx_explicit_timestamp_unit_enables_valid_elapsed_without_guessing(self):
        start = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc).timestamp()
        current = self.hcx(hcx_row(progress_startTime=start, progress_endTime=0))
        observed = build_hcx_report(run(current), hcx_time_unit="seconds")["records"][0]
        self.assertEqual(observed["duration_seconds"], 1800)
        self.assertEqual(observed["timestamp_basis"], "operator_supplied_seconds")
        current["records"][0].update(progress_startTime=start * 1000, progress_endTime=(start + 600) * 1000,
                                      progress_isDone=True)
        observed = build_hcx_report(run(current), hcx_time_unit="milliseconds")["records"][0]
        self.assertEqual(observed["duration_seconds"], 600)

    def test_hcx_inconsistent_or_future_timestamps_leave_elapsed_unknown(self):
        start = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc).timestamp()
        for changes in ({"progress_startTime": start + 7200, "progress_endTime": 0},
                        {"progress_startTime": start, "progress_endTime": start - 1, "progress_isDone": True},
                        {"progress_startTime": start, "progress_endTime": start + 7200, "progress_isDone": True},
                        {"progress_startTime": start, "progress_endTime": start + 1},
                        {"progress_startTime": -1, "progress_endTime": 0}):
            with self.subTest(changes=changes):
                observed = build_hcx_report(run(self.hcx(hcx_row(**changes))), hcx_time_unit="seconds")["records"][0]
                self.assertIsNone(observed["duration_seconds"])
        with self.assertRaises(ValueError):
            build_hcx_report(run(self.hcx()), hcx_time_unit="automatic")

    def test_changed_endpoint_or_scope_disables_interval(self):
        current = self.hcx()
        for field, value in (("endpoint", "https://different.example.com"),
                             ("collection", {"coverage": "complete", "include_archived": False})):
            old = self.hcx(time="2026-10-25T00:00:00Z")
            old[field] = value
            result = build_hcx_report(run(current), run(old))
            self.assertIsNone(result["records"][0]["comparison_minutes"])
            self.assertIsNone(result["records"][0]["possible_stall"])

    def test_nsx_zero_single_snapshot_is_not_unused(self):
        doc = document("nsx", "rule_statistics", [nsx_row(byte_count=0, packet_count=0)], nsx_scope())
        result = build_nsx_usage_report(run(doc))
        self.assertEqual(result["records"][0]["assessment"], "interval_unknown")
        self.assertNotIn("unused", json.dumps(result["records"]))

    def test_nsx_differences_and_decreases_preserve_native_counters(self):
        old = document("nsx", "rule_statistics", [nsx_row()], nsx_scope(), "2026-10-25T00:00:00Z")
        for changes, assessment in (({"byte_count": 120}, "counter_increase_observed"),
                                    ({"byte_count": 100}, "no_counter_increase_observed"),
                                    ({"byte_count": 1}, "counter_reset_or_replacement_possible")):
            current = document("nsx", "rule_statistics", [nsx_row(**changes)], nsx_scope())
            row = build_nsx_usage_report(run(current), run(old))["records"][0]
            self.assertEqual(row["assessment"], assessment)
            self.assertEqual(row["byte_count"], changes["byte_count"])
            if changes["byte_count"] == 1:
                self.assertEqual(row["observed_counter_change"], {})

    def test_nsx_changed_resolved_rules_or_realized_identity_cannot_be_compared(self):
        current = document("nsx", "rule_statistics", [nsx_row(byte_count=120)], nsx_scope())
        old = document("nsx", "rule_statistics", [nsx_row()], nsx_scope(["rule", "new-rule"]), "2026-10-25T00:00:00Z")
        self.assertIsNone(build_nsx_usage_report(run(current), run(old))["records"][0]["comparison_minutes"])
        old["collection"] = nsx_scope()
        old["records"][0]["internal_rule_id"] = "different-realization"
        self.assertEqual(build_nsx_usage_report(run(current), run(old))["records"][0]["assessment"], "interval_unknown")

    def test_nsx_contexts_stay_separate_and_ambiguous_context_is_omitted(self):
        first, second = nsx_row(), nsx_row(internal_rule_id="another", hit_count=5)
        doc = document("nsx", "rule_statistics", [first, second], nsx_scope())
        self.assertEqual(len(build_nsx_usage_report(run(doc))["records"]), 2)
        doc["records"].append(copy.deepcopy(first))
        result = build_nsx_usage_report(run(doc))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["records"]), 1)

    def test_nsx_absent_realized_identity_prevents_counter_interval_claim(self):
        current = document("nsx", "rule_statistics", [nsx_row(internal_rule_id=None, byte_count=120)], nsx_scope())
        old = document("nsx", "rule_statistics", [nsx_row(internal_rule_id=None)], nsx_scope(), "2026-10-25T00:00:00Z")
        row = build_nsx_usage_report(run(current), run(old))["records"][0]
        self.assertEqual(row["assessment"], "realized_rule_identity_not_available")
        self.assertEqual(row["observed_counter_change"], {})

    def test_empty_statistics_reports_resolved_scope(self):
        doc = document("nsx", "rule_statistics", [], nsx_scope([]))
        result = build_nsx_usage_report(run(doc))
        self.assertEqual(result["records"], [])
        self.assertEqual(result["scopes"][0]["scope"]["resolved_rule_ids"], {"policy": []})

    def automation(self, status="INPROGRESS", **extra):
        row = {"id": "request", "deploymentId": "deployment", "status": status,
               "createdAt": "2026-10-24T23:00:00Z", "completedTasks": 1, "totalTasks": 2, **extra}
        return document("vcf_automation", "deployment_requests", [row],
                        {"coverage": "complete", "api_family": "vm_apps", "queried_deployment_ids": ["deployment"]})

    def test_automation_age_uses_saved_observation_and_distinguishes_waiting(self):
        result = build_automation_report(run(self.automation()), now=datetime(2026, 10, 26, tzinfo=timezone.utc))
        self.assertEqual(result["records"][0]["age_minutes"], 120)
        self.assertTrue(result["records"][0]["long_running"])
        self.assertFalse(result["records"][0]["waiting"])
        waiting = build_automation_report(run(self.automation("APPROVAL_PENDING")), now="2026-10-25T02:00:00Z")
        self.assertTrue(waiting["records"][0]["waiting"])

    def test_automation_terminal_unknown_and_timestamp_conflict(self):
        now = datetime(2026, 10, 25, 2, tzinfo=timezone.utc)
        terminal = build_automation_report(run(self.automation("FAILED", completedAt="2026-10-25T00:00:00Z")), now=now)
        self.assertFalse(terminal["records"][0]["long_running"])
        self.assertEqual(terminal["records"][0]["duration_minutes"], 60)
        future = build_automation_report(run(self.automation("SUCCESSFUL", completedAt="2026-10-26T00:00:00Z")), now=now)
        self.assertEqual(future["status"], "partial")
        self.assertNotIn("duration_minutes", future["records"][0])
        for doc in (self.automation("UNKNOWN"), self.automation(completedAt="2026-10-25T00:00:00Z"),
                    self.automation(createdAt="2026-10-26T00:00:00Z")):
            result = build_automation_report(run(doc), now=now)
            self.assertEqual(result["status"], "partial")
            self.assertIsNone(result["records"][0]["long_running"])

    def test_reports_omit_raw_errors_inputs_and_unavailable_reason(self):
        doc = self.automation(details="private-error", inputs={"token": "secret"}, requestedBy="private-user")
        source = run(doc)
        source["unavailable"][("other", "vcf_automation", "deployment_requests")] = "private-error"
        result = build_automation_report(source, now="2026-10-25T02:00:00Z")
        rendered = json.dumps(result)
        for secret in ("private-error", "private-user", "secret"):
            self.assertNotIn(secret, rendered)
        self.assertEqual(result["status"], "partial")

    def test_invalid_thresholds_times_and_absent_resources_are_explicit(self):
        for threshold in (True, 0, -1, float("nan"), float("inf")):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                build_hcx_report(run(self.hcx()), stalled_minutes=threshold)
        with self.assertRaises(ValueError):
            build_automation_report(run(self.automation()), now=datetime(2026, 10, 25))
        result = build_nsx_usage_report({"resources": {}, "unavailable": {}})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["records"], [])


if __name__ == "__main__":
    unittest.main()
