<#
.SYNOPSIS
    Report all VMs with no tags assigned.

.DESCRIPTION
    Exports all VMs without any tag assignments, with name and notes.
    Logs all steps, outputs to CSV.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-VMsWithoutTags.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting VMs without tags report."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $tags = Get-TagAssignment -Entity $vm
        if ($tags.Count -eq 0) {
            [PSCustomObject]@{
                Name  = $vm.Name
                Notes = $vm.Notes
            }
        }
    }
    $OutFile = "VMsWithoutTags_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VMs without tags to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
