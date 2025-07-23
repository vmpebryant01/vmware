<#
.SYNOPSIS
    Export logs from ESXi hosts for support/troubleshooting.

.DESCRIPTION
    Prompts for host name (leave blank for all), downloads latest host log bundle to current directory.
    Logs all actions and any errors.

.NOTES
    PowerCLI >=13.0 required.
    You must have permissions to download logs.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostLogs.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting ESXi host log export..."

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
        $bundle = Get-Log -VMHost $host -Bundle
        $bundle | ForEach-Object {
            $filename = "$($host.Name)_LogBundle.tgz"
            Set-Content -Path $filename -Value $_.Content -Encoding Byte
            Write-Log "Downloaded log bundle for $($host.Name) as $filename"
        }
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed ESXi host log export."
