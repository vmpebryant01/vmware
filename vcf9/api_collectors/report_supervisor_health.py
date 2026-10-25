"""Report saved Supervisor state and namespace quotas. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="supervisor_health"))
