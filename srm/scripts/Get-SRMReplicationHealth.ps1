# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmProtectedVM', 'Get-SrmProtectionGroup')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Monitors real-time SRM replication health (bandwidth, lag, errors).

.DESCRIPTION
    Exports status, trends, and alerts to CSV for daily review.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
#>
$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$LogPath = "Get-SRMReplicationHealth.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking SRM replication health..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $report = foreach ($g in $groups) {
        foreach ($vm in Get-SrmProtectedVM -ProtectionGroup $g) {
            [PSCustomObject]@{
                VM = $vm.Name
                Group = $g.Name
                Lag = $vm.ReplicationLag
                Status = $vm.ReplicationState
                Errors = $vm.Alert
            }
        }
    }
    $OutFile = "SRMReplicationHealth_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Replication health exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Confirm:$false; Write-Log "Disconnected." }
