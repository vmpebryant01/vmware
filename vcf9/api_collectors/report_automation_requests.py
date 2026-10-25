"""Report VCF Automation deployment request exceptions. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="automation_requests"))
