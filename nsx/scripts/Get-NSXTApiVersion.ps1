<#
.SYNOPSIS
    Displays the NSX-T API/manager version for compliance.

.DESCRIPTION
    Outputs version and build info for the connected NSX-T Manager.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTApiVersion.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Fetching NSX-T version info..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $version = Get-NsxtService -Name "NsxComponent" | Select -ExpandProperty Version
    Write-Host "NSX-T Version: $version"
    Write-Log "NSX-T version: $version"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
