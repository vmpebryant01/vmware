# Optional operational resources

Author: Paul Bryant

Select these resources explicitly in a target's `resources` array to collect operational metadata through the shared authentication, TLS, JSON, CSV, and summary workflow. They do not expand the default inventory selection. All operational data requests use GET. Recovery collection can use the existing local and remote authentication requests when credentials are configured.

These resources use documented contracts and offline response tests. They have not been exercised against a live environment. Match API availability and permissions to the installed component release.

| Component | Optional resources | Additional target settings |
| --- | --- | --- |
| `sddc_manager` | `certificates`, `failed_tasks` | Optional `domain_ids`, `certificate_attention_days`, `task_days`. |
| `nsx` | `security_rules` | Required `policy_ids`; existing `domain_id` defaults to `default`. |
| `vcf_automation` | `catalog_items` | Existing `api_family` must be `all_apps` or `vm_apps`. |
| `live_site_recovery` | `folder_mappings`, `network_mappings`, `resource_mappings`, `storage_policy_mappings`, `test_network_mappings` | Required `pairing_id` and `srm_ids`; existing recovery authentication settings apply. |
| `vcf_operations` | `collectors` | Existing Operations authentication settings apply. |

Identifier lists accept 1 to 1,000 unique simple identifiers. Identifiers cannot contain URL escapes or path separators. Domain, policy, and SRM lists define separate scopes; their contents are not inferred from object names.

## SDDC Manager certificate metadata and failed tasks

For example, add these fields to an SDDC Manager target:

```json
"resources": ["certificates", "failed_tasks"],
"domain_ids": ["replace-with-domain-id"],
"certificate_attention_days": 60,
"task_days": 30
```

Omit `domain_ids` to enumerate visible domains. Otherwise, only the named domain IDs are queried. Certificate collection reads `/v1/domains/{domain_id}/resource-certificates` and retains resource identity, issued-to name, expiry date, remaining days, installation state, and renewal status. It excludes certificate PEM data, CA chains, and detailed error messages. See Broadcom's [domain certificate API](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/domains/id/resource-certificates/get/).

The `attention` field is true only for an installed certificate when the reported status is expired or about to expire, or its integer remaining-day value is at or below `certificate_attention_days`. This threshold defaults to 60 days and accepts integers from 1 to 3,650. It marks records for review and does not establish certificate trust, validate the chain, or initiate renewal. Missing expiry information is not proof of certificate health. Each row records the threshold and domain scope.

`failed_tasks` queries `/v1/tasks` with a fixed `completedAfter` cutoff in epoch milliseconds, then retains only tasks whose status is `FAILED`, ignoring case. The requested page size is capped at the API's documented maximum of 100. `task_days` defaults to 30 and accepts integers from 1 to 3,650. Rows contain task ID, name, type, status, creation/completion timestamps, resolution state, the requested window, and its cutoff. They exclude nested subtasks and full error payloads. The API's completed-task filter covers successful and failed statuses; this resource does not report every warning, timeout, cancellation, or unfinished task. See the [task API](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/tasks/get/).

The task window moves on each run. A task disappearing from a later window does not establish that the underlying issue was resolved.

## NSX distributed firewall rules

Add an explicit policy scope to an NSX target:

```json
"resources": ["security_rules"],
"domain_id": "default",
"policy_ids": ["application-policy", "infrastructure-policy"]
```

Each selected policy is queried at `/policy/api/v1/infra/domains/{domain_id}/security-policies/{policy_id}/rules`. Collection follows opaque cursors, including after short pages. Records contain domain ID, policy ID, rule ID, display name, action, direction, disabled state, logging state, and sequence number. Source/destination groups and other nested rule configuration are omitted. This resource does not enumerate project or Global Manager scopes or assess effective firewall behavior. See the [distributed firewall rule list API](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListSecurityRules.html).

## Automation catalog availability

Add `catalog_items` to an All Apps or VM Apps organization target:

```json
"resources": ["catalog_items"],
"api_family": "all_apps"
```

Collection uses `/catalog/api/items` with zero-based `page` and `size`. Records retain item ID, name, requestability, global state, creation/update timestamps, and the count of visible project IDs. The project count is null when the API omits that list. Catalog schemas, user details, and nested content are excluded. Provider-family targets cannot select this resource. Refer to the separate [All Apps catalog API](https://developer.broadcom.com/xapis/all-apps-org-instances/latest/catalog/api/items/get/) and [VM Apps catalog API](https://developer.broadcom.com/xapis/vm-apps-org-deployment/latest/catalog/api/items/get/).

## Recovery inventory mappings

Add mappings to a Live Site Recovery target, using the actual pairing and SRM identifiers:

```json
"resources": ["folder_mappings", "network_mappings", "resource_mappings", "storage_policy_mappings", "test_network_mappings"],
"pairing_id": "replace-with-pairing-id",
"srm_ids": ["replace-with-srm-id"]
```

The configured pairing must be visible to the authenticated session. The collector uses the existing recovery pairing discovery, remote login, and offset/limit handling. With username/password authentication, configure both `remote_username_env` and `remote_password_env` for the explicit pairing. An externally supplied session must already provide the required site access. No new appliance or remote endpoint is followed automatically.

Mapping requests use `/api/rest/srm/v2/pairings/{pairing_id}/srms/{srm_id}/inventory-mappings/` followed by the resource suffix:

| Resource | Suffix | Exported fields in addition to pairing and SRM IDs |
| --- | --- | --- |
| `folder_mappings` | `folders` | Mapping ID, primary/secondary object names, reverse mapping type. |
| `network_mappings` | `networks` | Same selected mapping metadata. |
| `resource_mappings` | `resources` | Same selected mapping metadata. |
| `storage_policy_mappings` | `storage-policies` | Same selected mapping metadata. |
| `test_network_mappings` | `test-networks` | Mapping ID, target network, test network, and test network name. |

These records describe configured mappings. They do not validate recovery readiness or initiate a recovery test, failover, or configuration change. A failed SRM request prevents the combined resource from being exported as successful. API-reported partial list errors are also failures. Public method references: [folder mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/folders/get/), [network mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/networks/get/), [resource mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/resources/get/), [storage policy mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/storage-policies/get/), and [test network mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/test-networks/get/).

## Operations collector status

Select `"resources": ["collectors"]` on an Operations target. The collector reads `/suite-api/api/collectors` and exports only collector ID, name, reported state, local flag, and data persistence flag. Adapter membership and other nested data are excluded. Reported state is operational metadata rather than an end-to-end availability test. See the [Operations collector API](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/collectors/get/).

## Running and interpreting collection

After configuring credentials or tokens through the existing environment-variable workflow, run:

```powershell
python .\collect.py --config .\config.json --output .\inventory --csv
```

Each selected operational resource uses the normal JSON file, optional CSV, and per-resource result in `summary.json`. Review the summary before treating files as complete. Pagination limits apply to each underlying list operation, including each domain, policy, pairing discovery, and SRM mapping scope. Repeated pages, inconsistent totals, malformed collections, and exhausted page limits fail explicitly.

Field selection reduces exposure but does not make infrastructure names and status data public. Store the output with the same access controls as other inventory. These exports are selected metadata, not full backups, security conclusions, or readiness certifications.
