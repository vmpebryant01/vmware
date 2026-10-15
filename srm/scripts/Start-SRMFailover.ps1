# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmRecoveryPlan', 'Invoke-SrmRecoveryPlan')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Initiates a real failover for a specified SRM Recovery Plan.

.DESCRIPTION
    Prompts for plan name, runs actual failover, logs and tracks the outcome.
    Alerts on errors.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
    WARNING: This script will initiate a DR failover!
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Start-SRMFailover.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM failover..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $planName = Read-Host "Enter SRM Recovery Plan name"
    $plan = Get-SrmRecoveryPlan -Name $planName
    if (!$plan) { Write-Log "ERROR: Plan not found."; throw "Plan not found." }
    Invoke-SrmRecoveryPlan -RecoveryPlan $plan
    Write-Log "Failover initiated for $planName"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed failover initiation."
