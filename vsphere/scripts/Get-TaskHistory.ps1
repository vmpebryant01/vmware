<#
.SYNOPSIS
    Export vCenter task/event history for audit.

.DESCRIPTION
    Prompts for days of history, collects recent tasks (user, entity, operation, status, time).
    Exports to CSV and logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-TaskHistory.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting vCenter task history..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $days = Read-Host "How many days of history?"
    $since = (Get-Date).AddDays(-[int]$days)
    $tasks = Get-Task | Where-Object { $_.StartTime -gt $since }
    $report = foreach ($task in $tasks) {
        [PSCustomObject]@{
            Entity   = $task.Entity.Name
            Operation= $task.Name
            Status   = $task.State
            User     = $task.User
            Start    = $task.StartTime
            End      = $task.FinishTime
        }
    }
    $outfile = "TaskHistory_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported task history to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed vCenter task history export."
