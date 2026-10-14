"""Export VMs with a CD-ROM device backed by an ISO file.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_vms


def iso_rows(vms, cdrom_type=None):
    if cdrom_type is None:
        from pyVmomi import vim
        cdrom_type = vim.vm.device.VirtualCdrom
    rows = []
    for vm in vms:
        config = getattr(vm, "config", None)
        hardware = getattr(config, "hardware", None)
        for device in getattr(hardware, "device", None) or []:
            if not isinstance(device, cdrom_type):
                continue
            iso_path = getattr(getattr(device, "backing", None), "fileName", None)
            if iso_path:
                connected = getattr(getattr(device, "connectable", None), "connected", None)
                rows.append((vm.name, iso_path, connected))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="vms_with_iso_attached.csv")
    args = parser.parse_args(argv)
    with vcenter_vms() as vms:
        rows = iso_rows(vms)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["VM", "ISOPath", "Connected"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} ISO backed CD-ROM devices to {args.csv}")


if __name__ == "__main__":
    main()
