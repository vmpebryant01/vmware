<#
.SYNOPSIS
    Set or update notes for a VM.

.DESCRIPTION
    Prompts for VM name and note content, applies to VM.
    Logs changes.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Set-VMNotes.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Setting VM notes..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $Note   = Read-Host "Enter new notes"

    Set-VM -VM $VMName -Notes $Note -Confirm:$false
    Write-Log "Set notes for $VMName: $Note"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed notes update."
