# Author: Paul Bryant
<#
.SYNOPSIS
    Export segment ports from NSX Manager to CSV.
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
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$SegmentId,
    [pscredential]$Credential
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Report-Common.ps1')
$arguments = @{ Name = 'segment_ports'; HostName = $HostName; OutputDirectory = $OutputDirectory; Identifiers = @{segment_id = $SegmentId} }
if ($PSBoundParameters.ContainsKey('Credential')) { $arguments.Credential = $Credential }
Invoke-PublishedReport @arguments
