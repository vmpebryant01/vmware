<#
.SYNOPSIS
    Comprehensive NSX-T inventory report.

.DESCRIPTION
    Exports all segments, routers, edge nodes, groups, and firewall rules.
    Consolidates into a single CSV per object type.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTInventory.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting comprehensive NSX-T inventory..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    Get-NsxtSegment         | Export-Csv -NoTypeInformation -Path "NSXT_Segments.csv"
    Get-NsxtLogicalRouter   | Export-Csv -NoTypeInformation -Path "NSXT_Routers.csv"
    Get-NsxtEdgeNode        | Export-Csv -NoTypeInformation -Path "NSXT_EdgeNodes.csv"
    Get-NsxtGroup           | Export-Csv -NoTypeInformation -Path "NSXT_Groups.csv"
    Get-NsxtFirewallRule    | Export-Csv -NoTypeInformation -Path "NSXT_FirewallRules.csv"
    Write-Log "Inventory exports completed."
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
