# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmRecoveryHistory', 'Get-SrmRecoveryPlan')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Exports recent SRM test recovery results to Excel/CSV.

.DESCRIPTION
    Pulls test runs, VMs, steps, outcomes, and durations for audit or reporting.
    Requires ImportExcel module for .xlsx output.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
    Install-Module ImportExcel if needed.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

Import-Module ImportExcel -ErrorAction SilentlyContinue

$LogPath = "Get-SRMTestResultsToExcel.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting SRM test results..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $plans = Get-SrmRecoveryPlan
    $rows = foreach ($p in $plans) {
        $runs = $p | Get-SrmRecoveryHistory | Where-Object { $_.Operation -eq "Test" }
        foreach ($run in $runs) {
            [PSCustomObject]@{
                Plan = $p.Name
                RunEnd = $run.EndTime
                Status = $run.Result
                DurationMin = [math]::Round((($run.EndTime - $run.StartTime).TotalMinutes),2)
            }
        }
    }
    $OutFile = "SRMTestResults_$(Get-Date -Format yyyyMMdd_HHmmss).xlsx"
    $rows | Export-Excel -Path $OutFile -AutoSize
    Write-Log "Exported test results to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed test results export."
