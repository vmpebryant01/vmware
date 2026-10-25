"""Report saved vCenter DNS, NTP and syslog configuration. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="management_services"))
