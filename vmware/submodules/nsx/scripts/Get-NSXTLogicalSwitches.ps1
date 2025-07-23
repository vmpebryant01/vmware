<#
.SYNOPSIS
    Exports all NSX-T logical switches (segments).

.DESCRIPTION
    Lists segment name, transport zone, VLAN, replication mode, and state.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTLogicalSwitches.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting NSX-T logical switches..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $segs = Get-NsxtSegment
    $report = $segs | Select DisplayName, TransportZoneDisplayName, VlanIds, ReplicationMode, AdminState
    $OutFile = "NSXTLogicalSwitches_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Logical switch report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
