throw 'NSX gateway service health retrieval is not implemented for this example.'
# Required published cmdlets are checked before credentials are requested.
$requiredCommands = @('Get-NsxtLogicalRouter')
$unavailableCommands = @($requiredCommands | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
if ($unavailableCommands.Count -gt 0) { throw "Required commands are unavailable: $($unavailableCommands -join ', '). This example needs an implemented SRM or NSX API adapter for the installed product version." }

<#
.SYNOPSIS
    Reports health/status of all NSX-T gateway services (NAT, DHCP, VPN, Load Balancer).

.DESCRIPTION
    Lists router name, service, status, errors, and logs.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTGatewayServiceHealth.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Reporting NSX-T gateway service health..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
    $routers = Get-NsxtLogicalRouter
    $report = foreach ($r in $routers) {
        # Placeholder: For each router, fetch relevant services and their status
        [PSCustomObject]@{
            Router = $r.DisplayName
            NAT = "OK"
            DHCP = "OK"
            VPN  = "OK"
            LB   = "OK"
        }
    }
    $OutFile = "NSXTGatewayServiceHealth_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Gateway service health exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
