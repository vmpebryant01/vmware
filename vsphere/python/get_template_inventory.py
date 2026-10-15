# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Export VM templates from the vSphere inventory.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_vms


def template_rows(vms):
    rows = []
    for vm in vms:
        config = getattr(vm, "config", None)
        if config is None or not getattr(config, "template", False):
            continue
        hardware = getattr(config, "hardware", None)
        datastores = sorted(store.name for store in (getattr(vm, "datastore", None) or []))
        rows.append((
            vm.name,
            getattr(config, "guestFullName", None) or "",
            getattr(hardware, "numCPU", None),
            getattr(hardware, "memoryMB", None),
            ";".join(datastores),
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="template_inventory.csv")
    args = parser.parse_args(argv)
    with vcenter_vms() as vms:
        rows = template_rows(vms)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "GuestOS", "CPUs", "MemoryMB", "Datastores"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} templates to {args.csv}")


if __name__ == "__main__":
    main()
