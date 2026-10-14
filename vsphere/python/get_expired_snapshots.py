"""Export vSphere VM snapshots older than a specified number of days.

Author: Paul Bryant
"""

import argparse
import csv
from datetime import datetime, timedelta, timezone

from vsphere_inventory import iter_snapshot_nodes, vcenter_vms


def expired_rows(vms, cutoff):
    rows = []
    for vm in vms:
        snapshot_info = getattr(vm, "snapshot", None)
        if snapshot_info is None:
            continue
        for node in iter_snapshot_nodes(snapshot_info.rootSnapshotList):
            created = node.createTime
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < cutoff:
                rows.append((vm.name, node.name, node.createTime.isoformat()))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--csv", default="expired_snapshots.csv")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    with vcenter_vms() as vms:
        rows = expired_rows(vms, cutoff)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["VM", "Snapshot", "Created"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} snapshots older than {args.days} days to {args.csv}")


if __name__ == "__main__":
    main()
