<#
.SYNOPSIS
    Export a report of all datastores and their usage.

.DESCRIPTION
    Collects free, used, capacity, and type for all datastores in vCenter.
    Exports to CSV, logs all steps.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-DatastoreUsage.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting datastore usage export."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $datastores = Get-Datastore
    $report = foreach ($ds in $datastores) {
        [PSCustomObject]@{
            Name      = $ds.Name
            Type      = $ds.Type
            CapacityGB= [math]::Round($ds.CapacityGB,2)
            FreeGB    = [math]::Round($ds.FreeSpaceGB,2)
            UsedGB    = [math]::Round($ds.CapacityGB-$ds.FreeSpaceGB,2)
        }
    }
    $OutFile = "DatastoreUsage_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported datastore usage to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
