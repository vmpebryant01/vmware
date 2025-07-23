<#
.SYNOPSIS
    Initiates a real failover for a specified SRM Recovery Plan.

.DESCRIPTION
    Prompts for plan name, runs actual failover, logs and tracks the outcome.
    Alerts on errors.

.NOTES
    PowerCLI >=13.0 required.
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
