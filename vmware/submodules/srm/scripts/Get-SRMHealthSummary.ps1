<#
.SYNOPSIS
    Daily health summary for SRM: plans, groups, mappings, errors.

.DESCRIPTION
    Exports summary stats and writes a plain text status report.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$LogPath = "Get-SRMHealthSummary.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Gathering SRM health summary..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $plans = Get-SrmRecoveryPlan
    $groups = Get-SrmProtectionGroup
    $mappings = $groups | Get-SrmProtectionGroupMapping
    $alerts = Get-SrmEvent | Where-Object { $_.Severity -eq "Error" -and $_.CreatedTime -gt (Get-Date).AddDays(-1) }
    $summary = @"
SRM Health Summary $(Get-Date)
Plans: $($plans.Count)
Groups: $($groups.Count)
Mappings: $($mappings.Count)
Errors past 24h: $($alerts.Count)
"@
    $OutFile = "SRMHealthSummary_$(Get-Date -Format yyyyMMdd_HHmmss).txt"
    $summary | Out-File $OutFile
    Write-Log "Health summary exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Confirm:$false; Write-Log "Disconnected." }
