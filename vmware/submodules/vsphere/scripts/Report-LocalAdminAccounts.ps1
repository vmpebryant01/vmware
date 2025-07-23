<#
.SYNOPSIS
    List ESXi local admin/root accounts, last login, expiration, and lockout.

.DESCRIPTION
    Exports account details for all hosts (root, other admin), with last login, lockout, expiration.
    Logs actions.

.NOTES
    PowerCLI >=13.0 required.
    Requires host root access.
#>
$vcServer = Read-Host "Enter vCenter FQDN/IP"
$vcUser = Read-Host "Enter vCenter username"
$vcPass = Read-Host "Enter vCenter password" -AsSecureString

$LogPath = "Report-LocalAdminAccounts.log"
function Write-Log($msg) { $timestamp = Get-Date -Format o; "$timestamp $msg" | Out-File $LogPath -Append }
Write-Log "Auditing ESXi local admin accounts..."

try {
    Connect-VIServer -Server $vcServer -User $vcUser -Password $vcPass -ErrorAction Stop
    Write-Log "Connected to $vcServer"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }

try {
    $hosts = Get-VMHost
    $report = foreach ($host in $hosts) {
        $esxcli = Get-EsxCli -VMHost $host
        $users = $esxcli.system.account.list() | Where-Object { $_.User -eq "root" -or $_.Admin -eq "true" }
        foreach ($user in $users) {
            [PSCustomObject]@{
                Host       = $host.Name
                User       = $user.User
                Admin      = $user.Admin
                LastLogin  = $user.LastLogin
                Expiration = $user.PasswordExpiration
                Locked     = $user.Locked
            }
        }
    }
    $OutFile = "ESXiAdminAccounts_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
    $report | Export-Csv -NoTypeInformation -Path $OutFile
    Write-Log "Exported local admin account report to $OutFile"
} catch { Write-Log "ERROR: $($_.Exception.Message)"; throw }
finally { Disconnect-VIServer -Server $vcServer -Confirm:$false; Write-Log "Disconnected." }
Write-Log "Completed account audit."
