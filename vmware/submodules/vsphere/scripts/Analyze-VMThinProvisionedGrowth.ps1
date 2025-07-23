<#
.SYNOPSIS
    Report thin-provisioned disk growth vs allocated space for VMs.

.DESCRIPTION
    Exports VM, disk name, allocated vs provisioned size, and percent used.
    Flags disks nearing full usage.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Analyze-VMThinProvisionedGrowth.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Analyzing thin-provisioned disk usage..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $report = @()
    foreach ($vm in Get-VM) {
        foreach ($hd in $vm | Get-HardDisk | Where-Object { $_.StorageFormat -eq "Thin" }) {
            $usedGB = $hd.CapacityGB * $hd.ExtensionData.Backing.ConsumedSize / $hd.CapacityKB / 1024
            $percentUsed = [math]::Round(($usedGB / $hd.CapacityGB) * 100, 2)
            $report += [PSCustomObject]@{
                VMName = $vm.Name
                DiskName = $hd.Name
                AllocatedGB = $hd.CapacityGB
                ConsumedGB = [math]::Round($usedGB,2)
                PercentUsed = $percentUsed
            }
        }
    }
    $OutFile = "VMThinDiskGrowth_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported thin disk usage report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed thin disk analysis."
