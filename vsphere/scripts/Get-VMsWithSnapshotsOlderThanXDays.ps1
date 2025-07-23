<#
.SYNOPSIS
    Report all VMs with snapshots older than X days.

.DESCRIPTION
    Prompts for day threshold, outputs all snapshots older than X days with VM, name, created, and size.
    Logs all actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-VMsWithSnapshotsOlderThanXDays.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Finding VMs with old snapshots..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $days = Read-Host "Enter max age (days)"
    $snaps = Get-VM | Get-Snapshot | Where-Object { $_.Created -lt (Get-Date).AddDays(-[int]$days) }
    $report = foreach ($snap in $snaps) {
        [PSCustomObject]@{
            VMName   = $snap.VM.Name
            Snapshot = $snap.Name
            Created  = $snap.Created
            AgeDays  = [math]::Round((New-TimeSpan -Start $snap.Created -End (Get-Date)).TotalDays,1)
            SizeGB   = [math]::Round($snap.SizeMB/1024,2)
        }
    }
    $OutFile = "OldSnapshots_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported old snapshot report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed old snapshot report."
