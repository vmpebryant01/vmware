# Author: Paul Bryant
# Read-only vCenter inventory report for VCF 9.1.x operations.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$VCenter,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$OutputDirectory,
    [pscredential]$Credential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PowerCLI-Common.ps1')
Assert-Vcf91PowerCLI
foreach ($name in @('Get-VMHost', 'Get-Cluster', 'Get-Datastore')) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "VCF PowerCLI is missing $name." }
}
if ($null -eq $Credential) { $Credential = Get-Credential -Message "Credentials for $VCenter" }
$server = $null
try {
    $server = Connect-VIServer -Server $VCenter -Credential $Credential -NotDefault -ErrorAction Stop
    $hosts = @(Get-VMHost -Server $server -ErrorAction Stop)
    $clusters = @(Get-Cluster -Server $server -ErrorAction Stop)
    $datastores = @(Get-Datastore -Server $server -ErrorAction Stop)
    $vms = @(Get-VM -Server $server -ErrorAction Stop)

    $path = New-ReportDirectory -Path $OutputDirectory
    [pscustomobject]@{
        VCenter = Protect-CsvText $VCenter
        Version = Protect-CsvText $server.Version
        CollectedUtc = [datetime]::UtcNow.ToString('o')
    } | Export-Csv -Path (Join-Path $path 'vcenter.csv') -NoTypeInformation -Encoding utf8

    $hostRows = @($hosts | ForEach-Object {
        [pscustomobject]@{
            Name = Protect-CsvText $_.Name
            Version = Protect-CsvText $_.Version
            Build = Protect-CsvText $_.Build
            ConnectionState = Protect-CsvText $_.ConnectionState
            CpuTotalMhz = $_.CpuTotalMhz
            CpuUsageMhz = $_.CpuUsageMhz
            MemoryTotalGB = $_.MemoryTotalGB
            MemoryUsageGB = $_.MemoryUsageGB
        }
    })
    Export-ReportCsv -Path (Join-Path $path 'hosts.csv') -Columns @('Name', 'Version', 'Build', 'ConnectionState', 'CpuTotalMhz', 'CpuUsageMhz', 'MemoryTotalGB', 'MemoryUsageGB') -Rows $hostRows

    $clusterRows = @($clusters | ForEach-Object {
        [pscustomobject]@{
            Name = Protect-CsvText $_.Name
            HAEnabled = $_.HAEnabled
            DrsEnabled = $_.DrsEnabled
        }
    })
    Export-ReportCsv -Path (Join-Path $path 'clusters.csv') -Columns @('Name', 'HAEnabled', 'DrsEnabled') -Rows $clusterRows

    $datastoreRows = @($datastores | ForEach-Object {
        [pscustomobject]@{
            Name = Protect-CsvText $_.Name
            Type = Protect-CsvText $_.Type
            CapacityGB = $_.CapacityGB
            FreeSpaceGB = $_.FreeSpaceGB
        }
    })
    Export-ReportCsv -Path (Join-Path $path 'datastores.csv') -Columns @('Name', 'Type', 'CapacityGB', 'FreeSpaceGB') -Rows $datastoreRows

    $vmRows = @($vms | ForEach-Object {
        [pscustomobject]@{
            Name = Protect-CsvText $_.Name
            PowerState = Protect-CsvText $_.PowerState
            NumCpu = $_.NumCpu
            MemoryGB = $_.MemoryGB
            VMHost = Protect-CsvText $_.VMHost
        }
    })
    Export-ReportCsv -Path (Join-Path $path 'vms.csv') -Columns @('Name', 'PowerState', 'NumCpu', 'MemoryGB', 'VMHost') -Rows $vmRows
    Write-Output "Saved five CSV reports in $path"
}
finally {
    if ($null -ne $server) {
        Disconnect-VIServer -Server $server -Confirm:$false -ErrorAction Continue | Out-Null
    }
}
