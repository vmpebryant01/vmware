# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtFirewallRule')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Reports NSX-T DFW shadow rules and rule shadowing relationships.

.DESCRIPTION
    Exports shadowed rules, their shadowing rules, and affected sections for troubleshooting.
    Useful for cleaning up ineffective/overridden rules.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTDFWShadowRules.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting NSX-T DFW shadow rules..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $rules = Get-NsxtFirewallRule | Where-Object { $_.ShadowingRule -ne $null }
    $report = $rules | Select DisplayName, SectionDisplayName, ShadowingRule
    $OutFile = "NSXTDFWShadowRules_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "DFW shadow rule report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
