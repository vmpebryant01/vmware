<#
.SYNOPSIS
    Generate a snapshot age and size report for all VMs.

.DESCRIPTION
    Lists all snapshots, including VM name, snapshot name, created date, description, and size.
    Exports to CSV, logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-SnapshotReport.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting snapshot report export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $snapshots = Get-VM | Get-Snapshot
    $report = foreach ($snap in $snapshots) {
        [PSCustomObject]@{
            VMName     = $snap.VM.Name
            Snapshot   = $snap.Name
            Created    = $snap.Created
            SizeGB     = [math]::Round($snap.SizeMB/1024,2)
            Description= $snap.Description
        }
    }
    $OutFile = "VMSnapshotReport_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported snapshot report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
