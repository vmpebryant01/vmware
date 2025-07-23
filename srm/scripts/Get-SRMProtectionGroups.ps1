<#
.SYNOPSIS
    Lists all SRM Protection Groups.

.DESCRIPTION
    Connects to SRM and vCenter, exports name, type, and VM count for each group.
    Logs all actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-SRMProtectionGroups.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM protection group export..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $report = foreach ($g in $groups) {
        $vms = Get-SrmProtectedVM -ProtectionGroup $g
        [PSCustomObject]@{
            Name    = $g.Name
            Type    = $g.ProtectionType
            VMCount = $vms.Count
        }
    }
    $OutFile = "SRMProtectionGroups_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported protection groups to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed protection group export."
