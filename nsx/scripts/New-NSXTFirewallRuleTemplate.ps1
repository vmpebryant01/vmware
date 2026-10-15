<#
.SYNOPSIS
    Creates a template for bulk NSX-T firewall rule automation.

.DESCRIPTION
    Outputs a CSV template for new DFW or Gateway rules, ready for mass import/automation.

.NOTES
    Target: NSX 4.2.x with VMware.PowerCLI 13.x (13.3 reference). See docs/compatibility.md.
#>
$template = @"
Section,RuleName,Source,Destination,Service,Action,Direction,Logging
Web,Allow-HTTP,WebSG,DBSG,HTTP,Allow,InOut,True
"@
$template | Out-File "NSXTFirewallRuleTemplate.csv"
Write-Host "Firewall rule template written to NSXTFirewallRuleTemplate.csv"
