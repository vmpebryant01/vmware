<#
.SYNOPSIS
    Orchestrates multi-wave failover for SRM Recovery Plans from a CSV.

.DESCRIPTION
    Reads a CSV "Wave,PlanName" and prompts approval before each wave.
    Executes failover for each plan per wave, logs every action.

.NOTES
    PowerCLI >=13.0 required.
    CSV example:
    Wave,PlanName
    1,FinanceRP
    2,DBRP
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString
$csvFile  = Read-Host "Enter path to failover wave CSV"

$LogPath = "Start-SRMMultiWaveFailover.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting multi-wave SRM failover..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $waves = Import-Csv $csvFile | Sort-Object Wave
    $uniqueWaves = $waves | Select-Object -ExpandProperty Wave -Unique
    foreach ($w in $uniqueWaves) {
        $plans = $waves | Where-Object { $_.Wave -eq $w } | Select-Object -ExpandProperty PlanName
        Write-Host "Wave $w plans: $($plans -join ', ')"
        $go = Read-Host "Type 'yes' to approve and start wave $w"
        if ($go -eq "yes") {
            foreach ($planName in $plans) {
                $plan = Get-SrmRecoveryPlan -Name $planName
                if ($plan) {
                    Invoke-SrmRecoveryPlan -RecoveryPlan $plan
                    Write-Log "Failover started for plan $planName (wave $w)"
                }
            }
        }
    }
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed multi-wave failover."
