"""Report Operations historical performance and capacity samples. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="metric_history"))
