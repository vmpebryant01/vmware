# Compare collection runs

Author: Paul Bryant

Compare two completed run folders offline. A comparison never contacts an appliance.

Write comparison output outside both input run directories so the saved inventories remain intact.

```powershell
python .\compare_runs.py --before .\inventory\earlier-run --after .\inventory\later-run --output .\reports\comparison.json --csv
```

Resources are matched by configured target name, component, and resource. Their endpoint, filters, API family, organization, recovery pairing, selected identifiers, and operational scopes must agree. An interrupted or still-running summary is rejected. A finished run with failures can still supply its successful resources; missing, failed, and incompletely covered resources are skipped. A resource file must remain inside its run directory and agree with the summary's identity and record count.

Within comparable resources, identifiers determine added, removed, and changed records. Display names and content hashes never substitute for an identifier. Duplicate identities or records without a supported identifier cause the resource to be skipped. Scoped fan-out identifiers include their parent context. `removed` means absent from the later visible inventory, not proof that an object was deleted from the platform. Different account permissions or platform changes during sequential collection can change visibility, even when configured scopes match. The API's visibility rules still apply, for example [vCenter VM inventory](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/vm/get/).

Only `_links` and `links` are ignored by default. Add repeated `--ignore-field` dotted paths or glob patterns to suppress known noise, for example `--ignore-field updateTime` or `--ignore-field "*.lastSeen"`. Arrays retain their order. The comparison report records the ignored patterns. Added and removed records retain their original data; ignored fields affect change detection only.

Failed tasks use the [SDDC Manager completion-time filter](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/tasks/get/). The rolling window advances between collections. Missing tasks appear under `no_longer_observed`, never `removed`; the per-row cutoff timestamp does not create a change by itself. Different `task_days` values prevent comparison.

Backup history, migration history, and deployment requests also use `no_longer_observed` for missing historical records because the service may expire retained observations. For recovery inventory and NSX rule statistics, resolved pairing, group, and rule scopes must agree before comparison. These scopes are retained for empty successful collections, so a changed discovery result does not imply removed infrastructure.

JSON includes full before/after records for changes. Optional CSV lists identities and change types; the companion `_changes.json` contains the same index. These files carry the sensitivity of the source inventory. Exit code 0 means every selected resource was comparable, 2 means at least one resource was skipped, and 1 means a run or output could not be read or written. A report with zero changes does not establish platform health or configuration support.
