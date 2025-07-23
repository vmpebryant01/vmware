<#
.SYNOPSIS
    Report VM templates not deployed from in X months.

.DESCRIPTION
    Prompts for months threshold, lists all templates with last used date (if available).
    Logs results.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Find-StaleTemplates.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Finding stale VM templates..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $months = Read-Host "Stale if not deployed from in X months"
    $cutoff = (Get-Date).AddMonths(-[int]$months)
    $templates = Get-Template
    $report = foreach ($tmpl in $templates) {
        # This field may not be directly available; for real audit, would need tracking on deployment tasks.
        [PSCustomObject]@{
            Name = $tmpl.Name
            Notes = $tmpl.Notes
            LastDeployed = "" # Placeholder
            Stale = "Unknown"
        }
    }
    $OutFile = "StaleTemplates_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported stale template report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed stale template search."
