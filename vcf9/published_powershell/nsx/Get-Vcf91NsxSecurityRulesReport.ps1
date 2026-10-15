# Author: Paul Bryant
<#
.SYNOPSIS
    Export security rules from NSX Manager to CSV.
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
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$DomainId,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$PolicyId,
    [pscredential]$Credential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Report-Common.ps1')
$arguments = @{ Name = 'security_rules'; HostName = $HostName; OutputDirectory = $OutputDirectory; Identifiers = @{domain_id = $DomainId; policy_id = $PolicyId} }
if ($PSBoundParameters.ContainsKey('Credential')) { $arguments.Credential = $Credential }
Invoke-PublishedReport @arguments
