"""Report observed NSX firewall rule counters. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="nsx_rule_usage"))
