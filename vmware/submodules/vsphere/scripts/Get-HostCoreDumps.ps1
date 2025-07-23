<#
.SYNOPSIS
    Report on ESXi host core dump configuration and status.

.DESCRIPTION
    Prompts for host name (blank for all), checks and reports core dump status.
    Exports to CSV and logs results.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostCoreDumps.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Reporting host core dumps..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hostName = Read-Host "Enter host name (leave blank for all)"
    if ($hostName) { $hosts = @(Get-VMHost -Name $hostName -ErrorAction Stop) }
    else           { $hosts = Get-VMHost }
    $report = foreach ($host in $hosts) {
        $coreDump = Get-EsxCli -VMHost $host | % { $_.system.coredump.file.get() }
        [PSCustomObject]@{
            Host        = $host.Name
            Enabled     = $coreDump.Enabled
            File        = $coreDump.File
            SizeMB      = $coreDump.Size
        }
    }
    $outfile = "HostCoreDumps_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported host core dump info to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed host core dump reporting."
