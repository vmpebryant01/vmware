<#
.SYNOPSIS
    Detect hosts or clusters nearing CPU or memory overcommitment.

.DESCRIPTION
    Flags hosts/clusters at or above defined commit ratio thresholds.
    Logs and exports to CSV.

.NOTES
    PowerCLI >=13.0 required.
    Adjust $cpuLimit and $memLimit as needed.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$cpuLimit = 6
$memLimit = 1.5

$LogPath = "Monitor-HostOvercommitment.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking for host/cluster overcommitment..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $report = foreach ($host in Get-VMHost) {
        $cpuCommit = ($host | Get-VM | Measure-Object -Property NumCpu -Sum).Sum / $host.NumCpu
        $memCommit = ($host | Get-VM | Measure-Object -Property MemoryGB -Sum).Sum / $host.MemoryTotalGB
        [PSCustomObject]@{
            Host       = $host.Name
            CPUCommit  = [math]::Round($cpuCommit,2)
            MemCommit  = [math]::Round($memCommit,2)
            CPUOver    = $cpuCommit -ge $cpuLimit
            MemOver    = $memCommit -ge $memLimit
        }
    }
    $OutFile = "HostOvercommitment_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported host overcommitment report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed overcommitment check."
