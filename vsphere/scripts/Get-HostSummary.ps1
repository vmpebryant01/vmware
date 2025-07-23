<#
.SYNOPSIS
    Export a summary of all ESXi hosts.

.DESCRIPTION
    Lists all hosts, model, CPU, memory, build, state, and connection status.
    Exports report to CSV and logs all actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostSummary.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting host summary."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hosts = Get-VMHost
    $report = foreach ($host in $hosts) {
        [PSCustomObject]@{
            Name          = $host.Name
            Manufacturer  = $host.Manufacturer
            Model         = $host.Model
            CPU           = $host.NumCpu
            MemoryGB      = [math]::Round($host.MemoryTotalGB,2)
            Build         = $host.Build
            Connection    = $host.ConnectionState
            PowerState    = $host.PowerState
        }
    }
    $OutFile = "HostSummary_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported host summary to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
