"""Maintenance collectors across shared entry points. Author: Paul Bryant."""

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vcf_inventory import cli, collectors, lifecycle, management_services, metric_history, supervisor
from vcf_inventory.compare import compare_runs
from vcf_inventory.config import ConfigError, load_config
from vcf_inventory.preflight import run_preflight
from vcf_inventory.runs import load_run


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "operations-maintenance.example.json"
MODULES = (lifecycle, management_services, supervisor, metric_history)


class MaintenanceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def config(self, value, name="config.json"):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def saved_run(self, name, component, resource, records, collection, **scope):
        path = self.root / name
        path.mkdir()
        document = {"author": "Paul Bryant", "target": "manager", "component": component,
                    "resource": resource, "endpoint": "https://manager.example.com", "scope_filters": {},
                    "collected_at": "2026-10-25T10:00:00Z", "record_count": len(records),
                    "records": records, "collection": collection, **scope}
        (path / "resource.json").write_text(json.dumps(document), encoding="utf-8")
        summary = {"author": "Paul Bryant", "status": "success", "completed_at": "2026-10-25T10:00:00Z",
                   "targets": [{"name": "manager", "component": component, "endpoint": document["endpoint"],
                                "resources": [{"resource": resource, "status": "success", "file": "resource.json",
                                               "record_count": len(records)}]}]}
        (path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return path

    def test_combined_example_loads_without_credentials_or_network(self):
        with patch("vcf_inventory.http_client.build_opener") as opener:
            config = load_config(EXAMPLE)
        opener.assert_not_called()
        self.assertEqual([target["component"] for target in config["targets"]], ["vcenter", "vcf_operations"])
        selected = {resource for target in config["targets"] for resource in collectors.resources_for(target)}
        self.assertEqual(selected, {resource for module in MODULES for paths in module.RESOURCE_PATHS.values() for resource in paths})

    def test_optional_resources_do_not_expand_existing_default_collections(self):
        config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        for target in config["targets"]:
            target.pop("resources")
        loaded = load_config(self.config(config))
        optional = {resource for module in MODULES for paths in module.RESOURCE_PATHS.values() for resource in paths}
        for target in loaded["targets"]:
            with self.subTest(component=target["component"]):
                self.assertFalse(set(collectors.resources_for(target)) & optional)
                self.assertTrue(collectors.resources_for(target))

    def test_configuration_rejects_missing_required_scope_for_new_resources(self):
        for field, resource in (("lifecycle_cluster_ids", "lifecycle_compliance"),
                                ("supervisor_ids", "supervisor_conditions"),
                                ("namespace_ids", "namespaces")):
            config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            config["targets"] = config["targets"][:1]
            target = config["targets"][0]
            target["resources"] = [resource]
            del target[field]
            with self.subTest(field=field), self.assertRaises(ConfigError):
                load_config(self.config(config))
        config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        config["targets"] = config["targets"][1:]
        del config["targets"][0]["metric_history"]
        with self.assertRaises(ConfigError):
            load_config(self.config(config))

    def test_shared_dispatch_reaches_each_supplemental_handler_before_base_product(self):
        for module in MODULES:
            component, paths = next(iter(module.RESOURCE_PATHS.items()))
            resource = next(iter(paths))
            client = Mock(target={"component": component})
            rows = [{"id": "handler-result"}]
            with self.subTest(resource=resource), patch.object(module, "collect_resource", return_value=rows) as handler, \
                    patch.object(collectors, "collect_vcenter") as base_vcenter, \
                    patch.object(collectors, "module_for") as product:
                result = collectors.collect_resource(client, resource, page_size=17, max_pages=9)
            self.assertIs(result, rows)
            handler.assert_called_once_with(client, resource, page_size=17, max_pages=9)
            base_vcenter.assert_not_called()
            product.assert_not_called()

    def test_preflight_uses_only_scoped_gets_for_new_resources(self):
        config = load_config(EXAMPLE)
        clients = []

        def factory(target, **options):
            client = Mock(target=target)
            client.request.return_value = ({"version": "9.1", "build": "123456"} if target["component"] == "vcenter"
                                           else {"major": 9, "minor": 1, "buildNumber": 123456})
            clients.append(client)
            return client

        report = run_preflight(config["targets"], config, client_factory=factory)
        self.assertEqual(report["status"], "success")
        paths = [call.args[1] for call in clients[0].request.call_args_list]
        self.assertEqual(paths, [
            "/api/appliance/system/version",
            "/api/esx/settings/clusters/domain-c101/software",
            "/api/esx/settings/clusters/domain-c101/software/compliance",
            "/api/appliance/networking/dns/servers", "/api/appliance/ntp", "/api/appliance/timesync",
            "/api/appliance/logging/forwarding",
            "/api/vcenter/namespace-management/supervisors/replace-with-supervisor-id/summary",
            "/api/vcenter/namespace-management/supervisors/replace-with-supervisor-id/conditions",
            "/api/vcenter/namespaces/instances/replace-with-namespace-id",
        ])
        for client in clients:
            self.assertTrue(all(call.args[0] == "GET" for call in client.request.call_args_list))
            client.close.assert_called_once_with()
        history = clients[1].request.call_args_list[-1]
        self.assertEqual(history.args[1], "/suite-api/api/resources/stats")
        self.assertEqual(history.kwargs["params"]["resourceId"], ["replace-with-operations-resource-id"])
        self.assertEqual(history.kwargs["params"]["statKey"], ["cpu|usage_average"])
        self.assertEqual(history.kwargs["params"]["end"] - history.kwargs["params"]["begin"], 86400000)
        self.assertEqual(history.kwargs["params"]["intervalQuantifier"], 5)

    def test_changed_resolved_scope_never_invents_removals(self):
        cases = [
            ("vcenter", "lifecycle_desired_image", "configured_cluster_ids", "queried_cluster_ids", "domain-c1", "domain-c2"),
            ("vcenter", "lifecycle_compliance", "configured_cluster_ids", "queried_cluster_ids", "domain-c1", "domain-c2"),
            ("vcenter", "supervisor_summaries", "supervisor_ids", "queried_ids", "supervisor-1", "supervisor-2"),
            ("vcenter", "supervisor_conditions", "supervisor_ids", "queried_ids", "supervisor-1", "supervisor-2"),
            ("vcenter", "namespaces", "namespace_ids", "queried_ids", "namespace-1", "namespace-2"),
        ]
        for index, (component, resource, configured, queried, old_id, new_id) in enumerate(cases):
            before = self.saved_run(f"before{index}", component, resource, [{"id": old_id}],
                                    {"coverage": "complete", configured: [old_id], queried: [old_id]})
            after = self.saved_run(f"after{index}", component, resource, [],
                                   {"coverage": "complete", configured: [new_id], queried: [new_id]})
            with self.subTest(resource=resource):
                result = compare_runs(before, after)
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["resources"][0]["status"], "skipped")
                self.assertNotIn("removed", result["resources"][0])

    def test_historical_windows_and_rollup_changes_are_not_like_for_like_comparisons(self):
        scope = {"coverage": "complete", "resource_ids": ["resource-1"], "stat_keys": ["metric"],
                 "windows": [{"label": "window", "begin_ms": 1000, "end_ms": 2000}],
                 "requested_rollup_type": "AVG", "requested_interval_type": "SECONDS", "requested_interval_quantifier": 1}
        record = {"resource_id": "resource-1", "stat_key": "metric", "window_label": "window", "begin_ms": 1000, "end_ms": 2000}
        for index, change in enumerate(({"windows": [{"label": "window", "begin_ms": 2000, "end_ms": 3000}]},
                                        {"requested_rollup_type": "MAX"}, {"stat_keys": ["other-metric"]})):
            before = self.saved_run(f"history-before{index}", "vcf_operations", "metric_history", [record], scope)
            after = self.saved_run(f"history-after{index}", "vcf_operations", "metric_history", [], {**scope, **change})
            with self.subTest(change=change):
                result = compare_runs(before, after)["resources"][0]
                self.assertEqual(result["status"], "skipped")
                self.assertNotIn("removed", result)

    def test_incomplete_fanout_evidence_is_skipped_by_saved_run_comparison(self):
        before = self.saved_run("complete", "vcenter", "lifecycle_compliance", [{"id": "domain-c1"}],
                                {"coverage": "complete", "configured_cluster_ids": ["domain-c1"], "queried_cluster_ids": ["domain-c1"]})
        after = self.saved_run("incomplete", "vcenter", "lifecycle_compliance", [],
                               {"coverage": "incomplete", "configured_cluster_ids": ["domain-c1"], "queried_cluster_ids": []})
        result = compare_runs(before, after)["resources"][0]
        self.assertEqual(result["status"], "skipped")
        self.assertNotIn("removed", result)

    def test_matching_resolved_scopes_still_compare_stable_records(self):
        cases = [
            ("vcenter", "lifecycle_compliance", {"id": "domain-c1"},
             {"coverage": "complete", "configured_cluster_ids": ["domain-c1"], "queried_cluster_ids": ["domain-c1"]}),
            ("vcenter", "supervisor_conditions", {"id": "supervisor-1"},
             {"coverage": "complete", "supervisor_ids": ["supervisor-1"], "queried_ids": ["supervisor-1"]}),
            ("vcf_operations", "metric_history", {"resource_id": "resource-1", "stat_key": "metric", "window_label": "window",
                                                    "begin_ms": 1000, "end_ms": 2000},
             {"coverage": "complete", "resource_ids": ["resource-1"], "stat_keys": ["metric"],
              "windows": [{"label": "window", "begin_ms": 1000, "end_ms": 2000}], "requested_rollup_type": "AVG",
              "requested_interval_type": "SECONDS", "requested_interval_quantifier": 1}),
        ]
        for index, (component, resource, identity, scope) in enumerate(cases):
            before = self.saved_run(f"matching-before{index}", component, resource, [{**identity, "observation": "earlier"}], scope)
            after = self.saved_run(f"matching-after{index}", component, resource, [{**identity, "observation": "later"}], scope)
            with self.subTest(resource=resource):
                result = compare_runs(before, after)["resources"][0]
                self.assertEqual(result["status"], "compared")
                self.assertEqual(result["counts"], {"added": 0, "removed": 0, "changed": 1, "no_longer_observed": 0})

    def test_real_cli_exports_scope_and_collection_metadata_readable_by_run_loader(self):
        config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        config["targets"] = config["targets"][:1]
        target = config["targets"][0]
        target["resources"] = ["lifecycle_desired_image"]
        client = Mock(target=copy.deepcopy(target))
        client.collection_metadata = {}
        client.get.return_value = {"base_image": {"version": "9.1.0.0"}, "components": {}}
        config_path = self.config(config)
        output = self.root / "inventory"
        with patch.object(cli, "HttpClient", return_value=client), patch("sys.stdout", new_callable=io.StringIO), \
                patch("sys.stderr", new_callable=io.StringIO):
            code = cli.main(["--config", str(config_path), "--output", str(output)])
        self.assertEqual(code, 0)
        directories = list(output.iterdir())
        self.assertEqual(len(directories), 1)
        loaded = load_run(directories[0])
        resource = loaded["resources"][(target["name"], "vcenter", "lifecycle_desired_image")]
        self.assertEqual(resource["lifecycle_cluster_ids"], ["domain-c101"])
        self.assertEqual(resource["supervisor_ids"], target["supervisor_ids"])
        self.assertEqual(resource["namespace_ids"], target["namespace_ids"])
        self.assertEqual(resource["collection"]["configured_cluster_ids"], ["domain-c101"])
        self.assertEqual(resource["collection"]["queried_cluster_ids"], ["domain-c101"])
        self.assertEqual(resource["collection"]["coverage"], "complete")
        summary_resource = loaded["summary"]["targets"][0]["resources"][0]
        self.assertEqual(summary_resource["collection"], resource["collection"])
        self.assertEqual(resource["author"], "Paul Bryant")
        client.get.assert_called_once_with("/api/esx/settings/clusters/domain-c101/software")
        client.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
