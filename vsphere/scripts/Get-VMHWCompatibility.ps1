<#
.SYNOPSIS
    Report on VM hardware version compatibility with hosts.

.DESCRIPTION
    Lists VMs and checks if their hardware version is supported by all connected hosts.
    Exports to CSV and logs any incompatible VMs.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-VMHWCompatibility.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking VM hardware compatibility..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hosts = Get-VMHost
    $maxHwVer = ($hosts | ForEach-Object { $_.ExtensionData.Capability.VmDirectPathGen2Supported } | Measure-Object -Maximum).Maximum
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        [PSCustomObject]@{
            VMName    = $vm.Name
            HWVersion = $vm.Version
            IsCompatible = if ([int]$vm.Version.Replace("vmx-","") -le $maxHwVer) { $true } else { $false }
        }
    }
    $outfile = "VMHWCompatibility_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $outfile
    Write-Log "Exported VM HW compatibility to $outfile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed HW compatibility check."
