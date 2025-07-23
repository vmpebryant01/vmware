<#
.SYNOPSIS
    Integrates SRM events or alerts with ServiceNow via REST API.

.DESCRIPTION
    On new critical SRM event, creates a ServiceNow incident.
    Requires REST endpoint and credentials.

.NOTES
    PowerCLI >=13.0 required.
    Requires ServiceNow REST API configuration.
#>

# User must fill out their SNOW REST endpoint/creds here:
$SNOWURL = "https://yourservicenow/instance/api/now/table/incident"
$SNOWUser = "admin"
$SNOWPass = "password"

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Send-SRMEventToServiceNow.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "SRM ServiceNow integration..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
} catch { Write-Log "ERROR: $_"; throw }

try {
    $since = (Get-Date).AddMinutes(-10)
    $events = Get-SrmEvent | Where-Object { $_.CreatedTime -gt $since -and $_.Severity -eq "Error" }
    foreach ($ev in $events) {
        $body = @{
            short_description = "SRM Alert: $($ev.EventType)"
            description = $ev.Message
            urgency = "2"
            impact  = "2"
        }
        $result = Invoke-RestMethod -Uri $SNOWURL -Method Post -Body ($body | ConvertTo-Json) -Credential (New-Object System.Management.Automation.PSCredential($SNOWUser, (ConvertTo-SecureString $SNOWPass -AsPlainText -Force))) -ContentType "application/json"
        Write-Log "Sent SRM event to SNOW: $($ev.EventType) - $($ev.Message)"
    }
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed ServiceNow integration."
