<#
.SYNOPSIS
    Remove all VM snapshots older than X days.

.DESCRIPTION
    Prompts for age threshold (in days). Removes all snapshots older than this for every VM.
    Logs all steps and outputs removal actions.

.NOTES
    PowerCLI >=13.0 required.
    Use with caution in production.
#>

$vcServer    = Read-Host "Enter vCenter FQDN or IP"
$vcUser      = Read-Host "Enter vCenter username"
$vcPass      = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Remove-OldSnapshots.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting old snapshot removal..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $Days = Read-Host "Remove snapshots older than how many days?"
    $cutoff = (Get-Date).AddDays(-[int]$Days)
    $snaps = Get-VM | Get-Snapshot | Where-Object { $_.Created -lt $cutoff }

    foreach ($snap in $snaps) {
        Write-Log "Removing snapshot $($snap.Name) from VM $($snap.VM.Name) created $($snap.Created)"
        Remove-Snapshot -Snapshot $snap -Confirm:$false
    }
    Write-Log "Removed $($snaps.Count) snapshots older than $Days days."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed old snapshot removal."
