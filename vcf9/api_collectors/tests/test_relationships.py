"""Offline relationship graph checks. Author: Paul Bryant."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import build_relationships as command
from vcf_inventory.exports import write_json, write_resource
from vcf_inventory.relationships import (build_relationships, endpoint_hostname,
                                         load_identity_map, validate_identity_map)


def inventory(target, component, resource, records, endpoint=None):
    return {"target": target, "component": component, "resource": resource,
            "endpoint": endpoint or "https://" + target + ".example.test", "records": records}


def saved_run(*documents, extra_targets=(), unavailable=None):
    targets = {}
    resources = {}
    for document in documents:
        key = (document["target"], document["component"], document["resource"])
        resources[key] = document
        targets[key[:2]] = {"name": key[0], "component": key[1], "endpoint": document["endpoint"]}
    for target in extra_targets:
        targets[(target["name"], target["component"])] = target
    return {"summary": {"status": "success", "completed_at": "2026-10-24T12:00:00Z", "targets": list(targets.values())},
            "resources": resources, "unavailable": unavailable or {}}


def uuid_rules():
    return [{"component": "vcenter", "resource": "vms", "field": "instance_uuid",
             "namespace": "vm_instance", "normalization": "uuid"},
            {"component": "vcf_operations", "resource": "resources", "field": "instance_uuid",
             "namespace": "vm_instance", "normalization": "uuid"}]


class RelationshipTests(unittest.TestCase):
    def test_documented_sddc_references_and_server_operations_directions(self):
        run = saved_run(
            inventory("sddc", "sddc_manager", "vcenters", [{"id": "vc1", "fqdn": "VC.EXAMPLE.TEST."}]),
            inventory("sddc", "sddc_manager", "nsx_clusters", [{"id": "nsx1", "vipFqdn": "nsx.example.test"}]),
            inventory("sddc", "sddc_manager", "domains", [{"id": "domain-1"}]),
            inventory("sddc", "sddc_manager", "clusters", [{"id": "cluster-1", "domain": {"id": "domain-1"}}]),
            inventory("ops", "vcf_operations", "resources", [{"identifier": "r1"}, {"identifier": "r2"}]),
            inventory("ops", "vcf_operations", "relationships", [{"resource_id": "r1", "relationship_type": "PARENT", "related_resource_id": "r2"}]),
            extra_targets=({"name": "vc", "component": "vcenter", "endpoint": "https://vc.example.test:443"},
                           {"name": "nsx", "component": "nsx", "endpoint": "https://NSX.EXAMPLE.TEST./"}))
        graph = build_relationships(run)
        self.assertEqual({edge["relationship"] for edge in graph["edges"]},
                         {"managed_vcenter", "managed_nsx", "belongs_to_domain", "has_parent"})
        self.assertEqual(graph["unresolved"], [])
        nodes = {node["id"]: node for node in graph["nodes"]}
        parent_edge = next(edge for edge in graph["edges"] if edge["relationship"] == "has_parent")
        self.assertEqual(nodes[parent_edge["source"]]["identity"], ["r1"])
        self.assertEqual(nodes[parent_edge["destination"]]["identity"], ["r2"])
        self.assertEqual(graph["author"], "Paul Bryant")

    def test_duplicate_endpoint_hostnames_do_not_choose_a_target(self):
        graph = build_relationships(saved_run(
            inventory("sddc", "sddc_manager", "vcenters", [{"id": "vc1", "fqdn": "vc.example.test"}]),
            extra_targets=({"name": "vc1", "component": "vcenter", "endpoint": "https://vc.example.test"},
                           {"name": "vc2", "component": "vcenter", "endpoint": "https://vc.example.test:8443"})))
        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["ambiguous"][0]["reason"], "server_hostname_is_not_unique")

    def test_duplicate_sddc_server_fqdns_do_not_choose_a_record(self):
        graph = build_relationships(saved_run(
            inventory("sddc", "sddc_manager", "nsx_clusters", [{"id": "one", "vipFqdn": "nsx.example.test"},
                                                               {"id": "two", "vipFqdn": "NSX.example.test."}]),
            extra_targets=({"name": "nsx", "component": "nsx", "endpoint": "https://nsx.example.test"},)))
        self.assertEqual(graph["edges"], [])
        self.assertEqual(len(graph["ambiguous"]), 1)

    def test_display_names_and_undeclared_uuids_never_match(self):
        identity = "12345678-1234-1234-1234-123456789abc"
        graph = build_relationships(saved_run(
            inventory("vc", "vcenter", "vms", [{"vm": "vm-1", "name": "same", "instance_uuid": identity}]),
            inventory("ops", "vcf_operations", "resources", [{"identifier": "r1", "name": "same", "instance_uuid": identity}])))
        self.assertEqual(graph["edges"], [])
        for field in ("name", "resourceKey.name", "display_name", "resourceName"):
            rule = dict(uuid_rules()[0], field=field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_identity_map({"rules": [rule]})

    def test_explicit_uuid_namespace_normalizes_and_links_cross_component(self):
        graph = build_relationships(saved_run(
            inventory("vc", "vcenter", "vms", [{"vm": "vm-1", "instance_uuid": "12345678123412341234123456789ABC"}]),
            inventory("ops", "vcf_operations", "resources", [{"identifier": "r1", "instance_uuid": "12345678-1234-1234-1234-123456789abc"}])), uuid_rules())
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["relationship"], "same_identity")
        self.assertEqual(graph["edges"][0]["evidence"]["namespace"], "vm_instance")

    def test_duplicate_identity_within_a_target_blocks_all_matches_in_namespace(self):
        value = "12345678-1234-1234-1234-123456789abc"
        graph = build_relationships(saved_run(
            inventory("vc", "vcenter", "vms", [{"vm": "vm-1", "instance_uuid": value}, {"vm": "vm-2", "instance_uuid": value}]),
            inventory("ops", "vcf_operations", "resources", [{"identifier": "r1", "instance_uuid": value}])), uuid_rules())
        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["ambiguous"][0]["reason"], "identity_namespace_is_not_unique_within_target")

    def test_exact_identity_does_not_coerce_integer_ids_into_strings(self):
        rules = [dict(rule, normalization="exact") for rule in uuid_rules()]
        graph = build_relationships(saved_run(
            inventory("vc", "vcenter", "vms", [{"vm": "vm-1", "instance_uuid": 1}]),
            inventory("ops", "vcf_operations", "resources", [{"identifier": "r1", "instance_uuid": "1"}])), rules)
        self.assertEqual(graph["edges"], [])

    def test_missing_fields_and_unmatched_rules_are_reported(self):
        graph = build_relationships(saved_run(inventory("vc", "vcenter", "vms", [{"vm": "vm-1"}])), uuid_rules())
        self.assertEqual(graph["edges"], [])
        self.assertEqual({item["reason"] for item in graph["unresolved"]},
                         {"identity_rule_field_missing_or_invalid", "identity_rule_has_no_collected_records"})

    def test_operations_reference_nodes_disclose_uncollected_and_failed_inventory(self):
        run = saved_run(inventory("ops", "vcf_operations", "relationships", [
            {"resource_id": "r1", "relationship_type": "CHILD", "related_resource_id": "r2"}]),
            unavailable={("ops", "vcf_operations", "resources"): "Resource did not complete successfully."})
        graph = build_relationships(run)
        references = [node for node in graph["nodes"] if node["kind"] == "record_reference"]
        self.assertEqual(len(references), 2)
        self.assertTrue(all(node["inventory_available"] is False for node in references))
        self.assertEqual(graph["edges"][0]["relationship"], "has_child")
        self.assertEqual(len(graph["unavailable_resources"]), 1)
        self.assertEqual(len(graph["unresolved"]), 2)

    def test_duplicate_resource_identifiers_cannot_resolve_an_operations_reference(self):
        graph = build_relationships(saved_run(
            inventory("ops", "vcf_operations", "resources", [{"identifier": "r1"}, {"identifier": "r1"}]),
            inventory("ops", "vcf_operations", "relationships", [{"resource_id": "r1", "relationship_type": "CHILD", "related_resource_id": "r2"}])))
        self.assertEqual(graph["edges"], [])
        self.assertIn("duplicate_record_identifier", {item["reason"] for item in graph["ambiguous"]})
        self.assertIn("operations_reference_is_not_unique", {item["reason"] for item in graph["ambiguous"]})

    def test_endpoint_normalization_has_no_alias_or_network_inference(self):
        self.assertEqual(endpoint_hostname("https://VC.Example.Test.:8443/"), "vc.example.test")
        self.assertEqual(endpoint_hostname("https://[2001:db8::1]:443"), "2001:db8::1")
        for value in ("http://vc.example.test", "https://user:password@vc.example.test", "vc.example.test", "https://bad_host", "https://vc.example.test.."):
            with self.subTest(value=value):
                self.assertIsNone(endpoint_hostname(value))

    def test_identity_map_rejects_unknown_fields_and_duplicate_json_keys(self):
        self.assertEqual(validate_identity_map({"author": "Paul Bryant", "rules": []}), [])
        for document in ({"rules": [], "extra": True}, {"rules": [dict(uuid_rules()[0], extra=True)]},
                         {"rules": [dict(uuid_rules()[0], normalization="guess")]}, {"rules": [uuid_rules()[0], uuid_rules()[0]]},
                         {"rules": [uuid_rules()[0], dict(uuid_rules()[1], normalization="exact")]}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                validate_identity_map(document)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identities.json"
            path.write_text('{"rules":[],"rules":[]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_identity_map(path)


class CommandTests(unittest.TestCase):
    def test_cli_reads_completed_run_and_writes_inspectable_json_and_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_directory = root / "run"
            metadata = {"target": "ops", "component": "vcf_operations", "resource": "resources", "endpoint": "https://ops.example.test"}
            write_resource(run_directory / "ops", "resources", [{"identifier": "r1"}], metadata, write_csv=False)
            write_json(run_directory / "summary.json", {"author": "Paul Bryant", "status": "success", "completed_at": "2026-10-24T12:00:00Z", "targets": [
                {"name": "ops", "component": "vcf_operations", "endpoint": metadata["endpoint"], "resources": [
                    {"resource": "resources", "status": "success", "record_count": 1, "file": "ops/resources.json"}]}]})
            output = root / "graph.json"
            with contextlib.redirect_stdout(io.StringIO()):
                result = command.main(["--run", str(run_directory), "--output", str(output), "--csv"])
            self.assertEqual(result, 0)
            content = output.read_text(encoding="utf-8")
            self.assertNotIn(str(run_directory), content)
            graph = json.loads(content)
            self.assertEqual(graph["author"], "Paul Bryant")
            self.assertEqual(len(graph["nodes"]), 2)
            self.assertTrue((root / "graph_nodes.csv").exists())
            sidecar = json.loads((root / "graph_nodes.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["record_count"], 2)
            self.assertEqual(sidecar["author"], "Paul Bryant")

    def test_cli_rejects_output_inside_input_run_without_touching_it(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "summary.json"
            output.write_text('{"preserve":true}', encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                result = command.main(["--run", directory, "--output", str(output)])
            self.assertEqual(result, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), '{"preserve":true}')


if __name__ == "__main__":
    unittest.main()
