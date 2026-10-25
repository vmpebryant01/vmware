"""Report vSAN health and capacity observations. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="vsan_health"))
