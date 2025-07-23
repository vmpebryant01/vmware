<#
.SYNOPSIS
    Creates a CSV template for bulk NSX-T segment deployment.

.DESCRIPTION
    Exports a sample template with all required segment fields for automation.

.NOTES
    PowerCLI >=13.0 required.
#>
$template = @"
DisplayName,TransportZone,ReplicationMode,VlanId,Subnet
Web-Segment,Overlay-TZ,Source,10,10.10.10.0/24
"@
$template | Out-File "NSXTSegmentTemplate.csv"
Write-Host "Segment template written to NSXTSegmentTemplate.csv"
