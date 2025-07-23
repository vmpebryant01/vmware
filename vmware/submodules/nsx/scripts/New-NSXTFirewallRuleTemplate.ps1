<#
.SYNOPSIS
    Creates a template for bulk NSX-T firewall rule automation.

.DESCRIPTION
    Outputs a CSV template for new DFW or Gateway rules, ready for mass import/automation.

.NOTES
    PowerCLI >=13.0 required.
#>
$template = @"
Section,RuleName,Source,Destination,Service,Action,Direction,Logging
Web,Allow-HTTP,WebSG,DBSG,HTTP,Allow,InOut,True
"@
$template | Out-File "NSXTFirewallRuleTemplate.csv"
Write-Host "Firewall rule template written to NSXTFirewallRuleTemplate.csv"
