<#
.SYNOPSIS
    Move a VM to a specific resource pool.

.DESCRIPTION
    Prompts for VM name and resource pool. Moves VM and logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer   = Read-Host "Enter vCenter FQDN or IP"
$vcUser     = Read-Host "Enter vCenter username"
$vcPass     = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Move-VMToResourcePool.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Moving VM to resource pool..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $PoolName = Read-Host "Enter resource pool name"

    $vm = Get-VM -Name $VMName -ErrorAction Stop
    $pool = Get-ResourcePool -Name $PoolName -ErrorAction Stop

    Move-VM -VM $vm -Destination $pool -Confirm:$false
    Write-Log "Moved VM $VMName to pool $PoolName"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed VM move."
