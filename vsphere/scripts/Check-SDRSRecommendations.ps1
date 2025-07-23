<#
.SYNOPSIS
    Gather and report all current Storage DRS recommendations.

.DESCRIPTION
    Lists SDRS moves, reasons, VM, source, target datastores, and status for all SDRS-enabled datastore clusters.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Check-SDRSRecommendations.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking Storage DRS recommendations..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $clusters = Get-DatastoreCluster
    $report = foreach ($cl in $clusters) {
        $sdrsMgr = Get-View $cl.ExtensionData.PodStorageDrsEntry.StorageDrs
        $rec = $sdrsMgr.Recommendations
        foreach ($r in $rec) {
            [PSCustomObject]@{
                Cluster      = $cl.Name
                Recommendation = $r.Reason
                Status         = $r.Status
                VMs            = ($r.VmRecommendation | ForEach-Object { $_.Vm.Name }) -join ","
                Source         = ($r.VmRecommendation | ForEach-Object { $_.Source.Name }) -join ","
                Target         = ($r.VmRecommendation | ForEach-Object { $_.Target.Name }) -join ","
            }
        }
    }
    $OutFile = "SDRSRecommendations_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported SDRS recommendations to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed SDRS recommendation check."
