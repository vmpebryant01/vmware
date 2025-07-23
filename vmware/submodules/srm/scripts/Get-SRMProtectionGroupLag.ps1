<#
.SYNOPSIS
    Exports replication lag and last sync for all SRM protection groups.

.DESCRIPTION
    Outputs group, VM count, max lag, and oldest sync for monitoring.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$LogPath = "Get-SRMProtectionGroupLag.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking SRM protection group lag..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $rows = @()
    foreach ($g in $groups) {
        $vms = Get-SrmProtectedVM -ProtectionGroup $g
        $maxLag = ($vms | Measure-Object -Property ReplicationLag -Maximum).Maximum
        $oldestSync = ($vms | Sort-Object LastReplication -Ascending | Select-Object -First 1).LastReplication
        $rows += [PSCustomObject]@{Group=$g.Name; VMCount=$vms.Count; MaxLag=$maxLag; OldestSync=$oldestSync}
    }
    $OutFile = "SRMProtectionGroupLag_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $rows | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Protection group lag exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Confirm:$false; Write-Log "Disconnected." }
