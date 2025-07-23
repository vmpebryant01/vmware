<#
.SYNOPSIS
    Generates a summary inventory of all clusters in the vCenter.

.DESCRIPTION
    Collects name, number of hosts, total CPUs, and total memory for every cluster.
    Exports report to CSV and logs all operations.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-ClusterInventory.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting cluster inventory."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $clusters = Get-Cluster
    $report = foreach ($cluster in $clusters) {
        [PSCustomObject]@{
            Name         = $cluster.Name
            HostCount    = ($cluster | Get-VMHost).Count
            TotalCPU     = [math]::Round($cluster.CpuTotalMhz/1000,2)
            TotalMemoryGB= [math]::Round($cluster.MemoryTotalGB,2)
        }
    }
    $OutFile = "ClusterInventory_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported cluster inventory to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
