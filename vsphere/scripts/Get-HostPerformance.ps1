<#
.SYNOPSIS
    Report on ESXi host CPU, memory, and network utilization.

.DESCRIPTION
    Prompts for host name (blank for all), collects last 24h performance metrics.
    Exports to CSV and logs all actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostPerformance.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Collecting host performance..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hostName = Read-Host "Enter host name (leave blank for all)"
    if ($hostName) {
        $hosts = @(Get-VMHost -Name $hostName -ErrorAction Stop)
    } else {
        $hosts = Get-VMHost
    }
    $start = (Get-Date).AddDays(-1)
    $report = foreach ($host in $hosts) {
        $cpu = (Get-Stat -Entity $host -Stat cpu.usage.average -Start $start | Measure-Object Value -Average).Average
        $mem = (Get-Stat -Entity $host -Stat mem.usage.average -Start $start | Measure-Object Value -Average).Average
        $net = (Get-Stat -Entity $host -Stat net.usage.average -Start $start | Measure-Object Value -Average).Average
        [PSCustomObject]@{
            HostName   = $host.Name
            AvgCPU     = [math]::Round($cpu,2)
            AvgMemory  = [math]::Round($mem,2)
            AvgNetwork = [math]::Round($net,2)
        }
    }
    $outfile = "HostPerformance_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported host performance report to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed host performance monitoring."
