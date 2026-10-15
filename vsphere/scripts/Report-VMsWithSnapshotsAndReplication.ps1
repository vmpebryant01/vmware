<#
.SYNOPSIS
    Flag VMs with active snapshots and in a replication/protection group.

.DESCRIPTION
    Lists VMs with snapshots and present in SRM/VVOL replication or vSphere Replication.
    Logs and exports results.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference).
    Requires a separately implemented SRM or replication command adapter.
#>
Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
$requiredCommands = @('Get-SrmProtectedVM', 'Get-SpbmReplicatedVM')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) {
    throw "Required replication commands are unavailable: $($unavailableCommands -join ', '). Implement an adapter for the installed product version."
}
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Report-VMsWithSnapshotsAndReplication.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Finding VMs with snapshots and replication..."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $repVMs = @()
    $repVMs += Get-SrmProtectedVM -ErrorAction Stop | Select-Object -ExpandProperty Name
    $repVMs += Get-SpbmReplicatedVM -ErrorAction Stop | Select-Object -ExpandProperty Name

    $report = foreach ($vm in Get-VM | Where-Object { (Get-Snapshot -VM $_ -ErrorAction SilentlyContinue) }) {
        $rep = $repVMs -contains $vm.Name
        if ($rep) {
            [PSCustomObject]@{
                VMName     = $vm.Name
                HasSnapshot= "Yes"
                Replicated = "Yes"
            }
        }
    }
    $OutFile = "VMsWithSnapshotsAndReplication_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed combined snapshot/replication audit."
