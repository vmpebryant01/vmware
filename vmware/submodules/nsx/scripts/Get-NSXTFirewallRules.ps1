<#
.SYNOPSIS
    Exports all NSX-T distributed and gateway firewall rules.

.DESCRIPTION
    Lists rule name, section, source, destination, service, action, direction, logging.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTFirewallRules.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting NSX-T firewall rules..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $rules = Get-NsxtFirewallRule
    $report = $rules | Select DisplayName, SectionDisplayName, Source, Destination, Service, Action, Direction, Logging
    $OutFile = "NSXTFirewallRules_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Firewall rule report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
