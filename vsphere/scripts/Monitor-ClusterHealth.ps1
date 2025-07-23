<#
.SYNOPSIS
    Monitor cluster health (HA, DRS, vSAN, alarms).

.DESCRIPTION
    Prompts for cluster (blank for all), outputs summary health and recent triggered alarms.
    Exports to CSV and logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Monitor-ClusterHealth.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Monitoring cluster health..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $clName = Read-Host "Enter cluster name (blank for all)"
    if ($clName) { $clusters = @(Get-Cluster -Name $clName -ErrorAction Stop) }
    else        { $clusters = Get-Cluster }

    $report = foreach ($cl in $clusters) {
        $alarms = Get-AlarmAction -Entity $cl | Where-Object { $_.Enabled -eq $true }
        [PSCustomObject]@{
            Cluster         = $cl.Name
            DRS             = $cl.DrsEnabled
            HA              = $cl.HaEnabled
            vSAN            = $cl.VsanEnabled
            ActiveAlarms    = ($alarms | Measure-Object).Count
        }
    }
    $outfile = "ClusterHealth_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported cluster health report to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed cluster health monitoring."
