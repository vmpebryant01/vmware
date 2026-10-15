# Author: Paul Bryant
<#
.SYNOPSIS
    Export collector groups from VCF Operations to CSV.
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
    [ValidateSet('OpsToken', 'Bearer')][string]$TokenScheme = 'OpsToken'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Report-Common.ps1')
$arguments = @{ Name = 'collector_groups'; HostName = $HostName; OutputDirectory = $OutputDirectory; Identifiers = @{} }
$arguments.TokenScheme = $TokenScheme
Invoke-PublishedReport @arguments
