# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmRecoveryHistory', 'Get-SrmRecoveryPlan')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Reports planned and recent SRM failover test schedule compliance.

.DESCRIPTION
    Exports last test run, next due, and compliance for each plan.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
#>
$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$LogPath = "Get-SRMFailoverTestSchedule.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting failover test schedule..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $plans = Get-SrmRecoveryPlan
    $rows = foreach ($p in $plans) {
        $last = $p | Get-SrmRecoveryHistory | Where-Object { $_.Operation -eq "Test" } | Sort-Object EndTime -Descending | Select-Object -First 1
        $lastTest = if ($last) { $last.EndTime } else { "Never" }
        $compliance = if ($lastTest -eq "Never" -or $lastTest -lt (Get-Date).AddMonths(-3)) { "NonCompliant" } else { "Compliant" }
        [PSCustomObject]@{Plan=$p.Name; LastTest=$lastTest; Compliance=$compliance}
    }
    $OutFile = "SRMFailoverTestSchedule_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $rows | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported test schedule to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Confirm:$false; Write-Log "Disconnected." }
