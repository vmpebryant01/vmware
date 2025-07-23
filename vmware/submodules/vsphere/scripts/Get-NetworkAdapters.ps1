<#
.SYNOPSIS
    Report on VM and host network adapters.

.DESCRIPTION
    Exports all VM network adapters, MACs, IPs, and all physical NICs for hosts.
    Output to CSV, logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-NetworkAdapters.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting network adapter export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $vmReport = foreach ($vm in $vms) {
        foreach ($nic in $vm | Get-NetworkAdapter) {
            [PSCustomObject]@{
                VMName  = $vm.Name
                Adapter = $nic.Name
                MAC     = $nic.MacAddress
                Network = $nic.NetworkName
                Type    = $nic.Type
            }
        }
    }
    $OutFile = "VMNetworkAdapters_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $vmReport | Export-Csv -NoTypeInformation -Path $OutFile

    $hosts = Get-VMHost
    $hostReport = foreach ($host in $hosts) {
        foreach ($nic in $host | Get-VMHostNetworkAdapter -Physical) {
            [PSCustomObject]@{
                HostName = $host.Name
                NIC      = $nic.Name
                MAC      = $nic.Mac
                Device   = $nic.DeviceName
                Speed    = $nic.BitRatePerSec/1MB
            }
        }
    }
    $OutFile2 = "HostPhysicalNICs_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $hostReport | Export-Csv -NoTypeInformation -Path $OutFile2

    Write-Log "Exported VM NICs to $OutFile and Host NICs to $OutFile2"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
