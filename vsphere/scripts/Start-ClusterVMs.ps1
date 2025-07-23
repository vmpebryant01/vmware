<#
.SYNOPSIS
    Start all powered-off VMs in a selected cluster.

.DESCRIPTION
    Prompts for cluster name, then starts all VMs in the cluster that are powered off.
    Logs each action and any errors.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer  = Read-Host "Enter vCenter FQDN or IP"
$vcUser    = Read-Host "Enter vCenter username"
$vcPass    = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Start-ClusterVMs.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting powered-off VMs in cluster..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $cluster = Read-Host "Enter cluster name"
    $clObj   = Get-Cluster -Name $cluster -ErrorAction Stop
    $vms     = Get-VM -Location $clObj | Where-Object { $_.PowerState -eq "PoweredOff" }

    foreach ($vm in $vms) {
        Write-Log "Starting VM $($vm.Name)"
        Start-VM -VM $vm | Out-Null
    }
    Write-Log "Started $($vms.Count) VMs in $cluster"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed cluster VM startup."
