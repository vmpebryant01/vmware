<#
.SYNOPSIS
    Export user session history and login attempts from vCenter.

.DESCRIPTION
    Collects successful logins, failed attempts, and session durations for auditing.
    Logs and outputs to CSV.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Audit-UserSessionHistory.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting user session history..."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $since = (Get-Date).AddDays(-30)
    $events = Get-VIEvent -Start $since | Where-Object { $_.GetType().Name -like "*Session*" }
    $report = foreach ($evt in $events) {
        [PSCustomObject]@{
            Time      = $evt.CreatedTime
            User      = $evt.UserName
            Type      = $evt.GetType().Name
            Message   = $evt.FullFormattedMessage
        }
    }
    $OutFile = "UserSessionHistory_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported user session report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed user session export."
