<#
.SYNOPSIS
    Report on VM tag compliance by category and value.

.DESCRIPTION
    Checks all VMs for required tags, exports those missing tags, and those compliant.
    Output to CSV, logs all steps.

.NOTES
    PowerCLI >=13.0 required.
    Adjust $RequiredTagCategory/$RequiredTagValue as needed.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

# Customize for your org
$RequiredTagCategory = "App"
$RequiredTagValue    = "Production"

$LogPath = "Get-VMTagCompliance.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File -FilePath $LogPath -Append }
Write-Log "Starting VM tag compliance check."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $vms = Get-VM
    $report = foreach ($vm in $vms) {
        $tags = (Get-TagAssignment -Entity $vm | Where-Object {$_.Tag.Category -eq $RequiredTagCategory}).Tag.Name
        $isCompliant = $tags -contains $RequiredTagValue
        [PSCustomObject]@{
            Name           = $vm.Name
            Compliant      = $isCompliant
            AssignedTags   = $tags -join ","
        }
    }
    $OutFile = "VMTagCompliance_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported VM tag compliance report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed."
