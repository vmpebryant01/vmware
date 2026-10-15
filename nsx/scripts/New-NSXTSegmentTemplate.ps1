<#
.SYNOPSIS
    Creates a CSV template for bulk NSX-T segment deployment.

.DESCRIPTION
    Exports a sample template with all required segment fields for automation.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$template = @"
DisplayName,TransportZone,ReplicationMode,VlanId,Subnet
Web-Segment,Overlay-TZ,Source,10,10.10.10.0/24
"@
$template | Out-File "NSXTSegmentTemplate.csv"
Write-Host "Segment template written to NSXTSegmentTemplate.csv"
