<#
.SYNOPSIS
    Report on VMs without recent backups (based on tag or notes search).

.DESCRIPTION
    Lists all VMs that are missing a 'Backup' tag or do not mention backup status in Notes.
    Output to CSV and logs all steps.

.NOTES
    PowerCLI >=13.0 required.
    Adjust $BackupTagCategory/$BackupTagValue as needed.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$BackupTagCategory = "Protection"
$BackupTagValue    = "BackedUp"

$LogPath = "Get-VMsNoBackups.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting VMs no backups report."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $tags = (Get-TagAssignment -Entity $vm | Where-Object {$_.Tag.Category -eq $BackupTagCategory}).Tag.Name
        $hasBackup = $tags -contains $BackupTagValue -or $vm.Notes -match "backup"
        if (-not $hasBackup) {
            [PSCustomObject]@{
                Name         = $vm.Name
                PowerState   = $vm.PowerState
                Notes        = $vm.Notes
                Tags         = $tags -join ","
            }
        }
    }
    $OutFile = "VMsNoBackups_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VMs with no backups report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
