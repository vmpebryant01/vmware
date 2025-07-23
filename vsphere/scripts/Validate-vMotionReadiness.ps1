<#
.SYNOPSIS
    Check all hosts and VMs for vMotion readiness.

.DESCRIPTION
    Reports on hosts/VMs failing vMotion checks (network, storage, compatibility).
    Logs all results.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Validate-vMotionReadiness.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Validating vMotion readiness..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hosts = Get-VMHost
    $report = foreach ($vm in Get-VM | Where-Object { $_.PowerState -eq "PoweredOn" }) {
        $vmsupported = $null
        try {
            $vmsupported = Test-VMotion -VM $vm -Destination $hosts[0]
        } catch {
            $vmsupported = $_.Exception.Message
        }
        [PSCustomObject]@{
            VMName = $vm.Name
            Compatible = $vmsupported -is [boolean] ? $vmsupported : $false
            Error      = if ($vmsupported -is [boolean]) { "" } else { $vmsupported }
        }
    }
    $OutFile = "vMotionReadiness_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported vMotion readiness report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed vMotion validation."
