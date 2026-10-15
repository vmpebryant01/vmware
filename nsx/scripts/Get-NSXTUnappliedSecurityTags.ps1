# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtTag', 'Get-NsxtTagAssignment')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Finds NSX-T Security Tags not applied to any objects.

.DESCRIPTION
    Flags unused tags for cleanup and reports all untagged inventory objects.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTUnappliedSecurityTags.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Scanning for unused security tags..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    $tags = Get-NsxtTag
    $unused = foreach ($tag in $tags) {
        $entities = $tag | Get-NsxtTagAssignment
        if ($entities.Count -eq 0) { $tag }
    }
    $OutFile = "NSXTUnappliedSecurityTags_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $unused | Select DisplayName, Id | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Unused tag report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
