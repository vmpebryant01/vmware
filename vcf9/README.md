# VCF 9.1.x read-only reports

By Paul Bryant

The [additional VCF 9.1.1 reports](ADDITIONAL_REPORTS.md) add 5 NSX, 5 Operations, 5 SDDC Manager, and 15 Protection and Recovery commands.

The [shared API collectors](api_collectors/README.md) add Fleet LCM, multi-component inventory, preflight, large vCenter collection, latest metrics, comparisons, and identifier-based relationships. Certificate, failed-task, firewall-rule, catalog, collector-state, and recovery-mapping resources also use the shared transport and JSON/CSV output. Existing standalone reports remain available below.

These examples collect a small operational baseline without changing infrastructure. They target the VCF 9.1.x product line and VCF PowerCLI 9.1.x. The original repository examples remain scoped to their earlier product generations.

The [eleven saved-run operational reports](api_collectors/docs/reports.md) add backup freshness, explicit protection requirements, cached vSAN health and capacity, HCX migration progress, vCenter access assignments, NSX rule counters, Automation request exceptions, lifecycle compliance, vCenter service settings, historical metric windows, and Supervisor/namespace state. Their additional resources are selected explicitly; the existing default collections retain their scope. The [live validation tool](api_collectors/docs/live_validation.md) applies request limits to actual collector runs and exports numeric build evidence with optional structural fixtures.

| Report | Data collected | Tool |
| --- | --- | --- |
| [SDDC Manager inventory](sddc_inventory.py) | Appliance version, workload domains, clusters, hosts | Python standard library |
| [SDDC Manager health](sddc_health.py) | Certificate expiry metadata and recently failed tasks | Python standard library |
| [vSphere inventory](Get-Vcf91VsphereInventory.ps1) | vCenter version, hosts, clusters, datastores, VMs | VCF PowerCLI |
| [Aged snapshots](Get-Vcf91SnapshotReport.ps1) | VM, snapshot name, creation time, age, size | VCF PowerCLI |
| [Cluster host builds](Get-Vcf91ClusterHostBuilds.ps1) | ESXi versions and builds within each cluster | VCF PowerCLI |

## Ten additional VCF 9.1.1 reports

These commands are read-only examples for a VCF 9.1.1 deployment. Each module writes one CSV file. They use documented GET endpoints, except for the existing SDDC Manager token request, and select only the columns listed below. Run them from the repository root with Python 3.11 or later.

| Area | Module | Report |
| --- | --- | --- |
| Fleet | `vcf9.fleet.management_components` | Management component FQDNs and deployment states |
| Fleet | `vcf9.fleet.services` | SDDC Manager service versions and states |
| Fleet | `vcf9.fleet.depot_sync` | Depot synchronization state and last completion time |
| Operations | `vcf9.operations.alerts` | Alert IDs, severity, state, and timestamps |
| Operations | `vcf9.operations.adapters` | Adapter collection and heartbeat metadata |
| Operations | `vcf9.operations.resources` | Inventory for one selected resource kind |
| Automation | `vcf9.automation.deployments` | Deployment and last request status |
| Automation | `vcf9.automation.catalog` | Catalog item availability and project count |
| NSX | `vcf9.nsx.gateways` | Tier-0 and Tier-1 gateway inventory |
| NSX | `vcf9.nsx.security_policies` | Distributed firewall policy inventory and rule counts |

Fleet commands prompt for an SDDC Manager password and verify that the appliance reports a 9.1.1 version. Operations commands require a valid VCF Operations session token in the process environment as `VCF_OPS_TOKEN`; the request uses the documented `OpsToken` authorization scheme. For a VCF SSO access token, set the same environment variable and add `--token-scheme Bearer`. Automation commands require a valid JWT access token as `VCF_AUTOMATION_TOKEN`; the request uses Bearer authorization. Obtain tokens through your site's approved sign-in process and do not save them in the repository. NSX commands prompt for a password and use HTTP Basic authentication over verified TLS; this may be disabled by site policy. Use read-only accounts where possible. All four target types accept `--ca-bundle` for a private issuing CA, and no command disables certificate checks.

```powershell
python -m vcf9.fleet.management_components --host sddc.example.com --username report-user --output-dir reports/fleet/components
python -m vcf9.fleet.services --host sddc.example.com --username report-user --output-dir reports/fleet/services
python -m vcf9.fleet.depot_sync --host sddc.example.com --username report-user --output-dir reports/fleet/depot
python -m vcf9.operations.alerts --host ops.example.com --output-dir reports/operations/alerts
python -m vcf9.operations.adapters --host ops.example.com --output-dir reports/operations/adapters
python -m vcf9.operations.resources --host ops.example.com --resource-kind VirtualMachine --output-dir reports/operations/resources
python -m vcf9.automation.deployments --host automation.example.com --output-dir reports/automation/deployments
python -m vcf9.automation.catalog --host automation.example.com --output-dir reports/automation/catalog
python -m vcf9.nsx.gateways --host nsx.example.com --username report-user --output-dir reports/nsx/gateways
python -m vcf9.nsx.security_policies --host nsx.example.com --username report-user --domain-id default --output-dir reports/nsx/policies
```

Replace the example hosts and NSX domain ID with site values. The Operations resource kind is required to limit inventory scope. Pagination has a 1000-page safety limit, and incomplete or malformed responses fail rather than silently producing partial CSVs. CSV values are escaped against spreadsheet formula interpretation. Output includes infrastructure names and IDs; store it in a restricted location. Repeating a command in the same output directory replaces that command's CSV. The depot report records whether an error message exists but omits its contents; the Automation reports omit deployment inputs, outputs, user email addresses, and catalog schemas. The catalog's visible project count is blank when the API omits project IDs. The NSX policy report lists policies and counts, not individual rules or an assessment of firewall effectiveness.

The SDDC Manager version check does not establish the version of the other components. The Operations, Automation, and NSX examples do not have a version preflight; point them only at the intended 9.1.1 components. Product permissions and response shapes may vary by deployment and patch level. These new reports have offline fixture tests and **have not been exercised against a live environment**.

API references: [management components](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/vcf-management-components/get/), [services](https://developer.broadcom.com/xapis/vmware-cloud-foundation-api/latest/v1/vcf-services/get/), [depot sync](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/system/settings/depot/depot-sync-info/get/), [Operations alerts](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/alerts/get/), [adapters](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/adapters/get/), [resources](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/get/), [Automation deployments](https://developer.broadcom.com/xapis/vm-apps-org-catalog/latest/deployment/api/deployments/get/), [catalog items](https://developer.broadcom.com/xapis/vm-apps-org-deployment/latest/catalog/api/items/get/), [NSX Tier-0](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListTier0s.html), [Tier-1](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListTier1.html), and [security policies](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListSecurityPoliciesForDomain.html).

## Run the reports

Use Python 3.11 or later for the SDDC Manager report. Provide the SDDC Manager name, a user with read access, and an output directory. The script prompts for the password and keeps the access token in memory. The token endpoint also issues a refresh token, which the script does not save or use. Review your SDDC Manager token expiration policy. TLS certificate verification is on by default. Supply `--ca-bundle` when the issuing CA is absent from the system trust store.

```powershell
python vcf9/sddc_inventory.py --host sddc.example.com --username report-user --output-dir reports/sddc --ca-bundle C:\certs\root-ca.pem
python -m vcf9.sddc_health --host sddc.example.com --username report-user --output-dir reports/health --ca-bundle C:\certs\root-ca.pem --days 30 --expires-within 60
```

The health report writes `certificates.csv` for all top-level certificates returned by the API, `certificate_attention.csv` for installed certificates that are expired or near expiry, `failed_tasks.csv` for tasks completed in the selected time window with a failed status, and `report_info.csv` for the collection time and thresholds. Certificate PEM data and full task error payloads are not exported. A certificate attention row is a review candidate, not a replacement instruction. The SDDC Manager API defines the `completedAfter` task filter for successful and failed tasks; warning and timeout states may require separate review in the product interface.

For the PowerCLI reports, use PowerShell 7.4 or later and install VCF.PowerCLI 9.1.x from the [Broadcom installation guide](https://developer.broadcom.com/powercli/installation-guide). The scripts check for the 9.1.x bundle and prompt for a credential. Leave certificate validation enabled and trust the issuing CA before connecting.

```powershell
Install-Module -Name VCF.PowerCLI -RequiredVersion 9.1.1.25718932 -Scope CurrentUser
./vcf9/Get-Vcf91VsphereInventory.ps1 -VCenter vc.example.com -OutputDirectory reports/vsphere
./vcf9/Get-Vcf91SnapshotReport.ps1 -VCenter vc.example.com -OutputDirectory reports/snapshots -OlderThanDays 14
./vcf9/Get-Vcf91ClusterHostBuilds.ps1 -VCenter vc.example.com -OutputDirectory reports/host-builds
```

Use a dedicated output directory for each run. Running the same report again in the same directory replaces its CSV files. The CSV files contain infrastructure names, versions, and capacity information, so store them with appropriate access controls. The snapshot report lists candidates for review and never removes snapshots. Snapshot size requires the vCenter `Datastore/Browse datastore` privilege; without it, PowerCLI may leave the size blank.

The cluster host build report flags clusters with more than one ESXi version/build combination. Mixed builds can be expected during lifecycle operations. The report does not determine whether a combination is supported, and it does not include standalone hosts.

## Compatibility and validation

The SDDC Manager script checks that the appliance reports version 9.1.x and then uses the documented `/v1` token, appliance, domain, cluster, and host endpoints. The `/v1` segment is an API resource version, not a VCF product version. The PowerCLI scripts check the installed VCF.PowerCLI bundle; they record the connected vCenter version because a VCF environment can contain components at different versions during lifecycle operations.

Offline tests cover Python request methods, pagination, version rejection, TLS verification, report selection, and CSV output. PowerShell files are syntax checked. These reports have **not been run against a live VCF 9.1.x environment**. Confirm permissions, returned fields, performance, and site policies in a nonproduction environment before operational use.

Broadcom references: [VCF release history](https://knowledge.broadcom.com/external/article?legacyId=52520), [VCF PowerCLI 9.1.1 package](https://www.powershellgallery.com/packages/VCF.PowerCLI/9.1.1.25718932), [SDDC Manager token creation](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/tokens/post/), [appliance information](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/system/appliance-info/get/), [domains](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/domains/get/), [clusters](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/clusters/get/), [hosts](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/hosts/get/), [domain certificates](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/domains/id/resource-certificates/get/), [tasks](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/tasks/get/), [PowerCLI Get-VMHost](https://developer.broadcom.com/powercli/latest/vmware.vimautomation.core/commands/get-vmhost).
