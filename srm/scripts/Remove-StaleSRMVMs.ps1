# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmProtectedVM', 'Get-SrmProtectionGroup', 'Remove-SrmProtectedVM')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Identifies and removes stale or orphaned VMs from SRM protection groups.

.DESCRIPTION
    Scans protection groups for VMs that are missing in vCenter or marked orphaned.
    Prompts before removal. Logs actions.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
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
