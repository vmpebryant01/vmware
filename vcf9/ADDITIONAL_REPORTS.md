# Additional VCF 9.1.1 operational reports

By Paul Bryant

These 30 Python commands export selected inventory and status fields to CSV. They do not change infrastructure. The 15 Protection and Recovery commands use the current Site Recovery Manager v2 API within VCF Protection and Recovery. The product has its own release version, so the SDDC Manager 9.1.1 version check does not establish its version. [Broadcom's product naming notice](https://knowledge.broadcom.com/external/article/426655/build-numbers-and-versions-of-vcf-protec.html) and [v2 API guide](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/) describe that distinction.

Run commands from the repository root with Python 3.11 or later. Every command requires `--host` and `--output-dir`. The output directory is created if needed; rerunning a command replaces its own CSV. Use `--ca-bundle C:\certs\root-ca.pem` when the site's CA is not in the operating system trust store. TLS validation stays enabled. CSV cells are escaped for spreadsheet formula safety. Store the reports where only authorized operators can read them.

## NSX Manager: five commands

These commands require `--username` and prompt for the NSX Manager password. The [NSX 9.1.1 API guide](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/) documents cursor pagination. Some NSX sites disable Basic authentication; use an account and access method allowed by site policy. Each command covers the specified infra, domain, segment, or site scope, not every possible NSX project or Global Manager object.

| Module suffix under `vcf9.nsx` | Extra arguments | Report and API |
| --- | --- | --- |
| `segments` | None | [Infra segments](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListAllInfraSegments.html) |
| `groups` | `--domain-id` | [Groups in one domain](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListGroupForDomain.html) |
| `segment_ports` | `--segment-id` | [Ports on one infra segment](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListInfraSegmentPorts.html) |
| `transport_zones` | `--site-id`, `--enforcement-point-id` | [Transport zones under one enforcement point](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListTransportZonesForEnforcementPoint.html) |
| `security_rules` | `--domain-id`, `--policy-id` | [Rules in one distributed firewall policy](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListSecurityRules.html) |

```powershell
python -m vcf9.nsx.segments --host nsx.example.com --username report-user --output-dir reports/nsx
python -m vcf9.nsx.security_rules --host nsx.example.com --username report-user --domain-id default --policy-id application --output-dir reports/nsx
```

The firewall report exports rule action, direction, disabled state, logging state, and order. It omits source and destination group paths and is an inventory, not an evaluation of effective security.

## VCF Operations: five commands

Set `VCF_OPS_TOKEN` in the process environment using a session token from your approved sign-in process. The default authorization scheme is `OpsToken`; use `--token-scheme Bearer` if the value is a VCF SSO access token. Do not save tokens in the repository.

| Module suffix under `vcf9.operations` | Report and API |
| --- | --- |
| `alert_definitions` | [Alert definition identifiers and timing](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/alertdefinitions/get/) |
| `policies` | [Policy summaries](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/policies/get/) |
| `collectors` | [Collector states](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/collectors/get/) |
| `collector_groups` | [Collector group membership counts and HA settings](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/collectorgroups/get/) |
| `custom_groups` | [Custom group names and resource kinds](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/groups/get/) |

```powershell
python -m vcf9.operations.collectors --host ops.example.com --output-dir reports/operations
```

## SDDC Manager: five commands

These commands require `--username` and prompt for a password. They verify that the target appliance identifies itself as SDDC Manager 9.1.1.x before collecting data. The release and bundle endpoints return page metadata but do not document page selectors; those commands stop with an error if more than one page exists, instead of writing incomplete reports.

| Module suffix under `vcf9.fleet` | Report and API |
| --- | --- |
| `vcenters` | [vCenter versions and states](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/vcenters/get/) |
| `nsx_clusters` | [NSX cluster versions and states](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/nsxt-clusters/get/) |
| `releases` | [Available release metadata](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/releases/get/) |
| `bundles` | [Bundle catalog metadata](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/bundles/get/) |
| `notifications` | [Notification severity and timestamps](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/notifications/get/) |

```powershell
python -m vcf9.fleet.vcenters --host sddc.example.com --username report-user --output-dir reports/vcf
```

## VCF Protection and Recovery: fifteen commands

Use the host serving the `/api/rest/srm/v2` endpoint and an account authorized to read Site Recovery Manager data. The command prompts for a local site password. Every command with `--pairing-id` also prompts for a remote site password and opens a [remote session](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/remote-session/post/) as shown in the [v2 getting started guide](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/). Use `--remote-username` when that account differs from `--username`. Sessions are logged out after collection. The login and remote session requests change session state only; report data comes from GET requests. These reports do not initiate protection, failover, testing, or recovery actions.

| Module suffix under `vcf9.protection_recovery` | Extra arguments | Report and API |
| --- | --- | --- |
| `pairings` | None | [Site pairings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/get/) |
| `pairing_issues` | `--pairing-id` | [Pairing issues](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/issues/get/) |
| `srms` | `--pairing-id` | [SRM server versions and status](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/get/) |
| `srm_issues` | `--pairing-id`, `--srm-id` | [SRM server issues](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/issues/get/) |
| `protection_groups` | `--pairing-id` | [Protection groups](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/protection-management/groups/get/) |
| `group_issues` | `--pairing-id`, `--group-id` | [Protection group issues](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/protection-management/groups/group_id/issues/get/) |
| `group_vms` | `--pairing-id`, `--group-id` | [VMs in a protection group](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/protection-management/groups/group_id/vms/get/) |
| `recovery_plans` | `--pairing-id` | [Recovery plans](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/recovery-management/plans/get/) |
| `plan_issues` | `--pairing-id`, `--plan-id` | [Recovery plan issues](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/recovery-management/plans/plan_id/issues/get/) |
| `plan_protection_groups` | `--pairing-id`, `--plan-id` | [Protection groups in a plan](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/recovery-management/plans/plan_id/protection-groups/get/) |
| `folder_mappings` | `--pairing-id`, `--srm-id` | [Folder mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/folders/get/) |
| `network_mappings` | `--pairing-id`, `--srm-id` | [Network mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/networks/get/) |
| `resource_mappings` | `--pairing-id`, `--srm-id` | [Resource mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/resources/get/) |
| `storage_policy_mappings` | `--pairing-id`, `--srm-id` | [Storage policy mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/storage-policies/get/) |
| `test_network_mappings` | `--pairing-id`, `--srm-id` | [Test network mappings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/srms/srm_id/inventory-mappings/test-networks/get/) |

```powershell
python -m vcf9.protection_recovery.pairings --host recovery.example.com --username report-user --output-dir reports/recovery
python -m vcf9.protection_recovery.protection_groups --host recovery.example.com --username report-user --pairing-id 55169ee6-a6fa-363c-b4c8-9c8808e79d43 --output-dir reports/recovery
```

The pairing report excludes certificate bodies. Other commands select only their documented columns, omitting nested configuration and authentication payloads. Empty mappings can be expected, but they do not establish that the recovery plan is ready. The reports are inventory snapshots. Check the product interface and site runbooks for operational conclusions.

## Validation status

The commands have offline tests for path construction, credential handling, pagination, column selection, and incomplete-response errors. They have **not been run against a live VCF 9.1.1 or Protection and Recovery environment**. API permissions and optional fields must be checked with a read-only account in a site environment before relying on the CSVs for operations.
