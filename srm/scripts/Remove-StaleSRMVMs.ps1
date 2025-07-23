<#
.SYNOPSIS
    Identifies and removes stale or orphaned VMs from SRM protection groups.

.DESCRIPTION
    Scans protection groups for VMs that are missing in vCenter or marked orphaned.
    Prompts before removal. Logs actions.

.NOTES
    PowerCLI >=13.0 required.
    Use with caution.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Remove-StaleSRMVMs.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting stale SRM VM cleanup..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    foreach ($g in $groups) {
        foreach ($vm in Get-SrmProtectedVM -ProtectionGroup $g) {
            if ($vm.PowerState -eq "Orphaned" -or $null -eq (Get-VM -Name $vm.Name -ErrorAction SilentlyContinue)) {
                Write-Log "Stale/orphaned VM detected: $($vm.Name) in group $($g.Name)"
                $resp = Read-Host "Remove $($vm.Name) from SRM? (Y/N)"
                if ($resp -eq "Y") {
                    Remove-SrmProtectedVM -ProtectedVM $vm -Confirm:$false
                    Write-Log "Removed $($vm.Name) from group $($g.Name)"
                }
            }
        }
    }
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed stale VM cleanup."
