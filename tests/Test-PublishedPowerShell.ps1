# Author: Paul Bryant
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Join-Path $PSScriptRoot '..\vcf9\published_powershell'
. (Join-Path $root 'Report-Common.ps1')
$catalog = Get-Content -LiteralPath (Join-Path $root 'reports.json') -Raw | ConvertFrom-Json -AsHashtable

if ($catalog.reports.Count -ne 30) { throw 'Expected 30 report definitions.' }
foreach ($entry in $catalog.reports.GetEnumerator()) {
    $spec = $entry.Value
    if ($spec.columns.Count -ne $spec.fields.Count) { throw "Column mismatch: $($entry.Key)" }
    $file = Join-Path $root $spec.script
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing script: $($entry.Key)" }
    $tokens = $null
    $errors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) { throw "Invalid PowerShell: $($entry.Key)" }
}

$script:mockResponses = @()
$script:nextResponse = 0
$script:requests = [Collections.Generic.List[string]]::new()
function Invoke-ReportRequest {
    param($Session, $Method, $Path, $Body, $AdditionalHeaders)
    $script:requests.Add($Path)
    $data = $script:mockResponses[$script:nextResponse]
    $script:nextResponse++
    return [pscustomobject]@{ Data = $data }
}

$script:mockResponses = @(
    ('{"results":[{"id":"first"}],"cursor":"next"}' | ConvertFrom-Json -AsHashtable),
    ('{"results":[{"id":"second"}]}' | ConvertFrom-Json -AsHashtable)
)
$result = Get-ReportItems -Session @{} -Spec $catalog.reports.segments -Path $catalog.reports.segments.path
if ($result.Items.Count -ne 2 -or $script:requests[1] -notmatch 'cursor=next') { throw 'NSX cursor pagination failed.' }

$script:mockResponses = @(
    ('{"results":[{"id":"first"}],"cursor":"next"}' | ConvertFrom-Json -AsHashtable),
    ('{"results":[{"id":"second"}],"cursor":"next"}' | ConvertFrom-Json -AsHashtable)
)
$script:nextResponse = 0
$repeatedCursorStopped = $false
try { $null = Get-ReportItems -Session @{} -Spec $catalog.reports.segments -Path $catalog.reports.segments.path }
catch { $repeatedCursorStopped = $true }
if (-not $repeatedCursorStopped) { throw 'Repeated cursor was accepted.' }

$script:mockResponses = @(
    ('{"resourceList":[{"identifier":"vm1"}],"pageInfo":{"totalCount":2}}' | ConvertFrom-Json -AsHashtable),
    ('{"resourceList":[{"identifier":"vm2"}],"pageInfo":{"totalCount":2}}' | ConvertFrom-Json -AsHashtable)
)
$script:nextResponse = 0
$script:requests.Clear()
$result = Get-ReportItems -Session @{} -Spec $catalog.reports.resources -Path '/suite-api/api/resources?resourceKind=VirtualMachine'
if ($result.Items.Count -ne 2 -or $script:requests[0] -notmatch '\?resourceKind=VirtualMachine&' -or $script:requests[1] -notmatch 'page=1') {
    throw 'Operations resource pagination failed.'
}

$script:mockResponses = @(
    ('{"list":[{"id":"pg1"}],"_meta":{"total":1}}' | ConvertFrom-Json -AsHashtable)
)
$script:nextResponse = 0
$result = Get-ReportItems -Session @{} -Spec $catalog.reports.protection_groups -Path '/pairings/p1/protection-management/groups'
if ($result.Items.Count -ne 1) { throw 'Recovery pagination failed.' }

$script:mockResponses = @(
    ('{"elements":[{"id":"release1"}],"pageMetadata":{"totalPages":2}}' | ConvertFrom-Json -AsHashtable)
)
$script:nextResponse = 0
$incompleteReleaseStopped = $false
try { $null = Get-ReportItems -Session @{} -Spec $catalog.reports.releases -Path '/v1/releases' }
catch { $incompleteReleaseStopped = $true }
if (-not $incompleteReleaseStopped) { throw 'Incomplete release list was accepted.' }

$script:mockResponses = @(
    ('{"adapterInstancesInfoDto":[{"id":"a1","resourceKey":{"name":"=SUM(1,1)","adapterKindKey":"VMWARE"},"credentialInstanceId":"secret"}]}' | ConvertFrom-Json -AsHashtable)
)
$script:nextResponse = 0
$script:requests.Clear()
$previousToken = $env:VCF_OPS_TOKEN
$env:VCF_OPS_TOKEN = 'offline-test-token'
$outputPath = Join-Path ([IO.Path]::GetTempPath()) ('vcf-report-test-' + [guid]::NewGuid().ToString('N'))
try {
    $null = Invoke-PublishedReport -Name adapters -HostName 'ops.example.com' -OutputDirectory $outputPath
    $csv = Import-Csv -LiteralPath (Join-Path $outputPath 'adapters.csv')
    if ($csv.Count -ne 1 -or $csv[0].name -ne "'=SUM(1,1)" -or $csv[0].PSObject.Properties.Name -contains 'credentialInstanceId') {
        throw 'CSV selection or formula protection failed.'
    }
}
finally {
    $env:VCF_OPS_TOKEN = $previousToken
    $resolvedTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $resolvedOutput = [IO.Path]::GetFullPath($outputPath)
    if ($resolvedOutput.StartsWith($resolvedTemp, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedOutput) -match '^vcf-report-test-[0-9a-f]{32}$') {
        Remove-Item -LiteralPath $resolvedOutput -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Output 'Published PowerShell offline checks passed.'
