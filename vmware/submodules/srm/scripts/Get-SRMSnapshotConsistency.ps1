<#
.SYNOPSIS
    Reports on snapshot consistency and policy for SRM protected VMs.

.DESCRIPTION
    Lists each protected VM and its most recent snapshot (if present).
    Exports results to CSV.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-SRMSnapshotConsistency.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking SRM VM snapshot consistency..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $vms = Get-SrmProtectionGroup | Get-SrmProtectedVM
    $report = foreach ($vm in $vms) {
        $snap = Get-Snapshot -VM $vm.Name -ErrorAction SilentlyContinue | Sort-Object -Property Created -Descending | Select-Object -First 1
        [PSCustomObject]@{
            VMName = $vm.Name
            LastSnapshot = if ($snap) { $snap.Created } else { "None" }
        }
    }
    $OutFile = "SRMSnapshotConsistency_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported snapshot consistency to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed snapshot consistency check."
