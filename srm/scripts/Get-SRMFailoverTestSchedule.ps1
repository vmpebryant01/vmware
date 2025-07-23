<#
.SYNOPSIS
    Reports planned and recent SRM failover test schedule compliance.

.DESCRIPTION
    Exports last test run, next due, and compliance for each plan.

.NOTES
    PowerCLI >=13.0 required.
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
