# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmRecoveryPlan', 'Invoke-SrmTestRecoveryPlan')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Runs a test recovery on a specified SRM Recovery Plan.

.DESCRIPTION
    Prompts for plan name, runs test recovery, logs and tracks the outcome.
    Alerts on errors.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Invoke-SRMTestRecoveryPlan.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM test recovery..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $planName = Read-Host "Enter SRM Recovery Plan name"
    $plan = Get-SrmRecoveryPlan -Name $planName
    if (!$plan) { Write-Log "ERROR: Plan not found."; throw "Plan not found." }
    Invoke-SrmTestRecoveryPlan -RecoveryPlan $plan
    Write-Log "Test recovery initiated for $planName"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed test recovery initiation."
