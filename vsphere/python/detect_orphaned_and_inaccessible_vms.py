"""Export VMs whose vSphere connection state is orphaned or inaccessible.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_vms


def affected_rows(vms):
    rows = []
    for vm in vms:
        runtime = getattr(vm, "runtime", None)
        state = str(getattr(runtime, "connectionState", "")).lower()
        if state in {"orphaned", "inaccessible"}:
            rows.append((vm.name, state))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="orphaned_inaccessible_vms.csv")
    args = parser.parse_args(argv)
    with vcenter_vms() as vms:
        rows = affected_rows(vms)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "ConnectionState"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} orphaned or inaccessible VMs to {args.csv}")


if __name__ == "__main__":
    main()
