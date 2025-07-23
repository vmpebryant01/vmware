<#
.SYNOPSIS
    Report DRS (Distributed Resource Scheduler) status for all clusters.

.DESCRIPTION
    Lists each cluster, DRS status, automation level, and migration threshold.
    Output to CSV and logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-ClusterDrsStatus.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting cluster DRS status export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $clusters = Get-Cluster
    $report = foreach ($cluster in $clusters) {
        [PSCustomObject]@{
            Name                = $cluster.Name
            DrsEnabled          = $cluster.DrsEnabled
            AutomationLevel     = $cluster.DrsAutomationLevel
            MigrationThreshold  = $cluster.DrsMigrationThreshold
        }
    }
    $OutFile = "ClusterDrsStatus_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported cluster DRS status to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
