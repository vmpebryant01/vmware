# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtFirewallRule', 'Get-NsxtFirewallSection')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Exports a full audit of all NSX-T DFW sections and rules.

.DESCRIPTION
    Lists every DFW section, rule, enablement, logging, and action, for compliance auditing.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTDFWSectionAudit.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Auditing NSX-T DFW sections..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    $sections = Get-NsxtFirewallSection
    $rules = Get-NsxtFirewallRule
    $audit = foreach ($s in $sections) {
        foreach ($r in $rules | Where-Object { $_.SectionDisplayName -eq $s.DisplayName }) {
            [PSCustomObject]@{
                Section   = $s.DisplayName
                Rule      = $r.DisplayName
                Enabled   = $r.Enabled
                Logging   = $r.Logging
                Action    = $r.Action
                Direction = $r.Direction
            }
        }
    }
    $OutFile = "NSXTDFWSectionAudit_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $audit | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Section audit exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
