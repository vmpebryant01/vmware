<#
.SYNOPSIS
    Report on datastore performance metrics (latency, IOPS, throughput).

.DESCRIPTION
    Gathers performance data for each datastore over the last 24 hours.
    Output to CSV and logs all steps.

.NOTES
    PowerCLI >=13.0 required.
    May require elevated permissions and performance data retention.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-DatastorePerformance.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting datastore performance report."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $datastores = Get-Datastore
    $report = foreach ($ds in $datastores) {
        $perf = Get-Stat -Entity $ds -Stat "datastore.totalReadLatency.latest","datastore.totalWriteLatency.latest","datastore.numberReadAveraged.latest","datastore.numberWriteAveraged.latest","datastore.read.average","datastore.write.average" -Start (Get-Date).AddDays(-1)
        $avgReadLatency = ($perf | Where-Object {$_.MetricId -eq "datastore.totalReadLatency.latest"} | Measure-Object Value -Average).Average
        $avgWriteLatency = ($perf | Where-Object {$_.MetricId -eq "datastore.totalWriteLatency.latest"} | Measure-Object Value -Average).Average
        $avgIOPS = ($perf | Where-Object {$_.MetricId -in @("datastore.numberReadAveraged.latest","datastore.numberWriteAveraged.latest")} | Measure-Object Value -Average).Average
        $avgThroughput = ($perf | Where-Object {$_.MetricId -in @("datastore.read.average","datastore.write.average")} | Measure-Object Value -Average).Average
        [PSCustomObject]@{
            Datastore      = $ds.Name
            AvgReadLatency = [math]::Round($avgReadLatency,2)
            AvgWriteLatency= [math]::Round($avgWriteLatency,2)
            AvgIOPS        = [math]::Round($avgIOPS,2)
            AvgThroughput  = [math]::Round($avgThroughput,2)
        }
    }
    $OutFile = "DatastorePerformance_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported datastore performance report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
