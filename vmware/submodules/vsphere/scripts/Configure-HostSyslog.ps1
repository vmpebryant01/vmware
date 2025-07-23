<#
.SYNOPSIS
    Set syslog server(s) for all or specific ESXi hosts.

.DESCRIPTION
    Prompts for syslog server address and host. Applies and logs result.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Configure-HostSyslog.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Configuring host syslog..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $Syslog = Read-Host "Enter syslog server address (e.g., udp://10.10.10.10:514)"
    $hostName = Read-Host "Enter host name (leave blank for all)"

    if ($hostName) {
        $hosts = @(Get-VMHost -Name $hostName -ErrorAction Stop)
    } else {
        $hosts = Get-VMHost
    }

    foreach ($host in $hosts) {
        Set-VMHostAdvancedConfiguration -VMHost $host -Name "Syslog.global.logHost" -Value $Syslog
        Write-Log "Set syslog [$Syslog] for host $($host.Name)"
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed syslog configuration."
