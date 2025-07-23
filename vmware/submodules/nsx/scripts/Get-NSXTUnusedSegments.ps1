<#
.SYNOPSIS
    Reports on unused or orphaned NSX-T segments (no attached VMs).

.DESCRIPTION
    Lists segments with zero VM attachments for cleanup/review.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTUnusedSegments.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Finding unused NSX-T segments..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
    $segs = Get-NsxtSegment
    $unused = foreach ($seg in $segs) {
        $members = $seg | Get-NsxtSegmentVnic
        if (!$members -or $members.Count -eq 0) { $seg }
    }
    $OutFile = "NSXTUnusedSegments_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $unused | Select DisplayName, VlanIds, TransportZoneDisplayName | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Unused segments exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
