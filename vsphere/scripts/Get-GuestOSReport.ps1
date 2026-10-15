<#
.SYNOPSIS
    Generate a report of all guest OS versions for all VMs.

.DESCRIPTION
    Exports each VM name, guest OS full name, tools status, and IP.
    Logs steps, outputs to CSV.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-GuestOSReport.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting Guest OS report."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $guest = $vm | Get-VMGuest
        [PSCustomObject]@{
            Name        = $vm.Name
            GuestOS     = $vm.Guest.OSFullName
            ToolsStatus = $vm.ExtensionData.Guest.ToolsStatus
            IP          = $guest.IPAddress -join ","
        }
    }
    $OutFile = "GuestOSReport_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported Guest OS report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
