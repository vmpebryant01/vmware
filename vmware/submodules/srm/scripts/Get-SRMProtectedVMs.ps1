<#
.SYNOPSIS
    Lists all VMs protected by SRM.

.DESCRIPTION
    Connects to SRM and vCenter, outputs name, group, replication, and RPO.
    Logs all actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-SRMProtectedVMs.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM protected VM export..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $report = foreach ($g in $groups) {
        foreach ($vm in Get-SrmProtectedVM -ProtectionGroup $g) {
            [PSCustomObject]@{
                VMName    = $vm.Name
                Group     = $g.Name
                Replication= $vm.ReplicationType
                RPO       = $vm.RecoveryPointObjective
            }
        }
    }
    $OutFile = "SRMProtectedVMs_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported protected VMs to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed protected VM export."
