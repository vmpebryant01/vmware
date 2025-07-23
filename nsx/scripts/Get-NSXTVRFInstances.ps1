<#
.SYNOPSIS
    Lists all NSX-T VRF instances and their parent Tier-0 routers.

.DESCRIPTION
    Exports VRF name, parent, status, and interfaces for multi-tenant routing audit.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTVRFInstances.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Listing VRF instances..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    $vrfs = Get-NsxtLogicalRouter | Where-Object { $_.RouterType -eq "VRF" }
    $report = $vrfs | Select DisplayName, ParentLogicalRouterDisplayName, Status
    $OutFile = "NSXTVRFInstances_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "VRF instance report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
