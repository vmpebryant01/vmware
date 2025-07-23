<#
.SYNOPSIS
    Export host firmware, BIOS, ILO/iDRAC, and driver versions.

.DESCRIPTION
    Exports firmware/driver inventory for hardware compliance.

.NOTES
    PowerCLI >=13.0 required.
    Some info may require vendor VIBs/tools.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostFirmwareVersions.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting host firmware and driver versions..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $report = foreach ($host in Get-VMHost) {
        $esxcli = Get-EsxCli -VMHost $host
        $firmware = $esxcli.hardware.platform.get()
        $bios = $esxcli.system.version.get()
        [PSCustomObject]@{
            Host        = $host.Name
            Vendor      = $firmware.Vendor
            Model       = $firmware.ProductName
            Serial      = $firmware.SerialNumber
            BIOSVersion = $bios.Version
        }
    }
    $OutFile = "HostFirmware_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported host firmware to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed firmware export."
