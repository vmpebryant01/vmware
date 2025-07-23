<#
.SYNOPSIS
    Configure DRS affinity or anti-affinity rules for a cluster.

.DESCRIPTION
    Prompts for cluster, rule type (affinity/anti-affinity), VMs, and rule name. Adds or updates rule.
    Logs all changes.

.NOTES
    PowerCLI >=13.0 required.
#>

$vcServer    = Read-Host "Enter vCenter FQDN or IP"
$vcUser      = Read-Host "Enter vCenter username"
$vcPass      = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Configure-DRSRules.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Configuring DRS rules..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $ClusterName = Read-Host "Enter cluster name"
    $RuleType    = Read-Host "Enter rule type (Affinity/AntiAffinity)"
    $VMs         = Read-Host "Enter VM names (comma separated)"
    $RuleName    = Read-Host "Enter rule name"

    $cluster = Get-Cluster -Name $ClusterName -ErrorAction Stop
    $vmArr   = $VMs -split ","
    $vmObjs  = foreach ($vm in $vmArr) { Get-VM -Name $vm.Trim() -ErrorAction Stop }

    if ($RuleType -eq "Affinity") {
        New-DrsRule -Cluster $cluster -Name $RuleName -Enabled:$true -KeepTogether:$true -VM $vmObjs -Confirm:$false
    } else {
        New-DrsRule -Cluster $cluster -Name $RuleName -Enabled:$true -KeepTogether:$false -VM $vmObjs -Confirm:$false
    }
    Write-Log "Added DRS $RuleType rule $RuleName to cluster $ClusterName"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed DRS rule config."
