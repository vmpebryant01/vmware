# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-SrmProtectedVM', 'Get-SrmProtectionGroup')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Reports on snapshot consistency and policy for SRM protected VMs.

.DESCRIPTION
    Lists each protected VM and its most recent snapshot (if present).
    Exports results to CSV.

.NOTES
    Target: SRM 8.x / Live Site Recovery 9.0.2.x with VMware.PowerCLI 13.x. See docs/compatibility.md.
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
