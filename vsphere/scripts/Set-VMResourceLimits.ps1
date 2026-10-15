<#
.SYNOPSIS
    Set CPU and memory resource limits for a VM.

.DESCRIPTION
    Prompts for VM name, CPU MHz, and memory MB limits. Applies limits and logs changes.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Set-VMResourceLimits.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Setting VM resource limits..."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $CPULimit = Read-Host "Enter CPU limit (MHz, blank for unlimited)"
    $MemLimit = Read-Host "Enter memory limit (MB, blank for unlimited)"

    $vm = Get-VM -Name $VMName -ErrorAction Stop

    if ($CPULimit) {
        $vm | Set-VMResourceConfiguration -CpuLimitMHz $CPULimit -Confirm:$false
        Write-Log "Set CPU limit $CPULimit MHz for $VMName"
    }
    if ($MemLimit) {
        $vm | Set-VMResourceConfiguration -MemLimitMB $MemLimit -Confirm:$false
        Write-Log "Set memory limit $MemLimit MB for $VMName"
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed resource limits update."
