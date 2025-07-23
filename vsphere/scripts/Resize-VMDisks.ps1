<#
.SYNOPSIS
    Resize one or more virtual disks on a VM.

.DESCRIPTION
    Prompts for VM name, new disk size (GB), and which disk to resize.
    Increases disk size and logs results.

.NOTES
    PowerCLI >=13.0 required.
    VM must be powered off.
#>

$vcServer   = Read-Host "Enter vCenter FQDN or IP"
$vcUser     = Read-Host "Enter vCenter username"
$vcPass     = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Resize-VMDisks.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Resizing VM disks..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $NewSize = Read-Host "Enter new disk size (GB)"
    $DiskNum = Read-Host "Enter disk number (0 for all disks, or specify index)"

    $vm = Get-VM -Name $VMName -ErrorAction Stop
    $disks = $vm | Get-HardDisk

    if ($DiskNum -eq "0") {
        foreach ($hd in $disks) {
            Set-HardDisk -HardDisk $hd -CapacityGB $NewSize -Confirm:$false
            Write-Log "Resized disk $($hd.Name) to $NewSize GB on $VMName"
        }
    } else {
        $hd = $disks[[int]$DiskNum-1]
        Set-HardDisk -HardDisk $hd -CapacityGB $NewSize -Confirm:$false
        Write-Log "Resized disk $($hd.Name) to $NewSize GB on $VMName"
    }
    Write-Log "Disk resize complete."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed disk resize."
