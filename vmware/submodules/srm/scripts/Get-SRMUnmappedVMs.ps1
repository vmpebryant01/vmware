<#
.SYNOPSIS
    Reports VMs in protection groups that are missing required recovery mappings.

.DESCRIPTION
    Lists VMs with incomplete or invalid mappings (networks, folders, datastores).
    Outputs to CSV for remediation.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$LogPath = "Get-SRMUnmappedVMs.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Scanning for unmapped SRM VMs..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $rows = @()
    foreach ($g in $groups) {
        foreach ($vm in Get-SrmProtectedVM -ProtectionGroup $g) {
            $mapping = $vm.MappingStatus
            if ($mapping -ne "Valid") {
                $rows += [PSCustomObject]@{VM=$vm.Name; Group=$g.Name; MappingStatus=$mapping}
            }
        }
    }
    $OutFile = "SRMUnmappedVMs_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $rows | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Unmapped VMs exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Confirm:$false; Write-Log "Disconnected." }
