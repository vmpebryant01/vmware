<#
.SYNOPSIS
    Export vCenter events to CSV for incident review and audit.

.DESCRIPTION
    Prompts for days of history and entity (cluster, host, or VM), collects all relevant events.
    Exports to CSV and logs actions.

.NOTES
    PowerCLI >=13.0 required.
    Adjust event types/filters as needed.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Collect-vCenterEvents.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Collecting vCenter events..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $days = Read-Host "Export events from how many days back?"
    $since = (Get-Date).AddDays(-[int]$days)
    $entityType = Read-Host "Entity type (Cluster/Host/VM/All)?"
    $entityName = ""
    if ($entityType -ne "All") {
        $entityName = Read-Host "Entity name"
    }

    switch ($entityType.ToLower()) {
        "cluster" { $entity = Get-Cluster -Name $entityName -ErrorAction Stop }
        "host"    { $entity = Get-VMHost -Name $entityName -ErrorAction Stop }
        "vm"      { $entity = Get-VM -Name $entityName -ErrorAction Stop }
        default   { $entity = $null }
    }

    if ($entity) {
        $events = Get-VIEvent -Entity $entity -Start $since
    } else {
        $events = Get-VIEvent -Start $since
    }
    $report = foreach ($evt in $events) {
        [PSCustomObject]@{
            Time    = $evt.CreatedTime
            User    = $evt.UserName
            Type    = $evt.GetType().Name
            Entity  = $evt.Entity.Name
            Message = $evt.FullFormattedMessage
        }
    }
    $outfile = "vCenterEvents_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported vCenter events to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed vCenter event collection."
