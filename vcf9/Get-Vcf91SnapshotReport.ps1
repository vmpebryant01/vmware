# Author: Paul Bryant
# Read-only snapshot age report for VCF 9.1.x operations.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$VCenter,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$OutputDirectory,
    [ValidateRange(1, 3650)][int]$OlderThanDays = 7,
    [pscredential]$Credential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PowerCLI-Common.ps1')
Assert-Vcf91PowerCLI
if (-not (Get-Command Get-Snapshot -ErrorAction SilentlyContinue)) { throw 'VCF PowerCLI is missing Get-Snapshot.' }
if ($null -eq $Credential) { $Credential = Get-Credential -Message "Credentials for $VCenter" }
$server = $null
try {
    $server = Connect-VIServer -Server $VCenter -Credential $Credential -NotDefault -ErrorAction Stop
    $cutoff = (Get-Date).AddDays(-$OlderThanDays)
    $rows = @(foreach ($vm in (Get-VM -Server $server -ErrorAction Stop)) {
        foreach ($snapshot in (Get-Snapshot -VM $vm -Server $server -ErrorAction Stop)) {
            if ($snapshot.Created -le $cutoff) {
                [pscustomobject]@{
                    VM = Protect-CsvText $vm.Name
                    Snapshot = Protect-CsvText $snapshot.Name
                    CreatedUtc = $snapshot.Created.ToUniversalTime().ToString('o')
                    AgeDays = [math]::Floor(((Get-Date) - $snapshot.Created).TotalDays)
                    SizeGB = $snapshot.SizeGB
                }
            }
        }
    })
    $path = New-ReportDirectory -Path $OutputDirectory
    Export-ReportCsv -Path (Join-Path $path 'old_snapshots.csv') -Columns @('VM', 'Snapshot', 'CreatedUtc', 'AgeDays', 'SizeGB') -Rows $rows
    Write-Output "Saved $($rows.Count) snapshot rows in $path"
}
finally {
    if ($null -ne $server) {
        Disconnect-VIServer -Server $server -Confirm:$false -ErrorAction Continue | Out-Null
    }
}
