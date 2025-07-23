<#
.SYNOPSIS
    Requests approval via email before running any SRM Recovery Plan.

.DESCRIPTION
    Emails DR team for approval; executes plan only after approval received.

.NOTES
    PowerCLI >=13.0 required.
    Configure SMTP below.
#>
$smtpServer = "smtp.yourdomain.com"
$smtpFrom   = "srm-approval@yourdomain.com"
$smtpTo     = "dr-leads@yourdomain.com"

$vcServer = Read-Host "vCenter FQDN/IP"
$vcUser   = Read-Host "vCenter username"
$vcPass   = Read-Host "vCenter password" -AsSecureString

$planName = Read-Host "Enter Recovery Plan to run"

Send-MailMessage -SmtpServer $smtpServer -From $smtpFrom -To $smtpTo -Subject "SRM Recovery Plan Approval Required" -Body "Please approve running plan: $planName"

$go = Read-Host "Type 'approve' after you receive sign-off"
if ($go -eq "approve") {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm
    $plan = Get-SrmRecoveryPlan -Name $planName
    Invoke-SrmRecoveryPlan -RecoveryPlan $plan
    Disconnect-VIServer -Confirm:$false
}
