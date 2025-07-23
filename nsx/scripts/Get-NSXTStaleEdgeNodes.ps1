<#
.SYNOPSIS
    Finds NSX-T Edge Nodes not assigned to any Edge Cluster.

.DESCRIPTION
    Reports on orphaned Edge Nodes for cleanup or troubleshooting.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTStaleEdgeNodes.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking for stale NSX-T Edge Nodes..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    $edges = Get-NsxtEdgeNode
    $stale = foreach ($e in $edges) {
        if (-not $e.EdgeClusterDisplayName) { $e }
    }
    $OutFile = "NSXTStaleEdgeNodes_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $stale | Select DisplayName, MgmtIpAddress, NodeId | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Stale edge node report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
