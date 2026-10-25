#!/usr/bin/env python3
"""Collect Live Site Recovery and vSphere Replication inventory. Author: Paul Bryant."""

from vcf_inventory.cli import main

if __name__ == "__main__":
    raise SystemExit(main(component_scope=("live_site_recovery", "vsphere_replication")))
