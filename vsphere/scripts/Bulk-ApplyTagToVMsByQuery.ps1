<#
.SYNOPSIS
    Apply a tag to VMs by advanced search criteria (OS, notes, power state, etc).

.DESCRIPTION
    Prompts for query type and tag, applies to all matching VMs.
    Logs and outputs changes.

.NOTES
    Target: vSphere 8.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Bulk-ApplyTagToVMsByQuery.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Applying tags to VMs by query..."

try {
    Connect-VIServer -Server $vcServer -Credential ([pscredential]::new($vcUser, $vcPass)) -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $criteria = Read-Host "Query (OS|Notes|PowerState)?"
    $value = Read-Host "Value to match"
    $tagCat = Read-Host "Tag category"
    $tagName = Read-Host "Tag name"

    $vms = switch ($criteria.ToLower()) {
        "os"         { Get-VM | Where-Object { $_.Guest.OSFullName -like "*$value*" } }
        "notes"      { Get-VM | Where-Object { $_.Notes -like "*$value*" } }
        "powerstate" { Get-VM | Where-Object { $_.PowerState -eq $value } }
        default      { @() }
    }
    $tag = Get-Tag -Category $tagCat -Name $tagName -ErrorAction Stop
    foreach ($vm in $vms) {
        New-TagAssignment -Entity $vm -Tag $tag
        Write-Log "Tagged $($vm.Name) with $($tag.Name)"
    }
    Write-Log "Tagged $($vms.Count) VMs."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed bulk tag assignment."
