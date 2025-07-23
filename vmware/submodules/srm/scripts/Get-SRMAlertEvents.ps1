<#
.SYNOPSIS
    Exports recent SRM alert and event messages.

.DESCRIPTION
    Collects and exports recent events and warnings related to SRM.
    Logs actions for audit trail.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-SRMAlertEvents.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM alert/event export..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $since = (Get-Date).AddDays(-7)
    $events = Get-SrmEvent | Where-Object { $_.CreatedTime -gt $since }
    $OutFile = "SRMAlertEvents_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $events | Select CreatedTime, EventType, Message | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported recent SRM events to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed alert/event export."
