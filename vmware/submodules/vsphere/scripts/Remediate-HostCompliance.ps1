<#
.SYNOPSIS
    Check and remediate host config drift (NTP, syslog, advanced settings).

.DESCRIPTION
    Compares each host’s NTP/syslog/advanced config to baseline, logs/remediates drift.

.NOTES
    PowerCLI >=13.0 required.
    Adjust $baselineNTP, $baselineSyslog, $advSettings as needed.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$baselineNTP    = "pool.ntp.org"
$baselineSyslog = "udp://10.0.0.1:514"
$advSettings    = @{ "VMKernel.Boot.autoBackup" = "1" }

$LogPath = "Remediate-HostCompliance.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting host compliance check..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    foreach ($host in Get-VMHost) {
        # NTP
        $ntp = (Get-VMHostNtpServer -VMHost $host) -join ","
        if ($ntp -ne $baselineNTP) {
            Add-VMHostNtpServer -VMHost $host -NtpServer ($baselineNTP -split ",") -Confirm:$false
            Write-Log "Fixed NTP on $($host.Name)"
        }
        # Syslog
        $syslog = (Get-VMHostAdvancedConfiguration -VMHost $host -Name "Syslog.global.logHost")["Syslog.global.logHost"]
        if ($syslog -ne $baselineSyslog) {
            Set-VMHostAdvancedConfiguration -VMHost $host -Name "Syslog.global.logHost" -Value $baselineSyslog
            Write-Log "Fixed syslog on $($host.Name)"
        }
        # Advanced settings
        foreach ($key in $advSettings.Keys) {
            $val = (Get-VMHostAdvancedConfiguration -VMHost $host -Name $key)[$key]
            if ($val -ne $advSettings[$key]) {
                Set-VMHostAdvancedConfiguration -VMHost $host -Name $key -Value $advSettings[$key]
                Write-Log "Fixed advanced setting $key on $($host.Name)"
            }
        }
    }
    Write-Log "Remediation complete."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed compliance remediation."
