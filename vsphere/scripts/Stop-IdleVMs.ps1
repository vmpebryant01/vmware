<#
.SYNOPSIS
    Shut down VMs with low CPU usage over a given period.

.DESCRIPTION
    Finds and powers off VMs with average CPU usage below a threshold for X days.
    Prompts for threshold and days. Logs actions and results.

.NOTES
    PowerCLI >=13.0 required.
    Use with caution.
#>

$vcServer    = Read-Host "Enter vCenter FQDN or IP"
$vcUser      = Read-Host "Enter vCenter username"
$vcPass      = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Stop-IdleVMs.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Stopping idle VMs..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $CPUThreshold = Read-Host "Enter CPU threshold (%) (e.g. 2)"
    $Days         = Read-Host "Evaluate for how many days?"

    $date = (Get-Date).AddDays(-[int]$Days)
    $vms  = Get-VM | Where-Object { $_.PowerState -eq "PoweredOn" }

    foreach ($vm in $vms) {
        $cpuAvg = (Get-Stat -Entity $vm -Stat cpu.usage.average -Start $date | Measure-Object Value -Average).Average
        if ($cpuAvg -lt $CPUThreshold) {
            Write-Log "Shutting down idle VM $($vm.Name), avg CPU: $([math]::Round($cpuAvg,2))"
            Stop-VM -VM $vm -Confirm:$false
        }
    }
    Write-Log "Evaluated $(($vms).Count) VMs for idleness."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed idle VM shutdown."
