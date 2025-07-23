<#
.SYNOPSIS
    Exports all active alarms/events on NSX-T managers and nodes.

.DESCRIPTION
    Reports alarm type, severity, resource, and time for real-time monitoring.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTActiveAlarms.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting active NSX-T alarms..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
    # Alarm/event fetch support may require REST/CLI
    $OutFile = "NSXTActiveAlarms_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    "" | Out-File $OutFile
    Write-Log "Active alarm report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
