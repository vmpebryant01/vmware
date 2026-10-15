# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmEvent')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Reports configuration drift events in SRM objects over the past week.

.DESCRIPTION
    Exports all events with type "ConfigDrift" or similar in the last 7 days.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
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
