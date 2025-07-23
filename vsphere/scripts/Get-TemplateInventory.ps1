<#
.SYNOPSIS
    Export a list of all VM templates.

.DESCRIPTION
    Lists template name, guest OS, notes, and datastore. Exports to CSV and logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-TemplateInventory.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting template inventory export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $templates = Get-Template
    $report = foreach ($tmpl in $templates) {
        [PSCustomObject]@{
            Name      = $tmpl.Name
            GuestOS   = $tmpl.GuestId
            Notes     = $tmpl.Notes
            Datastore = $tmpl.Datastore -join ","
        }
    }
    $OutFile = "TemplateInventory_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported template inventory to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
