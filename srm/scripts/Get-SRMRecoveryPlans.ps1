# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmRecoveryPlan', 'Get-SrmRecoveryPlanStep')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Lists all SRM Recovery Plans.

.DESCRIPTION
    Connects to SRM, exports name, state, and number of steps for each plan.
    Logs all actions.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-SRMRecoveryPlans.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM recovery plan export..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $plans = Get-SrmRecoveryPlan
    $report = foreach ($p in $plans) {
        [PSCustomObject]@{
            Name     = $p.Name
            State    = $p.State
            StepCount= ($p | Get-SrmRecoveryPlanStep).Count
        }
    }
    $OutFile = "SRMRecoveryPlans_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported recovery plans to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed recovery plan export."
