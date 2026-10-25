# Backup freshness and access assignments

Author: Paul Bryant

These optional resources and saved-run reports support backup and access reviews. They use the shared authentication, verified TLS, JSON, CSV, and collection-summary workflow. No backup, restore, schedule change, role change, or permission grant is performed. Select the resources explicitly; the default inventory remains unchanged.

The contracts have offline tests and have not been exercised against live appliances. The authorization APIs were introduced in vSphere API 9.0.0.0. Match availability and account privileges to the installed release; a missing endpoint does not by itself establish why it is unavailable. See Broadcom's [roles API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/authorization/roles/get/) and [permissions query API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/authorization/permissions__action=list/post/).

## Collection

Add these resources to the appropriate target's `resources` array:

```json
"resources": ["backup_jobs", "backup_schedules", "authorization_roles", "authorization_permissions"]
```

For an NSX target, select `"resources": ["backup_history"]`. No additional target options are required. Filters for these resources are rejected, so the exported scope is the account-visible endpoint response.

| Component | Resource | Request and retained metadata |
| --- | --- | --- |
| `vcenter` | `backup_jobs` | `GET /api/appliance/recovery/backup/job/details`; job ID, status, completion/start times, duration, size, type, and fast-backup flag. [Job details API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/recovery/backup/job/details/get/) |
| `vcenter` | `backup_schedules` | `GET /api/appliance/recovery/backup/schedules`; schedule ID, enabled flag, recurrence, retention count, and fast-backup flag. [Schedules API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/recovery/backup/schedules/get/) |
| `vcenter` | `authorization_roles` | `GET /api/vcenter/authorization/roles`; role ID, name, description, privileges, and system flag. [Roles API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/authorization/roles/get/) |
| `vcenter` | `authorization_permissions` | `POST /api/vcenter/authorization/permissions?action=list`; permission ID, principal, role ID, object ID/type, and propagation. This is a documented read query. [Permissions query API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/authorization/permissions__action=list/post/) |
| `nsx` | `backup_history` | `GET /api/v1/cluster/backups/history`; cluster, node, and inventory history with backup ID, raw numeric times, success flag, and error code. [Backup history API](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_GetBackupHistory.html) |

Backup destinations, backup users, detailed messages, and raw error payloads are excluded. Role and assignment rows include an `id` suitable for the existing saved-run comparison workflow. NSX backup IDs are combined with their history kind to distinguish records across arrays.

The permissions query sends only `{"iterate":{"page_size":100}}` initially, then the returned opaque marker in the same `iterate` structure. The configured `page_size` and `max_pages` limits apply. The transport permits this exact list action and body shape; the bare create-permission POST remains denied. Repeated identifiers, repeated markers, and exhausted page limits fail collection. The query is not automatically retried. See the [documented list request body](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/authorization/permissions__action=list/post/).

The role list currently uses the first service-defined page. If the response contains a continuation marker, collection fails with incomplete coverage. The public role schema describes an iteration structure, but its GET query serialization has not been verified. A truncated role catalog is not exported as complete. See the [role iteration schema](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/data-structures/Vcenter%20Authorization%20Roles%20IterationSpec/).

## Backup freshness report

Collect the resources first, then use the completed run directory:

```powershell
python collect.py --config config.json --output inventory --csv
python report_backup_freshness.py --run inventory\RUN_DIRECTORY --output reports\backup_freshness.json --max-age-hours 24 --csv
```

The report evaluates vCenter appliance history and each NSX history kind separately. It shows the last dated successful completion, its age, failures, whether a dated failure followed that success, and vCenter schedule state. Freshness is evaluated at the saved resource's `collected_at` time, with `summary.completed_at` used only when the resource time is absent. `observed_at` and `source_age_hours` distinguish that evidence from the later report evaluation. An old snapshot cannot establish what backups occurred afterward. The vCenter successful status is `SUCCEEDED`, following the [task status enumeration](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/data-structures/Cis%20Task%20Status/). A success older than the threshold at collection is marked `stale`; an enabled schedule does not override stale history.

Missing resources, undated or invalid successful completions, completions after the observation time, invalid or future observation times, unrecognized statuses, and no visible successful history remain unknown. A timezone is required in vCenter completion timestamps. The NSX timestamp-unit schema could not be verified, so NSX age classification stays unknown by default while raw times and success history remain available. Broadcom's [history response examples](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_GetBackupHistory.html) are consistent with epoch milliseconds, but do not explicitly establish the unit.

After confirming that unit against the installed appliance, the operator can supply it explicitly:

```powershell
python report_backup_freshness.py --run inventory\RUN_DIRECTORY --output reports\backup_freshness.json --max-age-hours 24 --nsx-time-unit milliseconds --csv
```

With that option, NSX rows state `timestamp_basis: operator_supplied_epoch_milliseconds`. The report does not infer the unit automatically.

History covers retained, account-visible records. The report does not test backup content, destination connectivity, restore readiness, or NSX schedule configuration. A report's `success` status means its available evidence was evaluated without unknown observations; stale history and disabled schedules can still require action. Missing evidence produces `partial` and exit code 2.

## Access assignments report

```powershell
python report_access_permissions.py --run inventory\RUN_DIRECTORY --output reports\access_permissions.json --broad-privilege-threshold 100 --csv
```

The report joins explicit permissions with roles and lists the principal, object scope, role, and propagation flag. It includes role-catalog rows and counts distinct privilege IDs. Reaching the chosen threshold marks a role for review. The count is not a severity rating and does not establish whether a role is appropriate. Group membership and effective user access are outside this report. vCenter can combine group privileges and apply user-specific precedence; see the [authorization model](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/vcenter/vcenter-authorization-permissions/).

Optionally supply an exact assignment baseline:

```json
{
  "author": "Paul Bryant",
  "schema_version": "1.0",
  "permissions": [
    {
      "target": "vc-a",
      "endpoint": "https://vcenter.example.com",
      "principal_type": "USER",
      "principal_name": "inventory-reader",
      "principal_domain": "example.local",
      "role_id": "replace-with-role-id",
      "object_type": "GlobalAcl",
      "object_id": "GlobalAcl",
      "propagating": true
    }
  ]
}
```

```powershell
python report_access_permissions.py --run inventory\RUN_DIRECTORY --baseline access_baseline.json --output reports\access_permissions.json --csv
```

Each baseline entry must include every field shown. Use `null` for `principal_domain` when the API omits it. Endpoints must exactly match the collected HTTPS origin, including any explicit port. A baseline match records an expected assignment, without approving its security. Different propagation or object scope is a different assignment. Global permissions use the documented `GlobalAcl` object; see Broadcom's [vSphere authorization API example](https://blogs.vmware.com/cloud-foundation/2025/07/07/automating-vsphere-authorization-with-global-authorization-apis/).

Assignments absent from the baseline and baseline assignments not observed in complete inventory are marked for review. Failed, malformed, or differently scoped evidence stays unknown. An unobserved assignment does not prove revocation. For changes between two collected role/permission snapshots, use the existing comparison command, retaining the same endpoint, configured scope, and account visibility.

Reports contain account names and infrastructure identifiers. Protect the inventory, baseline, and report files according to their audience. Write report output outside the source run directories.
