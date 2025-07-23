<#
.SYNOPSIS
    Export latest vmware.log for a specified VM.

.DESCRIPTION
    Prompts for VM name, downloads vmware.log for analysis.
    Logs all actions.

.NOTES
    PowerCLI >=13.0 required.
    Works only on VMs with logging enabled and accessible files.
#>

$vcServer = Read-Host "Enter vCenter FQDN or IP"
$vcUser   = Read-Host "Enter vCenter username"
$vcPass   = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Get-VMLogBundle.log"
function Write-Log ($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Exporting VM log bundle..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $VMName = Read-Host "Enter VM name"
    $vm = Get-VM -Name $VMName -ErrorAction Stop
    $logPath = ($vm | Get-View).LayoutEx.File | Where-Object { $_.Name -like "*vmware.log" } | Select-Object -First 1 -ExpandProperty Name
    if ($logPath) {
        $ds = ($vm | Get-HardDisk)[0].Filename.Split(']')[0].TrimStart('[')
        $dsObj = Get-Datastore -Name $ds -ErrorAction Stop
        $content = Get-Content -Path ("vmstore:\" + $ds + "\" + $logPath) -Raw
        $outfile = "$($VMName)_vmware.log"
        Set-Content -Path $outfile -Value $content
        Write-Log "Exported $outfile"
    } else {
        Write-Log "No vmware.log found for $VMName"
    }
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed VM log export."
