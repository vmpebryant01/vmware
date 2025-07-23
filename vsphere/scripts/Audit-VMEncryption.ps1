<#
.SYNOPSIS
    Report VM encryption, vTPM, and policy status for all VMs.

.DESCRIPTION
    Exports all VMs, their encryption state, KMS cluster, vTPM presence, and encryption policy.
    Logs actions and errors.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Audit-VMEncryption.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting VM encryption audit..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $enc = $vm.ExtensionData.Config.VmEncryption
        $vTPM = ($vm | Get-VMResourceConfiguration).ExtensionData.Device | Where-Object {$_.DeviceInfo.Label -like "*Trusted Platform Module*"}
        [PSCustomObject]@{
            VMName           = $vm.Name
            Encrypted        = if ($enc) { "Yes" } else { "No" }
            EncryptionPolicy = $vm.ExtensionData.Config.StoragePolicyName
            KMSCluster       = if ($enc) { $enc.KeyProviderId?.Id } else { "" }
            HasvTPM          = if ($vTPM) { "Yes" } else { "No" }
        }
    }
    $OutFile = "VMEncryptionAudit_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VM encryption audit to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed encryption audit."
