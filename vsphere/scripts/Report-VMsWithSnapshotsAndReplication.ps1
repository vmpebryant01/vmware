<#
.SYNOPSIS
    Flag VMs with active snapshots and in a replication/protection group.

.DESCRIPTION
    Lists VMs with snapshots and present in SRM/VVOL replication or vSphere Replication.
    Logs and exports results.

.NOTES
    PowerCLI >=13.0 and relevant modules required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Report-VMsWithSnapshotsAndReplication.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Finding VMs with snapshots and replication..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction SilentlyContinue
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $repVMs = @()
    try { $repVMs += Get-SrmProtectedVM | Select-Object -ExpandProperty Name } catch {}
    try { $repVMs += Get-SpbmReplicatedVM | Select-Object -ExpandProperty Name } catch {}

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
