<#
.SYNOPSIS
    List all VMs with ISO files mounted.

.DESCRIPTION
    Exports VMs, ISO path, status. Flags non-compliant VMs.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Find-VMsWithISOAttached.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking VMs with ISOs attached..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $report = foreach ($vm in Get-VM) {
        foreach ($cd in $vm | Get-CDDrive | Where-Object { $_.IsoPath }) {
            [PSCustomObject]@{
                VMName = $vm.Name
                ISO    = $cd.IsoPath
                Connected = $cd.Connected
            }
        }
    }
    $OutFile = "VMsWithISOs_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported ISO usage to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed ISO audit."
