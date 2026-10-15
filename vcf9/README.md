# VCF 9.1.x read-only reports

By Paul Bryant

These examples collect a small operational baseline without changing infrastructure. They target the VCF 9.1.x product line and VCF PowerCLI 9.1.x. The original repository examples remain scoped to their earlier product generations.

| Report | Data collected | Tool |
| --- | --- | --- |
| [SDDC Manager inventory](sddc_inventory.py) | Appliance version, workload domains, clusters, hosts | Python standard library |
| [SDDC Manager health](sddc_health.py) | Certificate expiry metadata and recently failed tasks | Python standard library |
| [vSphere inventory](Get-Vcf91VsphereInventory.ps1) | vCenter version, hosts, clusters, datastores, VMs | VCF PowerCLI |
| [Aged snapshots](Get-Vcf91SnapshotReport.ps1) | VM, snapshot name, creation time, age, size | VCF PowerCLI |
| [Cluster host builds](Get-Vcf91ClusterHostBuilds.ps1) | ESXi versions and builds within each cluster | VCF PowerCLI |

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
