"""Check that vSphere reports use actual inventory fields.

Author: Paul Bryant
"""

from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


PYTHON_DIR = Path(__file__).parents[1] / "vsphere" / "python"
sys.path.insert(0, str(PYTHON_DIR))
snapshots = importlib.import_module("get_vm_snapshots")
expired = importlib.import_module("get_expired_snapshots")
orphaned = importlib.import_module("detect_orphaned_and_inaccessible_vms")
vm_usage = importlib.import_module("monitor_vm_performance")
host_usage = importlib.import_module("monitor_host_performance")
templates = importlib.import_module("get_template_inventory")
tools_status = importlib.import_module("get_vm_tools_status")
vm_info = importlib.import_module("get_all_vm_info")
host_info = importlib.import_module("get_host_summary")
clusters = importlib.import_module("get_cluster_inventory")
datastores = importlib.import_module("get_datastore_usage")
iso_report = importlib.import_module("find_vms_with_iso_attached")
commitment = importlib.import_module("monitor_host_overcommitment")


class VsphereReportTests(unittest.TestCase):
    def test_snapshot_reports_include_nested_snapshots_and_filter_age(self):
        now = datetime.now(timezone.utc)
        child = SimpleNamespace(name="old", description="child", createTime=now - timedelta(days=40), childSnapshotList=[])
        root = SimpleNamespace(name="new", description="root", createTime=now - timedelta(days=2), childSnapshotList=[child])
        vm = SimpleNamespace(name="vm-1", snapshot=SimpleNamespace(rootSnapshotList=[root]))
        self.assertEqual(len(snapshots.snapshot_rows([vm])), 2)
        self.assertEqual(expired.expired_rows([vm], now - timedelta(days=30))[0][1], "old")

    def test_connection_state_and_usage_are_not_inferred_from_capacity(self):
        vm = SimpleNamespace(
            name="vm-1",
            runtime=SimpleNamespace(connectionState="inaccessible"),
            summary=SimpleNamespace(quickStats=SimpleNamespace(overallCpuUsage=150, guestMemoryUsage=512)),
        )
        self.assertEqual(orphaned.affected_rows([vm]), [("vm-1", "inaccessible")])
        self.assertEqual(vm_usage.performance_rows([vm], "time")[0][2:], (150, 512))
        host = SimpleNamespace(name="esx-1", summary=SimpleNamespace(quickStats=SimpleNamespace(overallCpuUsage=2400, overallMemoryUsage=8192)))
        self.assertEqual(host_usage.performance_rows([host], "time")[0][2:], (2400, 8192))

    def test_templates_and_tools_use_inventory_properties(self):
        vm = SimpleNamespace(
            name="template-1",
            config=SimpleNamespace(template=True, guestFullName="Linux", hardware=SimpleNamespace(numCPU=2, memoryMB=4096)),
            datastore=[SimpleNamespace(name="ds-1")],
            guest=SimpleNamespace(toolsVersion="12345"),
            summary=SimpleNamespace(guest=SimpleNamespace(toolsVersionStatus2="guestToolsCurrent", toolsRunningStatus="guestToolsRunning")),
        )
        self.assertEqual(templates.template_rows([vm])[0][2:4], (2, 4096))
        self.assertEqual(tools_status.tools_rows([vm])[0][1:], ("12345", "guestToolsCurrent", "guestToolsRunning"))

    def test_inventory_uses_hardware_values_and_converts_host_memory(self):
        host = SimpleNamespace(
            name="esx-1",
            summary=SimpleNamespace(
                hardware=SimpleNamespace(vendor="Example", model="Host", numCpuCores=16, memorySize=8 * 1024 * 1024 * 1024),
                runtime=SimpleNamespace(connectionState="connected", powerState="poweredOn"),
            ),
        )
        vm = SimpleNamespace(
            name="vm-1",
            _moId="vm-101",
            summary=SimpleNamespace(config=SimpleNamespace(guestFullName="Linux", numCpu=2, memorySizeMB=4096)),
            runtime=SimpleNamespace(powerState="poweredOn", host=host),
            datastore=[SimpleNamespace(name="ds-1")],
        )
        self.assertEqual(vm_info.vm_rows([vm])[0][1:6], ("vm-101", "poweredOn", "Linux", 2, 4096))
        self.assertEqual(host_info.host_rows([host])[0][-1], 8192)

    def test_cluster_datastore_iso_and_commitment_fields(self):
        cluster = SimpleNamespace(
            name="cluster-1", host=[1, 2],
            configuration=SimpleNamespace(
                drsConfig=SimpleNamespace(enabled=True),
                dasConfig=SimpleNamespace(enabled=False),
            ),
        )
        self.assertEqual(clusters.cluster_rows([cluster])[0], ("cluster-1", 2, True, False))
        datastore = SimpleNamespace(
            name="ds-1", summary=SimpleNamespace(type="VMFS", capacity=2 * 1024 ** 3, freeSpace=1024 ** 3, accessible=True),
        )
        self.assertEqual(datastores.datastore_rows([datastore])[0][2:4], (2.0, 1.0))

        class FakeCdrom:
            def __init__(self):
                self.backing = SimpleNamespace(fileName="[ds-1] images/install.iso")
                self.connectable = SimpleNamespace(connected=True)

        vm = SimpleNamespace(
            name="vm-1",
            config=SimpleNamespace(template=False, hardware=SimpleNamespace(numCPU=2, memoryMB=4096, device=[FakeCdrom()])),
        )
        self.assertEqual(iso_report.iso_rows([vm], FakeCdrom)[0][2], True)
        host = SimpleNamespace(
            name="esx-1",
            hardware=SimpleNamespace(cpuInfo=SimpleNamespace(numCpuCores=8), memorySize=8 * 1024 ** 3),
            vm=[vm],
        )
        self.assertEqual(commitment.commitment_rows([host])[0][3], 0.25)
        self.assertEqual(commitment.commitment_rows([host])[0][-1], 0.5)


if __name__ == "__main__":
    unittest.main()
