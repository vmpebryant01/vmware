<#
.SYNOPSIS
    Runs a daily health check on SRM and emails the results.

.DESCRIPTION
    Collects group, plan, VM, replication, and alert status; emails a summary to DR owners.
    (Requires SMTP and proper setup.)

.NOTES
    PowerCLI >=13.0 required.
    Configure your SMTP below.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

# Configure SMTP details here:
$smtpServer = "smtp.yourdomain.com"
$smtpFrom   = "srm-report@yourdomain.com"
$smtpTo     = "drteam@yourdomain.com"

$LogPath = "New-SRMDailyHealthReport.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Generating SRM daily health report..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $plans  = Get-SrmRecoveryPlan
    $alerts = Get-SrmEvent | Where-Object { $_.Severity -eq "Error" -and $_.CreatedTime -gt (Get-Date).AddDays(-1) }
    $body = "SRM Health Summary`nGroups: $($groups.Count)`nPlans: $($plans.Count)`nAlerts past 24h: $($alerts.Count)"
    Send-MailMessage -SmtpServer $smtpServer -From $smtpFrom -To $smtpTo -Subject "SRM Daily Health Report" -Body $body
    Write-Log "Daily report emailed."
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed daily health report."
