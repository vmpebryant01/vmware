<#
.SYNOPSIS
    Enable detailed logging for a VM.

.DESCRIPTION
    Prompts for VM name, sets logging to highest level (vmx.log.keepOld, vmx.log.level).
    Logs all actions.

.NOTES
    PowerCLI >=13.0 required.
    Use with caution (may impact disk usage).
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Enable-VMLogging.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Enabling VM logging..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $vm = Get-VM -Name $VMName -ErrorAction Stop

    New-AdvancedSetting -Entity $vm -Name "log.keepOld" -Value "10" -Force
    New-AdvancedSetting -Entity $vm -Name "log.level"   -Value "trivia" -Force

    Write-Log "Enabled advanced logging for $VMName"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed VM logging enablement."
