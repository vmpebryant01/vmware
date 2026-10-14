# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmRecoveryPlan', 'Invoke-SrmTestRecoveryPlan')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Runs a scheduled test recovery for all "test-required" SRM plans.

.DESCRIPTION
    Iterates all Recovery Plans with "TestRequired" in notes/tag.
    Runs test recovery, logs actions, and records failures.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$LogPath = "Test-SRMScheduledRecoveryPlan.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Running scheduled SRM test recoveries..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $plans = Get-SrmRecoveryPlan | Where-Object { $_.Notes -match "TestRequired" }
    foreach ($plan in $plans) {
        try {
            Invoke-SrmTestRecoveryPlan -RecoveryPlan $plan
            Write-Log "Test recovery succeeded for $($plan.Name)"
        } catch {
            Write-Log "Test recovery FAILED for $($plan.Name): $_"
        }
    }
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Confirm:$false; Write-Log "Disconnected." }
