"""Preview or rename vSphere inventory VMs from a CSV file.

CSV columns: old_name,new_name. The --apply flag performs changes.
Author: Paul Bryant
"""

import argparse
import csv
import os
import ssl
import sys


def read_renames(path):
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"old_name", "new_name"}.issubset(reader.fieldnames):
            raise ValueError("CSV requires old_name,new_name columns")
        rows = []
        source_names = set()
        target_names = set()
        for row in reader:
            old_name = (row["old_name"] or "").strip()
            new_name = (row["new_name"] or "").strip()
            if not old_name or not new_name:
                raise ValueError("VM names cannot be blank")
            if old_name in source_names or new_name in target_names:
                raise ValueError("Duplicate source or target name in CSV")
            source_names.add(old_name)
            target_names.add(new_name)
            rows.append((old_name, new_name))
    if not rows:
        raise ValueError("CSV contains no VM renames")
    return rows


def resolve_renames(vms, rows):
    by_name = {}
    for vm in vms:
        by_name.setdefault(vm.name, []).append(vm)
    resolved = []
    for old_name, new_name in rows:
        matches = by_name.get(old_name, [])
        if len(matches) != 1:
            raise ValueError(f"Expected one VM named {old_name!r}; found {len(matches)}")
        if new_name != old_name and new_name in by_name:
            raise ValueError(f"Target VM name {new_name!r} already exists")
        resolved.append((matches[0], new_name))
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    rows = read_renames(args.csv)

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
        resolved = resolve_renames(vms, rows)
        for vm, new_name in resolved:
            print(f"{vm.name} -> {new_name}")
        if not args.apply:
            print("Preview only. Rerun with --apply to rename these VMs.")
            return 0
        failures = 0
        for vm, new_name in resolved:
            if vm.name == new_name:
                continue
            try:
                WaitForTask(vm.Rename_Task(newName=new_name))
                print(f"Renamed VM to {new_name}")
            except Exception as exc:
                failures += 1
                print(f"Failed to rename {vm.name}: {exc}", file=sys.stderr)
        return 1 if failures else 0
    finally:
        Disconnect(service)


if __name__ == "__main__":
    raise SystemExit(main())
