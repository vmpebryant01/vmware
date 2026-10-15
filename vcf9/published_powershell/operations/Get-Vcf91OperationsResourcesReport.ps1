# Author: Paul Bryant
<#
.SYNOPSIS
    Export one resource kind from VCF Operations to CSV.
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
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$ResourceKind,
    [ValidateSet('OpsToken', 'Bearer')][string]$TokenScheme = 'OpsToken'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\Report-Common.ps1')
$arguments = @{ Name = 'resources'; HostName = $HostName; OutputDirectory = $OutputDirectory; Identifiers = @{ resource_kind = $ResourceKind } }
$arguments.TokenScheme = $TokenScheme

Invoke-PublishedReport @arguments
