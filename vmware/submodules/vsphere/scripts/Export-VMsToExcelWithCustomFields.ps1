<#
.SYNOPSIS
    Export VMs to Excel with custom business/tag/cost fields.

.DESCRIPTION
    Includes business owner, app, tag data, estimated cost, and core VM properties.
    Requires ImportExcel PowerShell module.

.NOTES
    PowerCLI >=13.0 required.
    Install-Module -Name ImportExcel if not present.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

Import-Module ImportExcel -ErrorAction Stop

$LogPath = "Export-VMsToExcelWithCustomFields.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting VMs to Excel with custom fields..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $tags = (Get-TagAssignment -Entity $vm | Select-Object -ExpandProperty Tag) -join ","
        $owner = ($tags -match "Owner:") ? ($tags -split "Owner:")[1].Split(",")[0] : ""
        $cost = [math]::Round($vm.MemoryGB * 10 + $vm.NumCpu * 20, 2) # Placeholder logic
        [PSCustomObject]@{
            Name      = $vm.Name
            GuestOS   = $vm.Guest.OSFullName
            CPUs      = $vm.NumCpu
            MemGB     = $vm.MemoryGB
            Tags      = $tags
            Owner     = $owner
            EstCost   = $cost
        }
    }
    $OutFile = "VMs_Custom_$(Get-Date -Format yyyyMMdd_HHmmss).xlsx"
    $report | Export-Excel -Path $OutFile -AutoSize
    Write-Log "Exported VMs with custom fields to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed Excel export."
