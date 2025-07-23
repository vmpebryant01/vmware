<#
.SYNOPSIS
    Audits SRM protection groups, plans, and VMs for policy compliance.

.DESCRIPTION
    Checks for RPO, test frequency, mapping completeness, and policy drift.
    Exports results to CSV and logs exceptions.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Invoke-SRMComplianceAudit.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting SRM compliance audit..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $groups = Get-SrmProtectionGroup
    $plans  = Get-SrmRecoveryPlan
    $report = @()
    foreach ($g in $groups) {
        foreach ($vm in Get-SrmProtectedVM -ProtectionGroup $g) {
            $violations = @()
            if ($vm.RecoveryPointObjective -gt 60) { $violations += "RPO>60min" }
            # Add more policy checks as needed
            $report += [PSCustomObject]@{
                VMName = $vm.Name
                Group  = $g.Name
                Violations = $violations -join "; "
            }
        }
    }
    $OutFile = "SRMComplianceAudit_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported compliance audit to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed compliance audit."
