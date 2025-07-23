<#
.SYNOPSIS
    Bulk update cluster settings (DRS, HA, admission control).

.DESCRIPTION
    Prompts for cluster, DRS/HA/Admission settings, and applies.
    Logs changes for auditing.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Update-ClusterSettings.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Updating cluster settings..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $ClusterName = Read-Host "Enter cluster name"
    $EnableDRS   = Read-Host "Enable DRS? (Y/N)"
    $EnableHA    = Read-Host "Enable HA? (Y/N)"
    $EnableAC    = Read-Host "Enable Admission Control? (Y/N)"

    $cluster = Get-Cluster -Name $ClusterName -ErrorAction Stop

    $drs = $EnableDRS -eq "Y"
    $ha  = $EnableHA  -eq "Y"
    $ac  = $EnableAC  -eq "Y"

    Set-Cluster -Cluster $cluster -DrsEnabled:$drs -HaEnabled:$ha -DrsAutomationLevel FullyAutomated -Confirm:$false | Out-Null
    if ($ac) { Set-Cluster -Cluster $cluster -HAAdmissionControlEnabled:$true -Confirm:$false | Out-Null }
    else     { Set-Cluster -Cluster $cluster -HAAdmissionControlEnabled:$false -Confirm:$false | Out-Null }
    Write-Log "Updated settings for cluster $ClusterName"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed cluster settings update."
