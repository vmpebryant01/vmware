# Author: Paul Bryant
Set-StrictMode -Version Latest

function Assert-Vcf91PowerCLI {
    if ($PSVersionTable.PSVersion -lt [version]'7.4.0') {
        throw 'PowerShell 7.4 or later is required for these VCF PowerCLI reports.'
    }
    $bundle = Get-Module -ListAvailable -Name VCF.PowerCLI |
        Where-Object { $_.Version -ge [version]'9.1.0' -and $_.Version -lt [version]'9.2.0' } |
        Sort-Object Version -Descending |
        Select-Object -First 1
    if ($null -eq $bundle) {
        throw 'Install VCF.PowerCLI 9.1.x before running this report.'
    }
    Import-Module VMware.VimAutomation.Core -MinimumVersion 13.5.0 -ErrorAction Stop
    foreach ($name in @('Connect-VIServer', 'Disconnect-VIServer', 'Get-VM')) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
            throw "VCF PowerCLI is missing the required command $name."
        }
    }
}

function Protect-CsvText {
    param([AllowNull()][object]$Value)
    if ($null -eq $Value) { return '' }
    $text = [string]$Value
    if ($text.TrimStart() -match '^[=+\-@]') { return "'$text" }
    return $text
}

function New-ReportDirectory {
    param([Parameter(Mandatory)][string]$Path)
    $resolved = [System.IO.Path]::GetFullPath($Path)
    [void](New-Item -ItemType Directory -Path $resolved -Force -ErrorAction Stop)
    return $resolved
}

function Export-ReportCsv {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string[]]$Columns,
        [AllowEmptyCollection()][object[]]$Rows
    )
    if ($null -eq $Rows -or $Rows.Count -eq 0) {
        $header = ($Columns | ForEach-Object { '"' + $_.Replace('"', '""') + '"' }) -join ','
        [System.IO.File]::WriteAllText($Path, $header + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    }
    else {
        $Rows | Export-Csv -Path $Path -NoTypeInformation -Encoding utf8
    }
}
