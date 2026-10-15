# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtEdgeNode', 'Get-NsxtFirewallRule', 'Get-NsxtGroup', 'Get-NsxtLogicalRouter', 'Get-NsxtSegment')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Example NSX-T inventory export.

.DESCRIPTION
    Intended to export segments, routers, edge nodes, groups, and firewall rules
    to separate CSV files. The required cmdlets are unavailable in the published
    module, so this example stops until an API adapter is implemented.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTInventory.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting NSX-T inventory export..."

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
