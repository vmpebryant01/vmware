"""
get_srm_protected_vms.py

Exports a list of all VMs protected by SRM.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
SRM_SERVER = os.getenv("SRM_SERVER")
SRM_USER   = os.getenv("SRM_USER")
SRM_PASS   = os.getenv("SRM_PASS")

logging.basicConfig(filename='get_srm_protected_vms.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not SRM_SERVER or not SRM_USER or not SRM_PASS:
    sys.exit("Missing SRM env vars. Check .env.")

def srm_login(): return True

def get_protected_vms():
    # TODO: Implement with SRM REST API or pyVmomi
    return [{"name": "AppVM01", "group": "AppGroup1"}, {"name": "DBVM01", "group": "DBGroup"}]

def main():
    srm_login()
    vms = get_protected_vms()
    outcsv = "srm_protected_vms.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VMName", "ProtectionGroup"])
        for vm in vms:
            writer.writerow([vm["name"], vm["group"]])
    logging.info(f"Exported protected VMs to {outcsv}")

if __name__ == "__main__":
    main()
