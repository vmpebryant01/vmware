<#
.SYNOPSIS
    Cross-checks SRM protected VMs with backup jobs (CSV or API).

.DESCRIPTION
    Flags protected VMs missing from backups, and vice versa.
    Exports reconciliation report.

.NOTES
    PowerCLI >=13.0 required.
    Requires backup CSV/API mapping (e.g. Veeam).
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString
$backupCSV = Read-Host "Enter path to backup VM CSV"

$LogPath = "Correlate-SRMVMsWithBackup.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Cross-referencing SRM with backup jobs..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
} catch { Write-Log "ERROR: $_"; throw }

try {
    $srmVMs = Get-SrmProtectionGroup | Get-SrmProtectedVM | Select-Object -ExpandProperty Name
    $bkpVMs = Import-Csv $backupCSV | Select-Object -ExpandProperty Name
    $missingInBackup = $srmVMs | Where-Object { $_ -notin $bkpVMs }
    $missingInSRM    = $bkpVMs | Where-Object { $_ -notin $srmVMs }
    $OutFile = "SRM_Backup_Reconciliation_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $results = @()
    foreach ($vm in $missingInBackup) { $results += [PSCustomObject]@{VM=$vm; Status="ProtectedNoBackup"} }
    foreach ($vm in $missingInSRM)    { $results += [PSCustomObject]@{VM=$vm; Status="BackupOnly"} }
    $results | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported backup correlation to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed backup correlation."
