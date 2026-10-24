"""Product-specific API implementations. Author: Paul Bryant."""

from importlib import import_module

PRODUCT_MODULES = {
    "vcf_fleet": "fleet",
    "hcx": "hcx",
    "vcf_operations": "operations",
    "vcf_automation": "automation",
    "live_site_recovery": "protection_recovery",
    "vsphere_replication": "protection_recovery",
}


def module_for(component):
    name = PRODUCT_MODULES.get(component)
    return import_module(f"{__name__}.{name}") if name else None


def modules():
    return [import_module(f"{__name__}.{name}") for name in dict.fromkeys(PRODUCT_MODULES.values())]
