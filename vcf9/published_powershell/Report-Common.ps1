# Author: Paul Bryant
# Shared transport for the published-pattern PowerShell reports.
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot '..\PowerCLI-Common.ps1')

function Assert-ReportHost {
    param([Parameter(Mandatory)][string]$HostName)
    if ($HostName -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$' -or $HostName.Contains('..')) {
        throw 'HostName must be a DNS name or IPv4 address without a scheme or port.'
    }
}

function Assert-ReportIdentifier {
    param([Parameter(Mandatory)][string]$Value, [Parameter(Mandatory)][string]$Label)
    if ($Value -notmatch '^[A-Za-z0-9_.:-]+$' -or $Value -in @('.', '..')) {
        throw "$Label must be a simple identifier."
    }
}

function New-ReportQuery {
    param([Parameter(Mandatory)][hashtable]$Values)
    $parts = foreach ($key in $Values.Keys) {
        '{0}={1}' -f [uri]::EscapeDataString([string]$key), [uri]::EscapeDataString([string]$Values[$key])
    }
    return '?' + ($parts -join '&')
}

function Invoke-ReportRequest {
    param(
        [Parameter(Mandatory)][hashtable]$Session,
        [Parameter(Mandatory)][ValidateSet('GET', 'POST', 'DELETE')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [AllowNull()][object]$Body,
        [AllowNull()][hashtable]$AdditionalHeaders
    )
    if (-not $Path.StartsWith('/') -or $Path.StartsWith('//')) { throw 'Invalid API path.' }
    $headers = @{'Accept' = 'application/json'}
    foreach ($key in $Session.Headers.Keys) { $headers[$key] = $Session.Headers[$key] }
    if ($null -ne $AdditionalHeaders) {
        foreach ($key in $AdditionalHeaders.Keys) { $headers[$key] = $AdditionalHeaders[$key] }
    }
    $request = @{
        Uri = $Session.BaseUrl + $Path
        Method = $Method
        Headers = $headers
        MaximumRedirection = 0
        TimeoutSec = 30
        ErrorAction = 'Stop'
    }
    if ($null -ne $Body) {
        $request.Body = ConvertTo-Json -InputObject $Body -Depth 20 -Compress
        $request.ContentType = 'application/json'
    }
    elseif ($Method -eq 'POST') { $request.Body = '' }
    try {
        $response = Invoke-WebRequest @request
        if ([int]$response.StatusCode -ge 300) { throw 'Unexpected redirect or HTTP error.' }
        if ([int]$response.StatusCode -eq 204 -or [string]::IsNullOrWhiteSpace($response.Content)) {
            return [pscustomobject]@{ Data = $null }
        }
        return [pscustomobject]@{ Data = (ConvertFrom-Json -InputObject $response.Content -AsHashtable -Depth 100) }
    }
    catch {
        $status = $null
        if ($_.Exception.PSObject.Properties.Name -contains 'Response' -and $null -ne $_.Exception.Response) {
            $status = $_.Exception.Response.StatusCode
        }
        if ($null -ne $status) { throw "API $Method $($Path.Split('?')[0]) returned HTTP $([int]$status)." }
        throw "API $Method $($Path.Split('?')[0]) failed. Check the host, trust chain, and access rights."
    }
}

function Get-ReportList {
    param([Parameter(Mandatory)][object]$Response, [Parameter(Mandatory)][string]$Key, [string]$Path)
    if ($Response -isnot [System.Collections.IDictionary] -or -not $Response.Contains($Key)) {
        throw "Unexpected response from $Path."
    }
    $items = $Response[$Key]
    if ($items -isnot [array]) { throw "Unexpected $Key list from $Path." }
    foreach ($item in $items) {
        if ($item -isnot [System.Collections.IDictionary]) { throw "Unexpected list item from $Path." }
    }
    return [pscustomobject]@{ Items = $items }
}

function Get-ReportItems {
    param([Parameter(Mandatory)][hashtable]$Session, [Parameter(Mandatory)][hashtable]$Spec, [Parameter(Mandatory)][string]$Path)
    $rows = [System.Collections.Generic.List[object]]::new()
    $seen = [System.Collections.Generic.HashSet[string]]::new()
    for ($page = 0; $page -lt 1000; $page++) {
        $query = @{}
        switch ($Spec.style) {
            'cursor' {
                $query.page_size = 100
                if ($page -gt 0) { $query.cursor = $cursor }
            }
            'ops_page' { $query.page = $page; $query.pageSize = 100 }
            'sddc_page' { $query.pageNumber = $page; $query.pageSize = 100 }
            'dr_page' { $query.limit = 100; $query.offset = $rows.Count }
        }
        $requestPath = $Path
        if ($query.Count -gt 0) {
            $separator = if ($requestPath.Contains('?')) { '&' } else { '?' }
            $requestPath += (New-ReportQuery -Values $query).Replace('?', $separator)
        }
        $response = (Invoke-ReportRequest -Session $Session -Method GET -Path $requestPath).Data
        if ($Spec.style -eq 'sddc_list') {
            if ($response -isnot [array]) { throw "Unexpected list from $Path." }
            foreach ($item in $response) {
                if ($item -isnot [System.Collections.IDictionary]) { throw "Unexpected list item from $Path." }
                $rows.Add($item)
            }
            return [pscustomobject]@{ Items = $rows.ToArray() }
        }
        $key = switch ($Spec.style) {
            'cursor' { 'results' }
            'ops_page' { $Spec.key }
            'list' { $Spec.key }
            'sddc_page' { 'elements' }
            'sddc_single' { 'elements' }
            'dr_page' { 'list' }
        }
        $batch = (Get-ReportList -Response $response -Key $key -Path $Path).Items
        foreach ($item in $batch) { $rows.Add($item) }
        switch ($Spec.style) {
            'list' { return [pscustomobject]@{ Items = $rows.ToArray() } }
            'cursor' {
                $next = $response['cursor']
                if (-not $next) { return [pscustomobject]@{ Items = $rows.ToArray() } }
                if ($next -isnot [string] -or -not $seen.Add($next)) { throw "Invalid cursor from $Path." }
                $cursor = $next
            }
            'ops_page' {
                $total = $response.pageInfo.totalCount
                if ($total -isnot [long] -or $total -lt 0) { throw "Invalid page count from $Path." }
                if ($rows.Count -ge $total) { return [pscustomobject]@{ Items = $rows.ToArray() } }
                if ($batch.Count -eq 0) { throw "Empty page before expected total from $Path." }
            }
            'sddc_page' {
                $totalPages = $response.pageMetadata.totalPages
                if ($totalPages -isnot [long] -or $totalPages -lt 0 -or $totalPages -gt 1000) { throw "Invalid page count from $Path." }
                if ($page + 1 -ge $totalPages) { return [pscustomobject]@{ Items = $rows.ToArray() } }
                if ($batch.Count -eq 0) { throw "Empty page before expected total from $Path." }
            }
            'sddc_single' {
                $totalPages = $response.pageMetadata.totalPages
                if ($totalPages -notin @(0, 1)) { throw "$Path has more than one page without a documented selector." }
                return [pscustomobject]@{ Items = $rows.ToArray() }
            }
            'dr_page' {
                $meta = $response['_meta']
                if ($meta -isnot [System.Collections.IDictionary] -or $meta.total -isnot [long] -or $meta.total -lt 0 -or $meta['errors']) {
                    throw "Invalid recovery page metadata from $Path."
                }
                if ($rows.Count -gt $meta.total) { throw "Inconsistent recovery total from $Path." }
                if ($rows.Count -ge $meta.total) { return [pscustomobject]@{ Items = $rows.ToArray() } }
                if ($batch.Count -eq 0) { throw "Empty page before expected total from $Path." }
            }
        }
    }
    throw "Page limit reached for $Path."
}

function Get-ReportScalar {
    param([Parameter(Mandatory)][hashtable]$Item, [Parameter(Mandatory)][string]$Field, [Parameter(Mandatory)][hashtable]$Identifiers)
    if ($Field.StartsWith('$')) { return $Identifiers[$Field.Substring(1)] }
    if ($Field.StartsWith('#')) {
        $value = $Item[$Field.Substring(1)]
        if ($value -is [array]) { return $value.Count }
        return $null
    }
    $value = $Item
    foreach ($part in $Field.Split('.')) {
        if ($value -isnot [System.Collections.IDictionary]) { return $null }
        $value = $value[$part]
    }
    if ($null -eq $value -or $value -is [string] -or $value -is [ValueType]) { return $value }
    return $null
}

function Invoke-PublishedReport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][string]$OutputDirectory,
        [AllowNull()][pscredential]$Credential,
        [AllowNull()][pscredential]$RemoteCredential,
        [hashtable]$Identifiers = @{},
        [ValidateSet('OpsToken', 'Bearer')][string]$TokenScheme = 'OpsToken'
    )
    if ($PSVersionTable.PSVersion -lt [version]'7.4.0') { throw 'PowerShell 7.4 or later is required.' }
    Assert-ReportHost -HostName $HostName
    $catalog = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'reports.json') -Raw | ConvertFrom-Json -AsHashtable
    if (-not $catalog.reports.Contains($Name)) { throw 'Unknown report name.' }
    $spec = $catalog.reports[$Name]
    foreach ($required in $spec.required) {
        $key = $required.Replace('-', '_')
        if (-not $Identifiers.ContainsKey($key)) { throw "Missing $required." }
        Assert-ReportIdentifier -Value $Identifiers[$key] -Label $required
    }
    $path = $spec.path
    foreach ($required in $spec.required) {
        $key = $required.Replace('-', '_')
        $path = $path.Replace('{' + $key + '}', [uri]::EscapeDataString($Identifiers[$key]))
    }
    $session = @{ BaseUrl = "https://$HostName"; Headers = @{} }
    $loggedIn = $false
    try {
        switch ($spec.target) {
            'NSX Manager' {
                if ($null -eq $Credential) { $Credential = Get-Credential -Message "NSX Manager $HostName" }
                $pair = '{0}:{1}' -f $Credential.UserName, $Credential.GetNetworkCredential().Password
                $session.Headers.Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
            }
            'VCF Operations' {
                if ([string]::IsNullOrWhiteSpace($env:VCF_OPS_TOKEN)) { throw 'Set VCF_OPS_TOKEN for this process.' }
                $session.Headers.Authorization = "$TokenScheme $env:VCF_OPS_TOKEN"
            }
            'SDDC Manager' {
                if ($null -eq $Credential) { $Credential = Get-Credential -Message "SDDC Manager $HostName" }
                $body = @{ username = $Credential.UserName; password = $Credential.GetNetworkCredential().Password }
                $auth = (Invoke-ReportRequest -Session $session -Method POST -Path '/v1/tokens' -Body $body).Data
                if ($auth.accessToken -isnot [string] -or -not $auth.accessToken) { throw 'SDDC Manager did not return an access token.' }
                $session.Headers.Authorization = 'Bearer ' + $auth.accessToken
                $appliance = (Invoke-ReportRequest -Session $session -Method GET -Path '/v1/system/appliance-info').Data
                if ($appliance.role -ne 'SddcManager' -or $appliance.version -notmatch '^9\.1\.1(\.|$)') {
                    throw 'The target must be SDDC Manager 9.1.1.'
                }
            }
            'VCF Protection and Recovery' {
                $session.BaseUrl += '/api/rest/srm/v2'
                if ($null -eq $Credential) { $Credential = Get-Credential -Message "Protection and Recovery $HostName" }
                $pair = '{0}:{1}' -f $Credential.UserName, $Credential.GetNetworkCredential().Password
                $basic = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
                $auth = (Invoke-ReportRequest -Session $session -Method POST -Path '/session' -AdditionalHeaders @{Authorization = $basic}).Data
                if ($auth.session_id -isnot [string] -or $auth.session_id -match '[\r\n]' -or -not $auth.session_id) {
                    throw 'Recovery API did not return a valid session ID.'
                }
                $session.Headers['x-dr-session'] = $auth.session_id
                $loggedIn = $true
                if ($spec.required -contains 'pairing-id') {
                    if ($null -eq $RemoteCredential) { $RemoteCredential = Get-Credential -Message "Remote recovery site for $HostName" }
                    $remotePair = '{0}:{1}' -f $RemoteCredential.UserName, $RemoteCredential.GetNetworkCredential().Password
                    $remoteBasic = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remotePair))
                    $remotePath = '/pairings/' + [uri]::EscapeDataString($Identifiers.pairing_id) + '/remote-session'
                    $null = Invoke-ReportRequest -Session $session -Method POST -Path $remotePath -AdditionalHeaders @{Authorization = $remoteBasic}
                }
            }
            default { throw 'Unsupported report target.' }
        }
        $items = (Get-ReportItems -Session $session -Spec $spec -Path $path).Items
        $rows = foreach ($item in $items) {
            $values = [ordered]@{}
            for ($index = 0; $index -lt $spec.columns.Count; $index++) {
                $values[$spec.columns[$index]] = Protect-CsvText (Get-ReportScalar -Item $item -Field $spec.fields[$index] -Identifiers $Identifiers)
            }
            [pscustomobject]$values
        }
        $directory = New-ReportDirectory -Path $OutputDirectory
        $file = Join-Path $directory ($Name.Replace('/', '_') + '.csv')
        Export-ReportCsv -Path $file -Columns $spec.columns -Rows @($rows)
        Write-Output "Saved $(@($rows).Count) rows to $file"
    }
    finally {
        if ($loggedIn) {
            try { $null = Invoke-ReportRequest -Session $session -Method DELETE -Path '/session' }
            catch { Write-Warning 'Recovery API logout failed.' }
        }
        $session.Headers.Clear()
    }
}
