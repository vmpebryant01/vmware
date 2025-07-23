<#
.SYNOPSIS
    Exports SRM configuration and inventory for backup and compliance.

.DESCRIPTION
    Dumps configuration of protection groups, recovery plans, mappings, and settings.
    Output is a JSON and CSV for compliance audits.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Export-SRMConfig.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM config export..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $plans  = Get-SrmRecoveryPlan
    $map    = $groups | ForEach-Object { $_ | Get-SrmProtectionGroupMapping }
    $config = @{
        Groups = $groups | Select Name, ProtectionType
        Plans  = $plans | Select Name, State
        Mappings = $map | Select Source, Target, Type
    }
    $JsonFile = "SRMConfig_$(Get-Date -Format yyyyMMdd_HHmmss).json"
    $config | ConvertTo-Json | Out-File -Encoding utf8 $JsonFile
    Write-Log "Exported SRM config to $JsonFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed config export."
