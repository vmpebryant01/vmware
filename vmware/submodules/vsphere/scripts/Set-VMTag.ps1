<#
.SYNOPSIS
    Assign a tag to one or more VMs.

.DESCRIPTION
    Prompts for tag category and value, and assigns it to selected or all VMs.
    Logs all actions and errors.

.NOTES
    PowerCLI >=13.0 required.
    Tag must exist in vCenter.
#>

$vcServer     = Read-Host "Enter vCenter FQDN or IP"
$vcUser       = Read-Host "Enter vCenter username"
$vcPass       = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Set-VMTag.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting tag assignment..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $TagCategory = Read-Host "Enter tag category"
    $TagName     = Read-Host "Enter tag name"
    $VMName      = Read-Host "Enter VM name (or leave blank for all)"

    $tag = Get-Tag -Category $TagCategory -Name $TagName -ErrorAction Stop

    if ($VMName) {
        $vms = Get-VM -Name $VMName -ErrorAction Stop
    } else {
        $vms = Get-VM
    }

    foreach ($vm in $vms) {
        New-TagAssignment -Entity $vm -Tag $tag
        Write-Log "Assigned tag $TagCategory/$TagName to VM $($vm.Name)"
    }
    Write-Log "Tag assignment complete."
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed VM tagging."
