<#
.SYNOPSIS
    Export VM to network mappings.

.DESCRIPTION
    Lists each VM, its NICs, and their assigned port groups.
    Exports to CSV, logs all steps.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-VMNetworkMappings.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting VM network mappings export."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        foreach ($nic in $vm | Get-NetworkAdapter) {
            [PSCustomObject]@{
                VMName    = $vm.Name
                Adapter   = $nic.Name
                Network   = $nic.NetworkName
                MAC       = $nic.MacAddress
            }
        }
    }
    $OutFile = "VMNetworkMappings_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported network mappings to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw } 
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
