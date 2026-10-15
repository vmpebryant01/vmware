# Author: Paul Bryant
<#
.SYNOPSIS
    Export pairing issues from VCF Protection and Recovery to CSV.
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
    [pscredential]$Credential,
    [pscredential]$RemoteCredential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Report-Common.ps1')
$arguments = @{ Name = 'pairing_issues'; HostName = $HostName; OutputDirectory = $OutputDirectory; Identifiers = @{pairing_id = $PairingId} }
if ($PSBoundParameters.ContainsKey('Credential')) { $arguments.Credential = $Credential }
if ($PSBoundParameters.ContainsKey('RemoteCredential')) { $arguments.RemoteCredential = $RemoteCredential }
Invoke-PublishedReport @arguments
