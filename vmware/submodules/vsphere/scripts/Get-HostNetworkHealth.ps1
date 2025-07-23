<#
.SYNOPSIS
    Report on ESXi host network health (NIC redundancy, link status, MTU, failover).

.DESCRIPTION
    Prompts for host (blank for all), outputs key network health metrics.
    Exports to CSV and logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostNetworkHealth.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting host network health..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hostName = Read-Host "Enter host name (leave blank for all)"
    if ($hostName) { $hosts = @(Get-VMHost -Name $hostName -ErrorAction Stop) }
    else           { $hosts = Get-VMHost }
    $report = foreach ($host in $hosts) {
        $pnic = Get-VMHostNetworkAdapter -VMHost $host -Physical
        [PSCustomObject]@{
            Host        = $host.Name
            NICCount    = $pnic.Count
            DownNICs    = ($pnic | Where-Object { $_.Status -ne "Up" }).Count
            MTU         = ($pnic | Select-Object -First 1).Mtu
            vSwitches   = (Get-VirtualSwitch -VMHost $host | Select-Object -ExpandProperty Name) -join ","
        }
    }
    $outfile = "HostNetworkHealth_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported host network health to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed host network health."
