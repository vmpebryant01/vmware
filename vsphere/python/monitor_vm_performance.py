# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Export a point-in-time VM CPU and guest memory usage sample.

Author: Paul Bryant
"""

import argparse
import csv
from datetime import datetime, timezone

from vsphere_inventory import vcenter_vms


def performance_rows(vms, collected_at):
    rows = []
    for vm in vms:
        summary = getattr(vm, "summary", None)
        quick = getattr(summary, "quickStats", None)
        rows.append((
            vm.name,
            collected_at,
            getattr(quick, "overallCpuUsage", None),
            getattr(quick, "guestMemoryUsage", None),
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="vm_performance.csv")
    args = parser.parse_args(argv)
    collected_at = datetime.now(timezone.utc).isoformat()
    with vcenter_vms() as vms:
        rows = performance_rows(vms, collected_at)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "CollectedAtUTC", "CpuUsageMHz", "GuestMemoryUsageMB"])
        writer.writerows(rows)
    print(f"Exported usage samples for {len(rows)} VMs to {args.csv}")


if __name__ == "__main__":
    main()
