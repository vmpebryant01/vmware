<#
.SYNOPSIS
    Collect and report VM CPU, memory, and disk performance.

.DESCRIPTION
    Prompts for VM name (blank for all), collects last 24h perf stats (CPU%, Mem%, Disk latency).
    Exports to CSV and logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Monitor-VMPerformance.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Collecting VM performance..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name (leave blank for all)"
    if ($VMName) {
        $vms = @(Get-VM -Name $VMName -ErrorAction Stop)
    } else {
        $vms = Get-VM
    }
    $start = (Get-Date).AddDays(-1)
    $report = foreach ($vm in $vms) {
        $cpuAvg = (Get-Stat -Entity $vm -Stat cpu.usage.average -Start $start | Measure-Object Value -Average).Average
        $memAvg = (Get-Stat -Entity $vm -Stat mem.usage.average -Start $start | Measure-Object Value -Average).Average
        $diskLat = (Get-Stat -Entity $vm -Stat disk.totalLatency.average -Start $start | Measure-Object Value -Average).Average
        [PSCustomObject]@{
            VMName        = $vm.Name
            AvgCPU        = [math]::Round($cpuAvg,2)
            AvgMem        = [math]::Round($memAvg,2)
            AvgDiskLatency= [math]::Round($diskLat,2)
        }
    }
    $outfile = "VMPerformance_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported VM performance report to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed VM performance monitoring."
