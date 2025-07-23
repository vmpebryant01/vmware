<#
.SYNOPSIS
    Set CPU limit for a VM.

.DESCRIPTION
    Prompts for VM name and CPU limit in MHz. Applies and logs change.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Set-VMCPULimit.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Setting VM CPU limit..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $CPULimit = Read-Host "Enter CPU limit (MHz, blank for unlimited)"
    $vm = Get-VM -Name $VMName -ErrorAction Stop
    if ($CPULimit) {
        $vm | Set-VMResourceConfiguration -CpuLimitMHz $CPULimit -Confirm:$false
        Write-Log "Set CPU limit $CPULimit MHz for $VMName"
    } else {
        $vm | Set-VMResourceConfiguration -CpuLimitMHz $null -Confirm:$false
        Write-Log "Removed CPU limit for $VMName"
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed VM CPU limit update."
