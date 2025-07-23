<#
.SYNOPSIS
    Configure DNS servers for all ESXi hosts or a specific host.

.DESCRIPTION
    Prompts for DNS servers and (optionally) a host name. Applies settings.
    Logs each action and any errors.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer  = Read-Host "Enter vCenter FQDN or IP"
$vcUser    = Read-Host "Enter vCenter username"
$vcPass    = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Set-HostDNS.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Configuring host DNS..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $dns = Read-Host "Enter DNS servers (comma separated)"
    $hostName = Read-Host "Enter host name (leave blank for all)"

    if ($hostName) {
        $hosts = @(Get-VMHost -Name $hostName -ErrorAction Stop)
    } else {
        $hosts = Get-VMHost
    }

    foreach ($host in $hosts) {
        Get-VMHostNetwork -VMHost $host | Set-VMHostNetwork -DNSAddress ($dns -split ",") -Confirm:$false
        Write-Log "Set DNS [$dns] for host $($host.Name)"
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed host DNS configuration."
