<#
.SYNOPSIS
    Compares SRM protected VMs against CMDB or CSV.

.DESCRIPTION
    Imports a CSV/CMDB file, flags VMs protected in SRM but missing in CMDB, and vice versa.
    Exports results for reconciliation.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString
$cmdbFile = Read-Host "Enter path to CMDB CSV (with VM names in 'Name' column)"

$LogPath = "Compare-SRMtoCMDB.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Comparing SRM VMs to CMDB..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Import-Module VMware.VimAutomation.Srm -ErrorAction Stop
    Write-Log "Connected to vCenter/SRM"
} catch { Write-Log "ERROR: $_"; throw }

try {
    $srmVMs = Get-SrmProtectionGroup | Get-SrmProtectedVM | Select-Object -ExpandProperty Name
    $cmdbVMs = Import-Csv $cmdbFile | Select-Object -ExpandProperty Name
    $missingInCMDB = $srmVMs | Where-Object { $_ -notin $cmdbVMs }
    $missingInSRM  = $cmdbVMs | Where-Object { $_ -notin $srmVMs }
    $OutFile = "SRM_CMDB_Drift_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $results = @()
    foreach ($vm in $missingInCMDB) { $results += [PSCustomObject]@{VM=$vm; Status="SRMOnly"} }
    foreach ($vm in $missingInSRM)  { $results += [PSCustomObject]@{VM=$vm; Status="CMDBOnly"} }
    $results | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported drift results to $OutFile"
} catch { Write-Log "ERROR: $_"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed CMDB/SRM comparison."
