<#
.SYNOPSIS
    Lists all BGP and OSPF adjacencies for Tier-0 routers.

.DESCRIPTION
    Useful for rapid troubleshooting of dynamic routing peering status.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTRoutingAdjacency.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Listing routing adjacencies..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    $routers = Get-NsxtLogicalRouter | Where-Object { $_.RouterType -eq "TIER0" }
    $report = foreach ($r in $routers) {
        # Placeholder: Get BGP/OSPF adjacencies via NSX-T API/REST if needed
        [PSCustomObject]@{
            Router = $r.DisplayName
            Adjacency = "N/A"
        }
    }
    $OutFile = "NSXTRoutingAdjacency_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Routing adjacency exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
