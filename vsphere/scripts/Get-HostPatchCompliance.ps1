<#
.SYNOPSIS
    Report ESXi host patch compliance and outstanding critical updates.

.DESCRIPTION
    Exports host name, build, compliance status, and count of critical patches.
    Output to CSV and logs all steps.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-HostPatchCompliance.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting ESXi patch compliance export."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hosts = Get-VMHost
    $report = foreach ($host in $hosts) {
        $baseline = Get-VMHostPatch -VMHost $host -Status NotInstalled
        [PSCustomObject]@{
            Name           = $host.Name
            Build          = $host.Build
            Compliance     = if ($baseline.Count -eq 0) {"Compliant"} else {"Non-Compliant"}
            CriticalPatches= ($baseline | Where-Object {$_.Severity -eq "Critical"}).Count
        }
    }
    $OutFile = "HostPatchCompliance_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported ESXi patch compliance to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
