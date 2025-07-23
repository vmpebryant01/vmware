"""
inventory_vms_by_custom_attribute.py

Exports VMs grouped by a custom attribute (app, owner, etc).
Requires: requests, python-dotenv

Note: Custom attributes access requires pyVmomi.
"""

import os, sys, csv, logging
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='inventory_vms_by_custom_attribute.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

def main():
    attr = input("Custom attribute name: ")
    outcsv = "vms_by_custom_attribute.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", attr])
        writer.writerow(["(REST unsupported)", "Use pyVmomi"])
    logging.info(f"Custom attribute inventory placeholder written to {outcsv}")

if __name__ == "__main__":
    main()
