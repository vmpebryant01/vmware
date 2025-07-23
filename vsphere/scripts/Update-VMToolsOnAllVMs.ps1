<#
.SYNOPSIS
    Bulk update VMware Tools on all VMs that are out-of-date.

.DESCRIPTION
    Finds all powered-on VMs with outdated Tools, updates them, logs success/failure.

.NOTES
    PowerCLI >=13.0 required.
    VM reboot may be required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Update-VMToolsOnAllVMs.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting VMTools bulk update..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM | Where-Object { $_.PowerState -eq "PoweredOn" -and $_.ExtensionData.Guest.ToolsStatus -notlike "toolsOk" }
    foreach ($vm in $vms) {
        Write-Log "Updating Tools on $($vm.Name)"
        Update-Tools -VM $vm -NoReboot:$true
    }
    Write-Log "Processed $($vms.Count) VMs for Tools update."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed Tools update."
