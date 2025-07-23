<#
.SYNOPSIS
    Lists all NSX-T Edge Nodes and their status.

.DESCRIPTION
    Connects to NSX Manager, exports node name, IP, status, role, and capacity.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
    Requires VMware.VimAutomation.Nsx.T module.
#>

$nsxServer = Read-Host "Enter NSX Manager FQDN/IP"
$nsxUser   = Read-Host "Enter NSX username"
$nsxPass   = Read-Host "Enter NSX password" -AsSecureString

$LogPath = "Get-NSXTEdgeNodes.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting NSX-T Edge Node inventory..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected to NSX-T"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $edges = Get-NsxtEdgeNode
    $report = $edges | Select Name, NodeId, Status, MgmtIpAddress, FormFactor, DeploymentType
    $OutFile = "NSXTEdgeNodes_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Edge node report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed NSX-T edge node export."
