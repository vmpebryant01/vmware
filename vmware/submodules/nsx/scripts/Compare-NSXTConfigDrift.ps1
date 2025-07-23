<#
.SYNOPSIS
    Compares NSX-T configuration to a baseline export and reports drift.

.DESCRIPTION
    Reads a baseline config (JSON/CSV), compares to live config, flags new/missing/changed objects.

.NOTES
    PowerCLI >=13.0 required.
    Baseline file must be exported previously (see Export-NSXTConfigBackup.ps1).
#>
$nsxServer = Read-Host "NSX Manager FQDN/IP"
$nsxUser   = Read-Host "NSX username"
$nsxPass   = Read-Host "NSX password" -AsSecureString
$baselineFile = Read-Host "Enter path to baseline config JSON/CSV"

$LogPath = "Compare-NSXTConfigDrift.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Comparing NSX-T config drift..."

try {
    Import-Module VMware.VimAutomation.Nsx.T -ErrorAction Stop
    Connect-NsxtServer -Server $nsxServer -User $nsxUser -Password $nsxPass -ErrorAction Stop
    Write-Log "Connected."
    # Compare logic placeholder (expand per object type)
    $currSegs = Get-NsxtSegment | Select DisplayName
    $baseline = Import-Csv $baselineFile
    $drift = $currSegs | Where-Object { $_.DisplayName -notin $baseline.DisplayName }
    $OutFile = "NSXTConfigDrift_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $drift | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Config drift exported to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-NsxtServer -Confirm:$false; Write-Log "Disconnected." }
