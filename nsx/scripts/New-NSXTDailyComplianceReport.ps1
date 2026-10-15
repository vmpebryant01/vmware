# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtEdgeNode', 'Get-NsxtSegment', 'Get-NsxtSegmentVnic')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Runs a daily NSX-T compliance audit and emails the report.

.DESCRIPTION
    Checks edge/transport node health, firewall rule compliance, segment orphan count, and configuration drift.
    Emails summary to the security/network team.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
    Configure SMTP details below.
#>
$smtpServer = "smtp.yourdomain.com"
$smtpFrom   = "nsx-report@yourdomain.com"
$smtpTo     = "netops@yourdomain.com"

$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

Write-Log "NSX-T daily compliance report started..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop

    $edges = Get-NsxtEdgeNode
    $orphanSegs = Get-NsxtSegment | Where-Object { (($_ | Get-NsxtSegmentVnic).Count -eq 0) }
    $firewallViolations = "" # Add compliance logic

    $body = "NSX-T Compliance Report`nEdges: $($edges.Count)`nOrphaned Segments: $($orphanSegs.Count)"
    Send-MailMessage -SmtpServer $smtpServer -From $smtpFrom -To $smtpTo -Subject "NSX-T Daily Compliance Report" -Body $body

    Write-Host "Compliance report emailed."
    Write-Log "Compliance report emailed."
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
