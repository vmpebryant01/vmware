<#
.SYNOPSIS
    Exports all NSX-T security groups and membership.

.DESCRIPTION
    Lists group name, description, dynamic criteria, and member count.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTSecurityGroups.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting NSX-T security groups..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-NsxtGroup
    $report = foreach ($g in $groups) {
        $members = $g | Get-NsxtGroupMember
        [PSCustomObject]@{
            GroupName   = $g.DisplayName
            Description = $g.Description
            Criteria    = $g.Expression
            MemberCount = $members.Count
        }
    }
    $OutFile = "NSXTSecurityGroups_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Security group report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
