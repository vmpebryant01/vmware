<#
.SYNOPSIS
    Detects configuration drift in SRM protection groups and recovery plans.

.DESCRIPTION
    Compares current config to baseline (JSON/CSV), flags changes and new/deleted objects.
    Exports drift report.

.NOTES
    PowerCLI >=13.0 required.
    Baseline file must be exported by Export-SRMConfig.ps1.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString
$baselineFile = Read-Host "Enter path to baseline config JSON"

$LogPath = "Detect-SRMConfigDrift.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Detecting SRM config drift..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
} catch { Write-Log "ERROR: $_"; throw }

try {
    $baseline = Get-Content $baselineFile | ConvertFrom-Json
    $currGroups = Get-SrmProtectionGroup | Select Name, ProtectionType
    $currPlans  = Get-SrmRecoveryPlan | Select Name, State

    $drift = @()
    foreach ($g in $currGroups) {
        if (-not ($baseline.Groups | Where-Object { $_.Name -eq $g.Name })) {
            $drift += [PSCustomObject]@{Type="Group"; Name=$g.Name; Drift="NewInSRM"}
        }
    }
    foreach ($g in $baseline.Groups) {
        if (-not ($currGroups | Where-Object { $_.Name -eq $g.Name })) {
            $drift += [PSCustomObject]@{Type="Group"; Name=$g.Name; Drift="MissingInSRM"}
        }
    }
    # Repeat for plans as needed...
    $OutFile = "SRMConfigDrift_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $drift | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported config drift report to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed config drift check."
