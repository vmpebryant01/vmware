<#
.SYNOPSIS
    Export all VM disk details.

.DESCRIPTION
    Lists every VM, disk name, size, SCSI controller, provisioning, and backing datastore.
    Exports to CSV and logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-VMDisks.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting VM disks export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        foreach ($hd in $vm | Get-HardDisk) {
            [PSCustomObject]@{
                VMName      = $vm.Name
                DiskName    = $hd.Name
                SizeGB      = [math]::Round($hd.CapacityGB,2)
                SCSI        = $hd.ExtensionData.ControllerKey
                Thin        = $hd.StorageFormat -eq "Thin"
                Datastore   = $hd.Filename.Split(']')[0].TrimStart('[')
            }
        }
    }
    $OutFile = "VMDisks_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VM disk details to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
