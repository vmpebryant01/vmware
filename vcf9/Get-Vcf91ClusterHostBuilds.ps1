# Author: Paul Bryant
# Read-only report of ESXi versions and builds by vCenter cluster.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$VCenter,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$OutputDirectory,
    [pscredential]$Credential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PowerCLI-Common.ps1')
Assert-Vcf91PowerCLI
foreach ($name in @('Get-Cluster', 'Get-VMHost')) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "VCF PowerCLI is missing $name." }
}
if ($null -eq $Credential) { $Credential = Get-Credential -Message "Credentials for $VCenter" }
$server = $null
try {
    $server = Connect-VIServer -Server $VCenter -Credential $Credential -NotDefault -ErrorAction Stop
    $rows = @(foreach ($cluster in (Get-Cluster -Server $server -ErrorAction Stop)) {
        $hosts = @(Get-VMHost -Location $cluster -Server $server -ErrorAction Stop)
        $builds = @($hosts | ForEach-Object { "$($_.Version)|$($_.Build)" } | Sort-Object -Unique)
        foreach ($hostEntry in $hosts) {
            [pscustomobject]@{
                Cluster = Protect-CsvText $cluster.Name
                Host = Protect-CsvText $hostEntry.Name
                Version = Protect-CsvText $hostEntry.Version
                Build = Protect-CsvText $hostEntry.Build
                ConnectionState = Protect-CsvText $hostEntry.ConnectionState
                ClusterHostCount = $hosts.Count
                BuildVariantCount = $builds.Count
                MixedBuilds = ($builds.Count -gt 1)
            }
        }
    })
    $path = New-ReportDirectory -Path $OutputDirectory
    Export-ReportCsv -Path (Join-Path $path 'cluster_host_builds.csv') -Columns @(
        'Cluster', 'Host', 'Version', 'Build', 'ConnectionState',
        'ClusterHostCount', 'BuildVariantCount', 'MixedBuilds'
    ) -Rows $rows
    Write-Output "Saved $($rows.Count) cluster host rows in $path"
}
finally {
    if ($null -ne $server) {
        Disconnect-VIServer -Server $server -Confirm:$false -ErrorAction Continue | Out-Null
    }
}
