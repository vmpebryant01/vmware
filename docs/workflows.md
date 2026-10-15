# Representative workflows

Author: Paul Bryant

These examples show design choices visible in the repository. Their unit tests exercise local planning or selection logic; no live vCenter or NSX result has been measured for this repository.

## Snapshot cleanup

[`remove_old_snapshots.py`](../vsphere/python/remove_old_snapshots.py) selects snapshots older than `--days`, including nested snapshots. It lists candidates without changing them by default. Deletion requires `--apply` and either `--vm` or `--all-vms`. The task result is awaited and failures produce a nonzero exit code.

```text
python vsphere/python/remove_old_snapshots.py --days 30 --vm example-vm
python vsphere/python/remove_old_snapshots.py --days 30 --vm example-vm --apply
```

The unit tests cover age selection and the apply scope guard. Validate inventory permissions, snapshot dependencies, and the exact vCenter build before a real deletion.

## VM rename

[`bulk_rename_vms.py`](../vsphere/python/bulk_rename_vms.py) reads a CSV with `old_name,new_name` columns. It rejects duplicate source or destination names, missing VMs, and a destination already present in inventory. The default run prints the plan; `--apply` sends rename tasks.

Example `renames.csv`:

```csv
old_name,new_name
example-vm,example-vm-renamed
```

```text
python vsphere/python/bulk_rename_vms.py --csv renames.csv
python vsphere/python/bulk_rename_vms.py --csv renames.csv --apply
```

The unit tests cover name collisions. Check application naming dependencies and the exact vCenter build before applying renames.

## NSX firewall import

[`create_nsxt_dfw_rules_from_csv.py`](../nsx/python_complex/dfw_rules_production/create_nsxt_dfw_rules_from_csv.py) validates CSV columns, actions, direction, unique rule names, and planned ordering before any API write. Its default preview does not connect to NSX. During apply, it checks referenced groups and services, then writes policies and rules through the NSX Policy API.

Start with the [included example CSV](../nsx/python_complex/dfw_rules_production/dfw_rules_production.csv). Its rules and object names are illustrative. Replace and review every row against your own policy before use.

```text
python nsx/python_complex/dfw_rules_production/create_nsxt_dfw_rules_from_csv.py --csv rules.csv
python nsx/python_complex/dfw_rules_production/create_nsxt_dfw_rules_from_csv.py --csv rules.csv --apply
```

The unit tests cover CSV validation and planned paths. The apply operation is not transactional. Review rule order, object paths, and rollback steps in a nonproduction NSX 4.2.x system before use.
