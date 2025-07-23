<#
.SYNOPSIS
    Export a full inventory and configuration report of all VMs in vCenter.

.DESCRIPTION
    Connects securely to vCenter, retrieves all VMs and key attributes, and exports them to CSV.
    Logs all actions and errors for auditing.

.NOTES
    PowerCLI >=13.0 required.
    Author: VMware Automation Team
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-AllVMInfo.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting VM inventory for $vcServer"

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: Could not connect to vCenter: $_"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $guest = $vm | Get-VMGuest
        [PSCustomObject]@{
            Name         = $vm.Name
            PowerState   = $vm.PowerState
            GuestOS      = $vm.Guest.OSFullName
            IP           = $guest.IPAddress -join ","
            Host         = $vm.VMHost
            Datastore    = $vm.Datastore -join ","
            ToolsStatus  = $vm.ExtensionData.Guest.ToolsStatus
            Notes        = $vm.Notes
        }
    }
    $OutFile = "AllVMs_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VM report to $OutFile"
} catch { Write-Log "ERROR: Failed exporting VM info: $_"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected from $vcServer" }
Write-Log "Completed inventory."
