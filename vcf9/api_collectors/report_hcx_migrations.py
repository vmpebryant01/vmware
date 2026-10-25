"""Report HCX migration progress and exceptions. Author: Paul Bryant."""

from vcf_inventory.reporting import main

if __name__ == "__main__":
    raise SystemExit(main(report_type="hcx_migrations"))
