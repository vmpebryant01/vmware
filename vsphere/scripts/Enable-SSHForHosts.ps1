<#
.SYNOPSIS
    Enable SSH service for all or specific ESXi hosts.

.DESCRIPTION
    Prompts for host name (blank for all), enables SSH, and sets policy to 'on'.
    Logs results.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Enable-SSHForHosts.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Enabling SSH on host(s)..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hostName = Read-Host "Enter host name (leave blank for all)"
    if ($hostName) {
        $hosts = @(Get-VMHost -Name $hostName -ErrorAction Stop)
    } else {
        $hosts = Get-VMHost
    }
    foreach ($host in $hosts) {
        $service = Get-VMHostService -VMHost $host | Where-Object {$_.Key -eq "TSM-SSH"}
        if ($service) {
            Start-VMHostService -HostService $service | Out-Null
            Set-VMHostService -HostService $service -Policy "on" | Out-Null
            Write-Log "Enabled SSH for $($host.Name)"
        }
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed SSH enablement."
