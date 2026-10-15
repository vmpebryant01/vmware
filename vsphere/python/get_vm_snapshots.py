# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Export vSphere VM snapshot inventory to CSV.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import iter_snapshot_nodes, vcenter_vms


def snapshot_rows(vms):
    rows = []
    for vm in vms:
        snapshot_info = getattr(vm, "snapshot", None)
        if snapshot_info is None:
            continue
        for node in iter_snapshot_nodes(snapshot_info.rootSnapshotList):
            rows.append((vm.name, node.name, node.description, node.createTime.isoformat()))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="vm_snapshots.csv")
    args = parser.parse_args(argv)

    with vcenter_vms() as vms:
        rows = snapshot_rows(vms)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["VM", "Snapshot", "Description", "Created"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} snapshots to {args.csv}")


if __name__ == "__main__":
    main()
