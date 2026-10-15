<#
.SYNOPSIS
    Set or update NTP servers for ESXi hosts.

.DESCRIPTION
    Prompts for NTP servers and (optionally) host name. Applies, enables, and restarts NTP.
    Logs each action.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>

$vcServer  = Read-Host "Enter vCenter FQDN or IP"
$vcUser    = Read-Host "Enter vCenter username"
$vcPass    = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Update-HostNTP.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Updating host NTP..."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $ntp = Read-Host "Enter NTP servers (comma separated)"
    $hostName = Read-Host "Enter host name (leave blank for all)"

    if ($hostName) {
        $hosts = @(Get-VMHost -Name $hostName -ErrorAction Stop)
    } else {
        $hosts = Get-VMHost
    }

    foreach ($host in $hosts) {
        $host | Add-VMHostNtpServer -NtpServer ($ntp -split ",") -Confirm:$false
        $host | Get-VMHostService | Where-Object { $_.Key -eq "ntpd" } | Start-VMHostService | Out-Null
        $host | Get-VMHostService | Where-Object { $_.Key -eq "ntpd" } | Set-VMHostService -Policy "on" | Out-Null
        Write-Log "Set NTP [$ntp] and enabled service for $($host.Name)"
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed NTP configuration."
