<#
.SYNOPSIS
    Report on hardware health status for all ESXi hosts.

.DESCRIPTION
    Collects system health, fan, temperature, and power supply status for each host.
    Output to CSV and logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostHardwareStatus.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting host hardware health export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hosts = Get-VMHost
    $report = foreach ($host in $hosts) {
        $status = Get-VMHostHardwareStatus -VMHost $host
        [PSCustomObject]@{
            Host        = $host.Name
            Overall     = $status.OverallStatus
            Fans        = ($status.FanStatus | ForEach-Object { $_.Status }) -join ","
            PowerSupply = ($status.PowerSupplyStatus | ForEach-Object { $_.Status }) -join ","
            TempSensor  = ($status.TemperatureStatus | ForEach-Object { $_.Status }) -join ","
        }
    }
    $OutFile = "HostHardwareStatus_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported host hardware status to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
