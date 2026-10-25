#!/usr/bin/env python3
"""Collect HCX inventory. Author: Paul Bryant."""

from vcf_inventory.cli import main

if __name__ == "__main__":
    raise SystemExit(main(component_scope=("hcx",)))
