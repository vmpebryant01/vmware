"""
set_vm_hw_version_policy.py

Checks and upgrades VMs to a minimum hardware version.
Requires: requests, python-dotenv

Note: Actual upgrade requires pyVmomi or PowerCLI.
"""

import os, sys, csv, logging
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='set_vm_hw_version_policy.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

def main():
    required_hw = input("Enter minimum HW version (e.g. vmx-14): ")
    outcsv = "hw_upgrade_candidates.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", "CurrentHW", "RequiredHW", "UpgradeRecommended"])
        writer.writerow(["(REST unsupported)", "", required_hw, "Use pyVmomi"])
    logging.info(f"VM HW version upgrade placeholder written to {outcsv}")

if __name__ == "__main__":
    main()
