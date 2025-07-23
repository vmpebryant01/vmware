<#
.SYNOPSIS
    Disable (disconnect) unused VM NICs.

.DESCRIPTION
    Prompts for VM name, disconnects any NICs with no network assigned or that are connected but not in use.
    Logs all actions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Disable-UnusedNICs.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Disabling unused NICs..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $vm = Get-VM -Name $VMName -ErrorAction Stop
    $adapters = $vm | Get-NetworkAdapter

    foreach ($nic in $adapters) {
        if (!$nic.Connected -or !$nic.NetworkName) {
            Set-NetworkAdapter -NetworkAdapter $nic -Connected:$false -Confirm:$false
            Write-Log "Disconnected NIC $($nic.Name) on $VMName"
        }
    }
    Write-Log "Checked $(($adapters).Count) adapters for $VMName"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed unused NIC disablement."
