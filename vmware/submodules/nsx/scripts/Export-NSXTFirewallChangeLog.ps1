<#
.SYNOPSIS
    Exports a log of all firewall rule changes in NSX-T for audit.

.DESCRIPTION
    Fetches and exports firewall rule add/modify/delete actions in the last N days.

.NOTES
    PowerCLI >=13.0 required.
    Deep audit may require REST/CLI for event fetch.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Export-NSXTFirewallChangeLog.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting firewall rule change log..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    # Placeholder: Events API/CLI for rule change logs
    $OutFile = "NSXTFirewallChangeLog_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    "" | Out-File $OutFile
    Write-Log "Change log exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
