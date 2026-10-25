"""Collect VCF Fleet Management inventory. Author: Paul Bryant."""

from vcf_inventory.cli import main

if __name__ == "__main__":
    raise SystemExit(main(component_scope={"vcf_fleet"}))
