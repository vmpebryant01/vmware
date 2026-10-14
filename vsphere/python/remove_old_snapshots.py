"""Preview or remove vSphere snapshots older than a specified age.

Author: Paul Bryant

Requires pyvmomi and python-dotenv. Set VCENTER_SERVER, VCENTER_USER, and
VCENTER_PASS in the environment or a local .env file. Certificate validation
is enabled; set VCENTER_CA_BUNDLE to a trusted CA bundle if needed.
"""

import argparse
from datetime import datetime, timedelta, timezone
import os
import ssl
import sys


def iter_snapshot_nodes(nodes):
    """Yield each snapshot tree node, including nested snapshots."""
    for node in nodes or []:
        yield node
        yield from iter_snapshot_nodes(node.childSnapshotList)


def older_snapshots(vms, cutoff):
    """Return VM and snapshot pairs whose creation time precedes cutoff."""
    candidates = []
    for vm in vms:
        snapshot_info = getattr(vm, "snapshot", None)
        if snapshot_info is None:
            continue
        for node in iter_snapshot_nodes(snapshot_info.rootSnapshotList):
            created = node.createTime
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < cutoff:
                candidates.append((vm, node))
    return candidates


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, required=True, help="Minimum snapshot age")
    parser.add_argument("--vm", help="Limit to one VM name")
    parser.add_argument("--all-vms", action="store_true", help="Allow changes across all VMs")
    parser.add_argument("--apply", action="store_true", help="Delete listed snapshots")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")
    if args.apply and not (args.vm or args.all_vms):
        parser.error("--apply requires --vm or --all-vms")
    if args.vm and args.all_vms:
        parser.error("choose either --vm or --all-vms")
    return args


def main(argv=None):
    args = parse_args(argv)
    from dotenv import load_dotenv
    from pyVim.connect import Disconnect, SmartConnect
    from pyVim.task import WaitForTask
    from pyVmomi import vim

    load_dotenv()
    server = os.getenv("VCENTER_SERVER")
    user = os.getenv("VCENTER_USER")
    password = os.getenv("VCENTER_PASS")
    if not all((server, user, password)):
        raise SystemExit("Set VCENTER_SERVER, VCENTER_USER, and VCENTER_PASS")

    context = ssl.create_default_context(cafile=os.getenv("VCENTER_CA_BUNDLE") or None)
    service = SmartConnect(host=server, user=user, pwd=password, sslContext=context)
    try:
        view = service.content.viewManager.CreateContainerView(
            service.content.rootFolder, [vim.VirtualMachine], True
        )
        try:
            vms = list(view.view)
        finally:
            view.Destroy()
        if args.vm:
            vms = [vm for vm in vms if vm.name == args.vm]
            if len(vms) != 1:
                raise SystemExit(f"Expected exactly one VM named {args.vm!r}; found {len(vms)}")

        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
        candidates = older_snapshots(vms, cutoff)
        for vm, node in candidates:
            print(f"{vm.name}: {node.name} ({node.createTime.isoformat()})")
        print(f"Found {len(candidates)} snapshots older than {args.days} days")
        if not args.apply:
            print("Preview only. Rerun with --apply and a VM scope to delete them.")
            return 0

        failures = 0
        for vm, node in candidates:
            try:
                WaitForTask(node.snapshot.RemoveSnapshot_Task(removeChildren=False))
                print(f"Removed {node.name} from {vm.name}")
            except Exception as exc:
                failures += 1
                print(f"Failed to remove {node.name} from {vm.name}: {exc}", file=sys.stderr)
        return 1 if failures else 0
    finally:
        Disconnect(service)


if __name__ == "__main__":
    raise SystemExit(main())
