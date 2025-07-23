<#
.SYNOPSIS
    Set advanced settings for a VM, host, or cluster.

.DESCRIPTION
    Prompts for entity type, name, setting, and value. Applies and logs changes.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer  = Read-Host "Enter vCenter FQDN or IP"
$vcUser    = Read-Host "Enter vCenter username"
$vcPass    = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Set-AdvancedSettings.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Setting advanced config..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $Type   = Read-Host "Entity type (VM, Host, Cluster)"
    $Name   = Read-Host "Entity name"
    $Key    = Read-Host "Advanced setting key"
    $Value  = Read-Host "Advanced setting value"

    switch ($Type.ToLower()) {
        "vm"      { $obj = Get-VM -Name $Name -ErrorAction Stop }
        "host"    { $obj = Get-VMHost -Name $Name -ErrorAction Stop }
        "cluster" { $obj = Get-Cluster -Name $Name -ErrorAction Stop }
        default   { throw "Invalid entity type." }
    }
    New-AdvancedSetting -Entity $obj -Name $Key -Value $Value -Force
    Write-Log "Set $Key=$Value on $Type $Name"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed advanced config update."
