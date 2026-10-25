"""Report appliance backup freshness. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="backup_freshness"))
