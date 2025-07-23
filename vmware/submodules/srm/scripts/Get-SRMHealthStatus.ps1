<#
.SYNOPSIS
    Checks SRM and connection health, logging any recent errors.

.DESCRIPTION
    Tests connection to SRM/vCenter, lists recent error events, and logs the results.

.NOTES
    PowerCLI >=13.0 required.
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
