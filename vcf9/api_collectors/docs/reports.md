# Operational reports from saved API collections

Author: Paul Bryant

The seven report commands read a completed inventory run and write JSON, with optional CSV. They make no network requests. Collect the additional resources first using the existing runner and [the report collection example](../examples/report-collection.example.json). Existing default inventories are unchanged. Replace all example targets and native identifiers with values verified for the installed services.

```powershell
python .\collect.py --config .\examples\report-collection.example.json --validate-config
python .\collect.py --config .\config.json --output .\inventory --csv
```

Use an actual generated run folder for `--run` in the examples below. Report output must remain outside the current and previous input run folders. Reports never replace a supplied policy or access baseline. The optional CSV has a companion `_records.json` file with report metadata. All outputs identify Paul Bryant as author.

| Command | Required resources | Report |
| --- | --- | --- |
| `report_backup_freshness.py` | vCenter `backup_jobs`, `backup_schedules`; NSX `backup_history` | Last observed successful backup, age, failures, and vCenter schedule observations |
| `report_protection_gaps.py` | vCenter `vms`; selected recovery `group_vms` and/or `replications` | Explicitly required protection missing from the selected scope, RPO exceptions, and synchronization age |
| `report_vsan_health.py` | vSAN `health_summary`, `space_usage` | Cached cluster/object/disk health and physical capacity |
| `report_hcx_migrations.py` | HCX `migrations` | Migration state, raw progress, failures, and unchanged progress across comparable observations |
| `report_access_permissions.py` | vCenter `authorization_roles`, `authorization_permissions` | Explicit role assignments, propagation, privilege counts, and optional baseline exceptions |
| `report_nsx_rule_usage.py` | NSX `rule_statistics` | Native counters and comparable observation intervals, separated by enforcement context |
| `report_automation_requests.py` | Automation `deployment_requests` | Request status and age relative to the saved collection time |

```powershell
python .\report_backup_freshness.py --run .\inventory\selected-run --output .\reports\backups.json --max-age-hours 24 --csv
python .\report_protection_gaps.py --run .\inventory\selected-run --policy .\examples\protection-policy.example.json --output .\reports\protection.json --csv
python .\report_vsan_health.py --run .\inventory\selected-run --output .\reports\vsan.json --max-used-percent 80 --csv
python .\report_hcx_migrations.py --run .\inventory\selected-run --previous .\inventory\earlier-run --output .\reports\migrations.json --stalled-minutes 30 --csv
python .\report_access_permissions.py --run .\inventory\selected-run --baseline .\examples\access-baseline.example.json --output .\reports\permissions.json --csv
python .\report_nsx_rule_usage.py --run .\inventory\selected-run --previous .\inventory\earlier-run --output .\reports\rule-usage.json --csv
python .\report_automation_requests.py --run .\inventory\selected-run --output .\reports\requests.json --long-running-minutes 60 --csv
```

The installed `vcf-report --report <report_type>` command provides the same reports, with underscore-separated types such as `backup_freshness` or `protection_gaps`. Direct scripts require no package installation or third-party runtime dependencies.

## Protection requirements

Adapt [the protection policy example](../examples/protection-policy.example.json). Each requirement names the configured vCenter target and its local VM ID, plus at least one explicit native protection reference. Replication references require target, pairing, source-vCenter ID, and replicated VM ID. Site Recovery references require target, pairing, protection group, and protected VM ID. These native IDs are supplied explicitly because similar names and coincident local IDs cannot establish cross-component identity.

The new `group_vms` resource reads the documented [protected VM list](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/protection-management/groups/group_id/vms/get/) using an explicit `pairing_id` and `group_ids`. It records successfully queried scopes even when no VMs are returned, and exports selected membership/status metadata without full error payloads. A non-applicable response or failed group query does not become an empty successful protection group. Credentials mode follows the existing remote-login protocol; supplied recovery sessions must already cover both sites.

Replication matching uses `source_vc_id`, `vm_id`, and pairing context from [replication information](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/data-structures/ReplicationInfo/). Synchronization timestamps are documented epoch milliseconds. `max_sync_age_hours` defaults to 24 per requirement and is an operator threshold. It is distinct from the API-reported RPO and [RPO-violation status](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/data-structures/CompoundReplicationStatus/).

Missing, failed, ambiguous, or differently scoped evidence remains unknown. A missing required VM is called a gap only inside a successfully collected matching scope. Positive group membership does not establish a successful recovery test. Replication-age thresholds apply at the saved resource collection time; the report also exposes the age of that observation when evaluated later.

## Interpretation and additional API scopes

Backup and authorization collection details are in [the assurance guide](assurance.md), including [vCenter backup jobs](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/recovery/backup/job/details/get/) and [NSX backup history](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_GetBackupHistory.html). NSX raw backup timestamps remain unverified by default. Add `--nsx-time-unit milliseconds` only after confirming the timestamp unit for the installed API; the report records that operator-supplied interpretation.

The [vSAN guide](vsan.md) describes its dedicated JSON API session, explicit cluster managed-object IDs, allowed schema releases, cached health queries, and byte-based physical capacity. A configured release and a successful query are not a blanket compatibility certification. Cached health time remains separate from collection time.

The [activity guide](activity.md) covers the documented [HCX migration query](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/migrations/post/), [NSX rule statistics](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_GetRuleStatistics.html), and [Automation deployment requests](https://developer.broadcom.com/xapis/vm-apps-org-policies/latest/deployment/api/deployments/deploymentId/requests/get/). HCX elapsed duration remains unknown unless `--hcx-time-unit seconds` or `--hcx-time-unit milliseconds` supplies the confirmed API unit. Two saved observations are still required for an unchanged-progress interval. Zero counters do not establish that a firewall rule is unnecessary.

Authorization observations use the [vCenter authorization APIs](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/vcenter/). The optional baseline compares exact explicit assignments. A privilege-count threshold identifies review candidates; it does not calculate effective access or establish a security verdict. Use the existing comparison command on `authorization_roles` and `authorization_permissions` to compare complete catalogs across runs.

Report status describes the completeness of its evidence. Exit code 0 means the report completed with the required observations; findings can still be present. Code 2 means at least part of the evidence is unknown or unavailable. Code 1 means input validation or local file access failed. Threshold findings and native product states remain separate from collection failures. Included tests use offline fixtures; live appliance behavior remains unverified.
