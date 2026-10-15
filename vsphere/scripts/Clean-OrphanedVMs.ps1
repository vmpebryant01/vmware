<#
.SYNOPSIS
    Detect and remove orphaned VMs, templates, and objects.

.DESCRIPTION
    Finds objects with no backing files or missing hosts, prompts for confirmation before removal.
    Logs findings and actions.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Clean-OrphanedVMs.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Detecting orphaned objects..."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $orphans = Get-VM | Where-Object { $_.PowerState -eq "Orphaned" }
    foreach ($vm in $orphans) {
        Write-Log "Found orphaned VM: $($vm.Name)"
        $resp = Read-Host "Remove $($vm.Name)? (Y/N)"
        if ($resp -eq "Y") {
            Remove-VM -VM $vm -DeletePermanently -Confirm:$false
            Write-Log "Removed orphaned VM $($vm.Name)"
        }
    }
    Write-Log "Processed $($orphans.Count) orphaned VMs."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed orphaned object cleanup."
