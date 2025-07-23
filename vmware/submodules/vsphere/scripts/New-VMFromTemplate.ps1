<#
.SYNOPSIS
    Deploy a new VM from a template.

.DESCRIPTION
    Prompts for VM name, template, datastore, and network. Clones the VM, customizes guest, and powers on.
    Logs all actions and errors.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer  = Read-Host "Enter vCenter FQDN or IP"
$vcUser    = Read-Host "Enter vCenter username"
$vcPass    = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "New-VMFromTemplate.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Starting new VM deployment..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName    = Read-Host "Enter new VM name"
    $Template  = Read-Host "Enter template name"
    $Datastore = Read-Host "Enter datastore name"
    $Network   = Read-Host "Enter network name"

    $tmpl = Get-Template -Name $Template -ErrorAction Stop
    $ds   = Get-Datastore -Name $Datastore -ErrorAction Stop
    $net  = Get-VirtualPortGroup -Name $Network -ErrorAction Stop

    $newVM = New-VM -Name $VMName -Template $tmpl -Datastore $ds -NetworkName $Network -ErrorAction Stop
    Start-VM -VM $newVM | Out-Null
    Write-Log "Deployed and powered on VM $VMName"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed new VM deployment."
