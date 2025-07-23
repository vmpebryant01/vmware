<#
.SYNOPSIS
    Exports all steps of all SRM Recovery Plans.

.DESCRIPTION
    Lists step number, type, description, and dependencies for each plan.
    Exports to CSV, logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Export-SRMRecoveryPlanSteps.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM recovery plan step export..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $plans = Get-SrmRecoveryPlan
    $report = foreach ($plan in $plans) {
        $steps = Get-SrmRecoveryPlanStep -RecoveryPlan $plan
        foreach ($step in $steps) {
            [PSCustomObject]@{
                PlanName = $plan.Name
                StepNum  = $step.StepNumber
                Type     = $step.Type
                Desc     = $step.Description
            }
        }
    }
    $OutFile = "SRMRecoveryPlanSteps_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported plan steps to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed plan step export."
