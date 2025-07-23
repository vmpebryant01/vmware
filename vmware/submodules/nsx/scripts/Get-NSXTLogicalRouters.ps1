<#
.SYNOPSIS
    Exports all Tier-0 and Tier-1 routers.

.DESCRIPTION
    Lists router name, type, HA mode, status, and edge cluster.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTLogicalRouters.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting NSX-T logical routers..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $routers = Get-NsxtLogicalRouter
    $report = $routers | Select DisplayName, RouterType, HighAvailabilityMode, Status, EdgeClusterDisplayName
    $OutFile = "NSXTLogicalRouters_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Logical router report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
