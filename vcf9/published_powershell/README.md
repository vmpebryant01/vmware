# Published-pattern VCF 9.1.1 PowerShell reports

By Paul Bryant

These 30 PowerShell 7.4 reports provide CSV snapshots for NSX Manager (5), VCF Operations (5), SDDC Manager (5), and VCF Protection and Recovery (15). They follow the read-only reporting style used elsewhere in this repository. The commands use documented REST APIs directly; they do not require the PowerCLI module. Sign-in and sign-out requests create and close API sessions, but the reports do not initiate infrastructure changes.

The reports were independently written for this repository using the linked vendor APIs and published reporting patterns in [PUBLISHED_SOURCES.md](PUBLISHED_SOURCES.md). Source projects document testing on some earlier releases, while other references are official published examples without a documented live run. **None of these 30 adaptations has been run against a live VCF 9.1.1 environment.** Do not treat a successful CSV export as proof of recovery readiness or compatibility with every deployment.

## Run a report

Run from the repository root with PowerShell 7.4 or later. Each script needs a host name and output directory. Use a read-only account where the product permits it. Your workstation must trust the target certificate chain. Do not disable TLS verification to make a report run.

```powershell
./vcf9/published_powershell/nsx/Get-Vcf91NsxSegmentsReport.ps1 -HostName nsx.example.com -OutputDirectory ./reports/nsx
```

NSX Manager scripts prompt for credentials. VCF Operations scripts read a token from `VCF_OPS_TOKEN` in the current process and default to the `OpsToken` scheme. Specify `-TokenScheme Bearer` for an approved VCF SSO access token.

```powershell
$env:VCF_OPS_TOKEN = '<session-token-from-approved-sign-in>'
./vcf9/published_powershell/operations/Get-Vcf91OperationsResourcesReport.ps1 -HostName ops.example.com -ResourceKind VirtualMachine -OutputDirectory ./reports/operations
Remove-Item Env:VCF_OPS_TOKEN
```

SDDC Manager scripts prompt for credentials, obtain an API token, and require an appliance version beginning `9.1.1`. Protection and Recovery scripts prompt for local credentials and, for pairing-scoped reports, remote credentials. Specify the host serving `/api/rest/srm/v2`; its release version is separate from SDDC Manager's. Reports with scope parameters require identifiers from your site.

```powershell
./vcf9/published_powershell/sddc/Get-Vcf91SddcVcentersReport.ps1 -HostName sddc.example.com -OutputDirectory ./reports/sddc
./vcf9/published_powershell/recovery/Get-Vcf91RecoveryPairingsReport.ps1 -HostName recovery.example.com -OutputDirectory ./reports/recovery
```

Each run replaces its own CSV file. CSV values that could execute as spreadsheet formulas are prefixed with an apostrophe. Keep exports in an operator-controlled location because inventory can be sensitive. See the [30-script source map](PUBLISHED_SOURCES.md) for each report's published reference and its evidence status. The endpoint-to-column mappings and scope limits follow the [VCF 9.1.1 API report notes](../ADDITIONAL_REPORTS.md).

## Verification

The repository includes an offline PowerShell check for script syntax, catalog consistency, API pagination, CSV field selection, and spreadsheet formula handling. Run it with:

```powershell
pwsh -NoProfile -File ./tests/Test-PublishedPowerShell.ps1
```

The check uses synthetic responses. Before operational use, verify credentials, permissions, endpoint responses, required fields, and output against your specific site with a read-only account.
