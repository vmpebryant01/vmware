# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmRecoveryPlan', 'Invoke-SrmFailback')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Initiates SRM failback for a specified plan or group.

.DESCRIPTION
    Prompts for plan/group, initiates failback, logs and audits action.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
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
