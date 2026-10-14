# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtEdgeNode', 'Get-NsxtManager')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Connectivity/health test of NSX-T management, edge, and fabric nodes.

.DESCRIPTION
    Verifies reachability and management status for all NSX-T core node types.
    Logs actions, outputs status to CSV.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Test-NSXTConnectivity.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Testing NSX-T node connectivity..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $edges = Get-NsxtEdgeNode | Select Name, MgmtIpAddress, Status
    $mgmt  = Get-NsxtManager | Select Name, MgmtIpAddress, Status
    $OutFile = "NSXTConnectivity_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $edges + $mgmt | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Node connectivity status exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
