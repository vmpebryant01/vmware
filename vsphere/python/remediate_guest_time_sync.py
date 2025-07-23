"""
remediate_guest_time_sync.py

Enables or disables VMware Tools guest time sync for all VMs by policy.
Requires: requests, python-dotenv

Note: Only possible with pyVmomi.
"""

import os, sys, csv, logging
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='remediate_guest_time_sync.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

def main():
    desired = input("Enable guest time sync? (yes/no): ").lower().startswith('y')
    outcsv = "remediate_guest_time_sync.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", "RequestedAction", "Status"])
        writer.writerow(["(REST unsupported)", "Enable/Disable", "Use pyVmomi"])
    logging.info(f"Time sync report placeholder written to {outcsv}")

if __name__ == "__main__":
    main()
