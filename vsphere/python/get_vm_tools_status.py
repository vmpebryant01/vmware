# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Export VMware Tools version and running status for VMs.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_vms


def tools_rows(vms):
    rows = []
    for vm in vms:
        guest = getattr(vm, "guest", None)
        summary_guest = getattr(getattr(vm, "summary", None), "guest", None)
        rows.append((
            vm.name,
            getattr(guest, "toolsVersion", None) or "",
            getattr(summary_guest, "toolsVersionStatus2", None) or "",
            getattr(summary_guest, "toolsRunningStatus", None) or "",
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="vm_tools_status.csv")
    args = parser.parse_args(argv)
    with vcenter_vms() as vms:
        rows = tools_rows(vms)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "ToolsVersion", "VersionStatus", "RunningStatus"])
        writer.writerows(rows)
    print(f"Exported tools status for {len(rows)} VMs to {args.csv}")


if __name__ == "__main__":
    main()
