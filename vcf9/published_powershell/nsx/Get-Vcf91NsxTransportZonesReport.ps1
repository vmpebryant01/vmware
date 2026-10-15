# Author: Paul Bryant
<#
.SYNOPSIS
    Export transport zones from NSX Manager to CSV.
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
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$SiteId,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$EnforcementPointId,
    [pscredential]$Credential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Report-Common.ps1')
$arguments = @{ Name = 'transport_zones'; HostName = $HostName; OutputDirectory = $OutputDirectory; Identifiers = @{site_id = $SiteId; enforcement_point_id = $EnforcementPointId} }
if ($PSBoundParameters.ContainsKey('Credential')) { $arguments.Credential = $Credential }
Invoke-PublishedReport @arguments
