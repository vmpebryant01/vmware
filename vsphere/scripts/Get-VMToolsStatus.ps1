<#
.SYNOPSIS
    Report on VMware Tools status for all VMs.

.DESCRIPTION
    Exports all VMs with their VMware Tools version, status, upgrade policy, and power state.
    Logs all steps, outputs to CSV.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-VMToolsStatus.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting VMTools status report."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $tools = $vm.ExtensionData.Guest.ToolsVersion
        $toolsStatus = $vm.ExtensionData.Guest.ToolsStatus
        $upgradePolicy = $vm.ExtensionData.Config.Tools.ToolsUpgradePolicy
        [PSCustomObject]@{
            Name           = $vm.Name
            ToolsVersion   = $tools
            ToolsStatus    = $toolsStatus
            UpgradePolicy  = $upgradePolicy
            PowerState     = $vm.PowerState
        }
    }
    $OutFile = "VMToolsStatus_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VMware Tools report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
