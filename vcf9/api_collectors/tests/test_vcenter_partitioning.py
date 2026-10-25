"""Offline vCenter coverage and partitioning tests. Author: Paul Bryant."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from vcf_inventory.http_client import ApiError
from vcf_inventory import vcenter_inventory as inventory


def vm(identifier, datacenter, state="POWERED_ON", **extra):
    value = {"vm": identifier, "name": identifier, "power_state": state,
             "_datacenters": [datacenter]}
    value.update(extra)
    return value


class InventoryApi:
    """A bounded list API fixture with real filter intersection semantics."""

    def __init__(self, resources, filters=None, truncate=False):
        self.resources = deepcopy(resources)
        self.target = {"component": "vcenter", "filters": deepcopy(filters or {})}
        self.collection_metadata = {}
        self.calls = []
        self.truncate = truncate
        self.interceptor = None

    def get(self, path, params=None):
        params = deepcopy(params or {})
        self.calls.append((path, params))
        if self.interceptor is not None:
            result = self.interceptor(path, params)
            if result is not None:
                return result
        resource = next(name for name, value in inventory.PATHS.items() if path == value)
        values = self.resources.get(resource, [])
        key = inventory.ID_KEYS[resource]
        matched = []
        for value in values:
            include = True
            for field, requested in params.items():
                expected = requested if isinstance(requested, list) else [requested]
                if not expected:
                    continue
                if field == resource:
                    actual = [value[key]]
                elif field == "names":
                    actual = [value["name"]]
                elif field == "power_states":
                    actual = [value["power_state"]]
                else:
                    actual = value.get("_" + field, [])
                include = include and bool(set(actual) & set(expected))
            if include:
                matched.append({field: item for field, item in value.items() if not field.startswith("_")})
        limit = inventory.VCENTER_LIMITS[resource]
        if len(matched) > limit:
            if self.truncate:
                return matched[:limit]
            raise ApiError("HTTP 500. API request failed.", status=500)
        return matched


class PartitionTests(unittest.TestCase):
    def limits(self, **overrides):
        values = dict(inventory.VCENTER_LIMITS)
        values.update(overrides)
        return patch.dict(inventory.VCENTER_LIMITS, values)

    def test_complete_direct_query_preserves_filters_and_needs_one_request(self):
        original = {"vms": {"names": ["vm-1"], "power_states": ["POWERED_ON"]}}
        current = InventoryApi({"vms": [vm("vm-1", "dc-1"), vm("vm-2", "dc-2")]}, filters=original)
        rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual([row["vm"] for row in rows], ["vm-1"])
        self.assertEqual(current.target["filters"], original)
        self.assertEqual(len(current.calls), 1)
        self.assertEqual(current.collection_metadata["vms"]["strategy"], "direct")
        self.assertEqual(current.collection_metadata["vms"]["coverage"], "complete")

    def test_more_than_four_thousand_vms_complete_across_datacenters(self):
        values = [vm(f"vm-{index}", "dc-1" if index < 2500 else "dc-2") for index in range(5001)]
        current = InventoryApi({"vms": values, "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}]})
        rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual(len(rows), 5001)
        self.assertEqual(len({row["vm"] for row in rows}), 5001)
        metadata = current.collection_metadata["vms"]
        self.assertEqual(metadata["coverage"], "complete")
        self.assertEqual(metadata["partition_count"], 2)
        self.assertEqual(metadata["request_count"], len(current.calls))
        self.assertTrue(any(part["status"] == "unclassified_http_500" for part in metadata["partitions"]))

    def test_large_explicit_vm_id_union_uses_complete_subsets_within_default_budget(self):
        identifiers = [f"vm-{index}" for index in range(5001)]
        current = InventoryApi({"vms": [vm(identifier, "dc-1") for identifier in identifiers]},
                               filters={"vms": {"vms": identifiers, "power_states": ["POWERED_ON"]}})
        rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual({row["vm"] for row in rows}, set(identifiers))
        self.assertEqual(len(current.calls), 5)
        self.assertTrue(all(path == inventory.PATHS["vms"] for path, _ in current.calls))
        self.assertEqual(current.target["filters"]["vms"]["vms"], identifiers)

    def test_capped_parent_sample_must_be_covered_by_all_child_scopes(self):
        current = InventoryApi({
            "vms": [vm("orphan", "hidden-dc"), vm("vm-1", "dc-1"), vm("vm-2", "dc-2"), vm("vm-3", "dc-2")],
            "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}],
        }, truncate=True)
        with self.limits(vms=3), self.assertRaisesRegex(ApiError, "missing coverage"):
            inventory.collect_vcenter(current, "vms")
        self.assertEqual(current.collection_metadata["vms"]["coverage"], "incomplete")

    def test_vm_datacenter_partition_keeps_hostless_and_disconnected_objects(self):
        current = InventoryApi({
            "vms": [vm("hostless-orphan", "dc-1", _hosts=[]), vm("disconnected-vm", "dc-1", _hosts=["disconnected-host"]),
                    vm("vm-3", "dc-2"), vm("vm-4", "dc-2")],
            "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}],
        })
        with self.limits(vms=3):
            rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual({row["vm"] for row in rows}, {"hostless-orphan", "disconnected-vm", "vm-3", "vm-4"})
        self.assertFalse(any("hosts" in params or "clusters" in params for _, params in current.calls))

    def test_standalone_hosts_are_not_replaced_by_cluster_only_discovery(self):
        current = InventoryApi({
            "hosts": [{"host": "standalone", "_datacenters": ["dc-1"], "_clusters": []},
                      {"host": "cluster-host-1", "_datacenters": ["dc-1"], "_clusters": ["cluster-1"]},
                      {"host": "disconnected", "_datacenters": ["dc-2"], "connection_state": "DISCONNECTED"},
                      {"host": "cluster-host-2", "_datacenters": ["dc-2"], "_clusters": ["cluster-2"]}],
            "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}],
        })
        with self.limits(hosts=3):
            rows = inventory.collect_vcenter(current, "hosts")
        self.assertEqual(len(rows), 4)
        self.assertIn("standalone", {row["host"] for row in rows})
        self.assertFalse(any("clusters" in params for _, params in current.calls))

    def test_vm_power_state_partitions_cover_all_three_states(self):
        values = [vm("off-1", "dc-1", "POWERED_OFF"), vm("off-2", "dc-1", "POWERED_OFF"),
                  vm("on-1", "dc-1"), vm("on-2", "dc-1"), vm("suspended", "dc-1", "SUSPENDED")]
        current = InventoryApi({"vms": values}, filters={"vms": {"datacenters": ["dc-1"]}})
        with self.limits(vms=3):
            rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual(len(rows), 5)
        requested = {params["power_states"][0] for _, params in current.calls if "power_states" in params}
        self.assertEqual(requested, set(inventory.VM_POWER_STATES))

    def test_finite_host_filters_split_without_losing_other_intersections(self):
        values = [vm("vm-1", "dc-1", _hosts=["host-1"], _clusters=["cluster-1"], _folders=["folder-1"]),
                  vm("vm-2", "dc-1", _hosts=["host-2"], _clusters=["cluster-1"], _folders=["folder-1"]),
                  vm("excluded-off", "dc-1", "POWERED_OFF", _hosts=["host-1"], _clusters=["cluster-1"], _folders=["folder-1"])]
        original = {"vms": {"hosts": ["host-1", "host-2"], "clusters": ["cluster-1"],
                            "datacenters": ["dc-1"], "folders": ["folder-1"], "power_states": ["POWERED_ON"]}}
        current = InventoryApi({"vms": values}, filters=original)
        with self.limits(vms=2):
            rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual({row["vm"] for row in rows}, {"vm-1", "vm-2"})
        for path, params in current.calls:
            self.assertEqual(path, inventory.PATHS["vms"])
            for field in ("clusters", "datacenters", "folders", "power_states"):
                self.assertEqual(params[field], original["vms"][field])
        self.assertEqual(current.target["filters"], original)

    def test_overlapping_explicit_folder_scopes_are_deduplicated_by_vm_id(self):
        current = InventoryApi({"vms": [vm("one", "dc-1", _folders=["parent"]),
                                       vm("two", "dc-1", _folders=["parent"]),
                                       vm("shared", "dc-1", _folders=["parent", "child"]),
                                       vm("four", "dc-1", _folders=["child"])]},
                               filters={"vms": {"folders": ["parent", "child"]}})
        with self.limits(vms=4):
            rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual(len(rows), 4)
        self.assertEqual(current.collection_metadata["vms"]["deduplicated_count"], 1)

    def test_irreducible_capped_child_fails_instead_of_returning_partial_rows(self):
        values = [vm(f"vm-{index}", "dc-1") for index in range(5)]
        current = InventoryApi({"vms": values, "datacenters": [{"datacenter": "dc-1"}]})
        with self.limits(vms=3), self.assertRaisesRegex(ApiError, "no exhaustive supported filter split remains"):
            inventory.collect_vcenter(current, "vms")
        metadata = current.collection_metadata["vms"]
        self.assertEqual(metadata["coverage"], "incomplete")
        self.assertTrue(metadata["missing_coverage"])
        self.assertNotIn("record_count", metadata)

    def test_capped_datacenter_discovery_never_treats_children_as_full_coverage(self):
        current = InventoryApi({"vms": [vm("one", "dc-1"), vm("two", "dc-2"), vm("three", "dc-3")],
                                "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}, {"datacenter": "dc-3"}]})
        with self.limits(vms=2, datacenters=2), self.assertRaisesRegex(ApiError, "full datacenter partition set is unknown"):
            inventory.collect_vcenter(current, "vms")
        self.assertEqual(len(current.calls), 2)

    def test_request_budget_includes_discovery_and_verification(self):
        current = InventoryApi({"vms": [vm("one", "dc-1"), vm("two", "dc-2")],
                                "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}]})
        with self.limits(vms=2), self.assertRaisesRegex(ApiError, "request budget"):
            inventory.collect_vcenter(current, "vms", max_pages=4)
        self.assertEqual(len(current.calls), 4)
        self.assertEqual(current.collection_metadata["vms"]["request_count"], 4)

    def test_partition_changes_during_verification_are_an_error(self):
        current = InventoryApi({"vms": [vm("one", "dc-1"), vm("two", "dc-2")],
                                "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}]})

        def change(path, params):
            if path == inventory.PATHS["vms"] and params.get("datacenters") == ["dc-1"]:
                attempts = sum(previous_path == path and previous == params for previous_path, previous in current.calls)
                if attempts == 2:
                    return [{"vm": "one", "name": "changed", "power_state": "POWERED_ON"}]
            return None

        current.interceptor = change
        with self.limits(vms=2), self.assertRaisesRegex(ApiError, "changed during verification"):
            inventory.collect_vcenter(current, "vms")

    def test_discovery_changes_during_verification_are_an_error(self):
        current = InventoryApi({"vms": [vm("one", "dc-1"), vm("two", "dc-2")],
                                "datacenters": [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}]})

        def change(path, params):
            if path == inventory.PATHS["datacenters"] and sum(call[0] == path for call in current.calls) == 2:
                return [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}, {"datacenter": "dc-new"}]
            return None

        current.interceptor = change
        with self.limits(vms=2), self.assertRaisesRegex(ApiError, "datacenter set changed"):
            inventory.collect_vcenter(current, "vms")

    def test_typed_backend_error_is_not_hidden_by_partitioning(self):
        error = ApiError("HTTP 500. API request failed.", status=500)
        error.error_type = "ERROR"
        current = SimpleNamespace(target={}, get=Mock(side_effect=error), collection_metadata={})
        with self.assertRaises(ApiError) as caught:
            inventory.collect_vcenter(current, "vms")
        self.assertIs(caught.exception, error)
        current.get.assert_called_once()

    def test_typed_limit_error_is_recorded_without_exposing_server_payloads(self):
        current = InventoryApi({"vms": [vm("one", "dc-1"), vm("two", "dc-1")]},
                               filters={"vms": {"vms": ["one", "two"]}})

        def limit_error(path, params):
            if len(params.get("vms", [])) == 2:
                error = ApiError("HTTP 500. API request failed.", status=500)
                error.error_type = "UNABLE_TO_ALLOCATE_RESOURCE"
                raise error
            return None

        current.interceptor = limit_error
        rows = inventory.collect_vcenter(current, "vms")
        self.assertEqual(len(rows), 2)
        self.assertEqual(current.collection_metadata["vms"]["partitions"][0]["status"], "limit_error")

    def test_unknown_observed_power_state_cannot_be_silently_excluded(self):
        current = InventoryApi({"vms": [vm("one", "dc-1", "FUTURE_STATE"), vm("two", "dc-1")]},
                               filters={"vms": {"datacenters": ["dc-1"]}})
        with self.limits(vms=2), self.assertRaisesRegex(ApiError, "unknown VM power state"):
            inventory.collect_vcenter(current, "vms")

    def test_automatic_datacenter_partitions_cannot_overlap(self):
        row = {"vm": "same-vm", "name": "same", "power_state": "POWERED_ON"}
        current = SimpleNamespace(target={}, collection_metadata={}, get=Mock(side_effect=[
            ApiError("HTTP 500. API request failed.", status=500),
            [{"datacenter": "dc-1"}, {"datacenter": "dc-2"}], [row], [row],
        ]))
        with self.assertRaisesRegex(ApiError, "overlapped unexpectedly"):
            inventory.collect_vcenter(current, "vms")

    def test_permission_error_is_not_retried_as_a_partition_limit(self):
        current = SimpleNamespace(target={}, get=Mock(side_effect=ApiError("Forbidden.", status=403)), collection_metadata={})
        with self.assertRaises(ApiError) as caught:
            inventory.collect_vcenter(current, "vms")
        self.assertEqual(caught.exception.status, 403)
        current.get.assert_called_once()

    def test_malformed_or_missing_identifiers_fail_with_incomplete_metadata(self):
        for rows in ({"unexpected": []}, [{"name": "missing-id"}], [{"vm": "same"}, {"vm": "same"}]):
            with self.subTest(rows=rows):
                current = SimpleNamespace(target={}, get=Mock(return_value=rows), collection_metadata={})
                with self.assertRaises(ApiError):
                    inventory.collect_vcenter(current, "vms")
                self.assertEqual(current.collection_metadata["vms"]["coverage"], "incomplete")

    def test_server_ignoring_explicit_identifier_filter_is_rejected(self):
        current = SimpleNamespace(target={"filters": {"vms": {"vms": ["vm-1"]}}},
                                  get=Mock(return_value=[{"vm": "vm-other"}]), collection_metadata={})
        with self.assertRaisesRegex(ApiError, "identifier filter"):
            inventory.collect_vcenter(current, "vms")


if __name__ == "__main__":
    unittest.main()
