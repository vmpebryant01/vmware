# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtFirewallRule')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Audits NSX-T Distributed Firewall rule hit counts and last used.

.DESCRIPTION
    Lists rule name, section, hit count, last used timestamp for all DFW rules.
    Flags unused rules for potential cleanup.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
    Some fields may require API extension or pyVmomi.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTDFWRuleUsage.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Auditing NSX-T DFW rule usage..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
} catch { Write-Log "ERROR: $_"; throw }

try {
    $rules = Get-NsxtFirewallRule
    $report = foreach ($r in $rules) {
        [PSCustomObject]@{
            Rule = $r.DisplayName
            Section = $r.SectionDisplayName
            HitCount = $r.Statistics.HitCount
            LastHit  = $r.Statistics.LastHitTimestamp
        }
    }
    $OutFile = "NSXTDFWRuleUsage_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "DFW rule usage report exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
