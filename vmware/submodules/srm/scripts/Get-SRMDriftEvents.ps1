<#
.SYNOPSIS
    Reports configuration drift events in SRM objects over the past week.

.DESCRIPTION
    Exports all events with type "ConfigDrift" or similar in the last 7 days.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$LogPath = "Get-SRMDriftEvents.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting SRM drift events..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $since = (Get-Date).AddDays(-7)
    $events = Get-SrmEvent | Where-Object { $_.CreatedTime -gt $since -and $_.EventType -match "Drift" }
    $OutFile = "SRMDriftEvents_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $events | Select CreatedTime, EventType, Message | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Drift events exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Confirm:$false; Write-Log "Disconnected." }
