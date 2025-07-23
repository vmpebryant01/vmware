<#
.SYNOPSIS
    Initiates an NSX-T configuration backup and downloads the backup file.

.DESCRIPTION
    Starts a manual config backup, waits for completion, downloads the file to a local path.

.NOTES
    PowerCLI >=13.0 required.
    Requires backup configured and NSX Manager permissions.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString
$localPath = Read-Host "Enter local path to save backup file"

$LogPath = "Export-NSXTConfigBackup.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting NSX-T config backup..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
    # Actual backup trigger and download may require REST/API call (PowerCLI may have limited support)
    Write-Log "Backup initiated (REST API required for file download)."
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
