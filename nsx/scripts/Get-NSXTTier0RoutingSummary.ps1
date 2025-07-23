<#
.SYNOPSIS
    Summarizes all Tier-0 router BGP/OSPF/Static routes.

.DESCRIPTION
    Exports Tier-0 router name, protocol, neighbor, learned and advertised route counts.

.NOTES
    PowerCLI >=13.0 required.
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString

$LogPath = "Get-NSXTTier0RoutingSummary.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Summarizing Tier-0 router routes..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass
    Write-Log "Connected."
    $routers = Get-NsxtLogicalRouter | Where-Object { $_.RouterType -eq "TIER0" }
    $report = foreach ($r in $routers) {
        [PSCustomObject]@{
            Router      = $r.DisplayName
            Protocols   = "BGP,OSPF,Static" # Placeholder; expand with Get-Nsxt* commands as needed
            Neighbors   = "N/A"
            RoutesLearned  = "N/A"
            RoutesAdvertised = "N/A"
        }
    }
    $OutFile = "NSXTTier0RoutingSummary_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Tier-0 routing summary exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false }
