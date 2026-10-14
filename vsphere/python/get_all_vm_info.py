"""Export vSphere VM inventory fields available through pyVmomi.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_vms


def vm_rows(vms):
    rows = []
    for vm in vms:
        summary = getattr(vm, "summary", None)
        config = getattr(summary, "config", None)
        runtime = getattr(vm, "runtime", None)
        host = getattr(runtime, "host", None)
        datastores = sorted(store.name for store in (getattr(vm, "datastore", None) or []))
        rows.append((
            vm.name,
            getattr(vm, "_moId", ""),
            str(getattr(runtime, "powerState", "")),
            getattr(config, "guestFullName", None) or "",
            getattr(config, "numCpu", None),
            getattr(config, "memorySizeMB", None),
            getattr(host, "name", "") if host is not None else "",
            ";".join(datastores),
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="all_vm_info.csv")
    args = parser.parse_args(argv)
    with vcenter_vms() as vms:
        rows = vm_rows(vms)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "VMID", "PowerState", "GuestOS", "CPUCount", "MemoryMB", "Host", "Datastores"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} VMs to {args.csv}")


if __name__ == "__main__":
    main()
