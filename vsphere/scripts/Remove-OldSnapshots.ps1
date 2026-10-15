<#
.SYNOPSIS
    Remove all VM snapshots older than X days.

.DESCRIPTION
    Prompts for age threshold (in days). Removes all snapshots older than this for every VM.
    Logs all steps and outputs removal actions.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
    Use with caution in production.
#>

$vcServer    = Read-Host "Enter vCenter FQDN or IP"
$vcUser      = Read-Host "Enter vCenter username"
$vcPass      = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Remove-OldSnapshots.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting old snapshot removal..."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $Days = 0
    if (-not [int]::TryParse((Read-Host "Preview snapshots older than how many days?"), [ref]$Days) -or $Days -lt 1) {
        throw "Snapshot age must be a positive whole number."
    }
    $cutoff = (Get-Date).AddDays(-$Days)
    $snaps = @(Get-VM | Get-Snapshot | Where-Object { $_.Created -lt $cutoff })
    $snaps | Select-Object @{Name='VM';Expression={$_.VM.Name}}, Name, Created | Format-Table -AutoSize
    Write-Log "Found $($snaps.Count) candidate snapshots older than $Days days."
    if ($snaps.Count -eq 0) { return }

    $approval = Read-Host "Type DELETE to remove these $($snaps.Count) snapshots"
    if ($approval -cne 'DELETE') {
        Write-Log "Snapshot removal cancelled after preview."
        return
    }

    foreach ($snap in $snaps) {
        Write-Log "Removing snapshot $($snap.Name) from VM $($snap.VM.Name) created $($snap.Created)"
        Remove-Snapshot -Snapshot $snap -Confirm:$false -ErrorAction Stop
    }
    Write-Log "Removed $($snaps.Count) snapshots older than $Days days."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed old snapshot removal."
