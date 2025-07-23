<#
.SYNOPSIS
    Reports NSX-T DFW shadow rules and rule shadowing relationships.

.DESCRIPTION
    Exports shadowed rules, their shadowing rules, and affected sections for troubleshooting.
    Useful for cleaning up ineffective/overridden rules.

.NOTES
    PowerCLI >=13.0 required.
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
