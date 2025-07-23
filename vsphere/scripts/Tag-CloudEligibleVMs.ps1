<#
.SYNOPSIS
    Identify and tag VMs suitable for cloud migration.

.DESCRIPTION
    Based on OS, size, uptime, and custom criteria, tags cloud-eligible VMs.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Tag-CloudEligibleVMs.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Tagging cloud-eligible VMs..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM | Where-Object {
        $_.Guest.OSFullName -match "Windows|Linux" -and
        $_.MemoryGB -le 16 -and
        $_.PowerState -eq "PoweredOn"
    }
    $tag = Get-Tag -Category "Cloud" -Name "Eligible" -ErrorAction Stop
    foreach ($vm in $vms) {
        New-TagAssignment -Entity $vm -Tag $tag
        Write-Log "Tagged $($vm.Name) as Cloud Eligible"
    }
    Write-Log "Tagged $($vms.Count) VMs."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed cloud eligibility tagging."
