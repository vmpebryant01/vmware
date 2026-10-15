# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmEvent')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Checks SRM and connection health, logging any recent errors.

.DESCRIPTION
    Tests connection to SRM/vCenter, lists recent error events, and logs the results.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-SRMHealthStatus.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking SRM health..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $errors = Get-SrmEvent | Where-Object { $_.EventType -match "Error" -or $_.Severity -eq "Error" }
    $OutFile = "SRMHealthStatus_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $errors | Select CreatedTime, EventType, Message | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported recent errors to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed SRM health check."
