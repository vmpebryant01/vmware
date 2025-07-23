"""
generate_vm_lifecycle_report.py

Summarizes VM creation, last power-on, last snapshot, and age.
Requires: requests, python-dotenv

Note: Some data requires pyVmomi.
"""

import os, sys, csv, logging
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='generate_vm_lifecycle_report.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

def main():
    outcsv = "vm_lifecycle_report.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", "Created", "LastPowerOn", "LastSnapshot", "AgeDays"])
        writer.writerow(["(REST unsupported)", "", "", "", ""])
    logging.info(f"VM lifecycle report placeholder written to {outcsv}")

if __name__ == "__main__":
    main()
