#!/usr/bin/env python3
"""Collect VCF Operations resources, alerts, adapters, and policies. Author: Paul Bryant."""

from vcf_inventory.cli import main

if __name__ == "__main__":
    raise SystemExit(main(component_scope=("vcf_operations",)))
