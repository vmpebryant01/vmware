# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Shared read-only pyVmomi inventory access for vSphere reports.

Author: Paul Bryant
"""

from contextlib import contextmanager
import os
import ssl


def iter_snapshot_nodes(nodes):
    for node in nodes or []:
        yield node
        yield from iter_snapshot_nodes(node.childSnapshotList)


@contextmanager
def vcenter_objects(object_type):
    from dotenv import load_dotenv
    from pyVim.connect import Disconnect, SmartConnect
    from pyVmomi import vim

    load_dotenv()
    server = os.getenv("VCENTER_SERVER")
    user = os.getenv("VCENTER_USER")
    password = os.getenv("VCENTER_PASS")
    if not all((server, user, password)):
        raise ValueError("Set VCENTER_SERVER, VCENTER_USER, and VCENTER_PASS")
    context = ssl.create_default_context(cafile=os.getenv("VCENTER_CA_BUNDLE") or None)
    service = SmartConnect(host=server, user=user, pwd=password, sslContext=context)
    try:
        view = service.content.viewManager.CreateContainerView(
            service.content.rootFolder, [getattr(vim, object_type)], True
        )
        try:
            yield list(view.view)
        finally:
            view.Destroy()
    finally:
        Disconnect(service)


@contextmanager
def vcenter_vms():
    with vcenter_objects("VirtualMachine") as objects:
        yield objects


@contextmanager
def vcenter_hosts():
    with vcenter_objects("HostSystem") as objects:
        yield objects


@contextmanager
def vcenter_clusters():
    with vcenter_objects("ClusterComputeResource") as objects:
        yield objects


@contextmanager
def vcenter_datastores():
    with vcenter_objects("Datastore") as objects:
        yield objects
