# Author: Paul Bryant
<#
.SYNOPSIS
    Export group issues from VCF Protection and Recovery to CSV.
.DESCRIPTION
    Reads selected status and inventory fields. It does not change infrastructure.
.NOTES
    The adapted script has not been run against a live VCF 9.1.1 site.
    Source and original run evidence are listed in ../PUBLISHED_SOURCES.md.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$HostName,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$OutputDirectory,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$PairingId,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$GroupId,
    [pscredential]$Credential,
    [pscredential]$RemoteCredential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Report-Common.ps1')
$arguments = @{ Name = 'group_issues'; HostName = $HostName; OutputDirectory = $OutputDirectory; Identifiers = @{pairing_id = $PairingId; group_id = $GroupId} }
if ($PSBoundParameters.ContainsKey('Credential')) { $arguments.Credential = $Credential }
if ($PSBoundParameters.ContainsKey('RemoteCredential')) { $arguments.RemoteCredential = $RemoteCredential }
Invoke-PublishedReport @arguments
