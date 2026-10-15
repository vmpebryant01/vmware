<#
.SYNOPSIS
    Report on snapshots older than a threshold (default 7 days).

.DESCRIPTION
    Exports all VM snapshots older than $MaxAgeDays days, with name, age, and size.
    Output to CSV and logs all steps.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
    Adjust $MaxAgeDays as needed.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$MaxAgeDays = 7

$LogPath = "Get-ExpiredSnapshots.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting expired snapshot report."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $snapshots = Get-VM | Get-Snapshot | Where-Object { $_.Created -lt (Get-Date).AddDays(-$MaxAgeDays) }
    $report = foreach ($snap in $snapshots) {
        [PSCustomObject]@{
            VMName     = $snap.VM.Name
            Snapshot   = $snap.Name
            Created    = $snap.Created
            AgeDays    = [math]::Round((New-TimeSpan -Start $snap.Created -End (Get-Date)).TotalDays,1)
            SizeGB     = [math]::Round($snap.SizeMB/1024,2)
            Description= $snap.Description
        }
    }
    $OutFile = "ExpiredSnapshots_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported expired snapshot report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
