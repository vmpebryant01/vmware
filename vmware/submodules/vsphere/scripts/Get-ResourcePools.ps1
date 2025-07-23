<#
.SYNOPSIS
    Export a report of all resource pools in vCenter.

.DESCRIPTION
    Lists resource pool name, parent, CPU/memory limits, and used capacity.
    Exports to CSV, logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-ResourcePools.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting resource pool export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $pools = Get-ResourcePool
    $report = foreach ($pool in $pools) {
        [PSCustomObject]@{
            Name        = $pool.Name
            Parent      = $pool.Parent
            CpuLimitMhz = $pool.ExtensionData.Runtime.Cpu.MaxUsage
            MemLimitMB  = $pool.ExtensionData.Runtime.Memory.MaxUsage
            CpuUsedMhz  = $pool.ExtensionData.Summary.Runtime.Cpu.OverallUsage
            MemUsedMB   = $pool.ExtensionData.Summary.Runtime.Memory.OverallUsage
        }
    }
    $OutFile = "ResourcePools_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported resource pool report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
