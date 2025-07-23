<#
.SYNOPSIS
    Report VMs with/without backup tools/services installed.

.DESCRIPTION
    Checks all VMs for presence of common backup/agent services (e.g., Veeam, Commvault, Avamar).
    Logs and exports to CSV.

.NOTES
    PowerCLI >=13.0 required.
    Requires VMware Tools running on VMs.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Check-VMBackupTools.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking VM backup agents..."

$backupServices = @("VeeamAgent","CVService","AvamarClient")

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM | Where-Object { $_.PowerState -eq "PoweredOn" }
    $report = foreach ($vm in $vms) {
        $tools = $vm | Get-VMGuest
        $services = $tools.ExtensionData.GuestOperationsManager.ProcessManager.ListProcessesInGuest($tools.ExtensionData.MoRef, @()).Name
        $hasAgent = $backupServices | Where-Object { $services -contains $_ }
        [PSCustomObject]@{
            VMName     = $vm.Name
            BackupTool = $hasAgent -join ","
            Status     = if ($hasAgent) { "AgentFound" } else { "NotFound" }
        }
    }
    $OutFile = "VMBackupAgents_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VM backup agent report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed backup tools check."
