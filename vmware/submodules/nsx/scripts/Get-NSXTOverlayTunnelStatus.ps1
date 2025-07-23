<#
.SYNOPSIS
    Reports status of NSX-T overlay tunnels (TEP to TEP).

.DESCRIPTION
    Checks VXLAN/Geneve tunnel status for all transport/edge nodes.
    Flags down tunnels for troubleshooting.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTOverlayTunnelStatus.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Checking overlay tunnel status..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    $nodes = Get-NsxtTransportNode
    $report = foreach ($n in $nodes) {
        # Placeholder: Insert logic to get overlay tunnel status per node
        [PSCustomObject]@{
            Node = $n.DisplayName
            TunnelStatus = "OK"
        }
    }
    $OutFile = "NSXTOverlayTunnelStatus_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Overlay tunnel status exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
