<#
.SYNOPSIS
    Initiates SRM failback for a specified plan or group.

.DESCRIPTION
    Prompts for plan/group, initiates failback, logs and audits action.

.NOTES
    PowerCLI >=13.0 required.
    Use with caution in production.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Invoke-SRMFailback.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM failback..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $planName = Read-Host "Enter Recovery Plan for failback"
    $plan = Get-SrmRecoveryPlan -Name $planName
    if ($plan) {
        Invoke-SrmFailback -RecoveryPlan $plan
        Write-Log "Failback initiated for $planName"
    } else {
        Write-Log "Plan not found."
    }
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed failback."
