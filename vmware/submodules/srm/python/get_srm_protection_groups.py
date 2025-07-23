"""
get_srm_protection_groups.py

Exports a list of all SRM protection groups.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
SRM_SERVER = os.getenv("SRM_SERVER")
SRM_USER   = os.getenv("SRM_USER")
SRM_PASS   = os.getenv("SRM_PASS")

logging.basicConfig(filename='get_srm_protection_groups.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not SRM_SERVER or not SRM_USER or not SRM_PASS:
    sys.exit("Missing SRM env vars. Check .env.")

def srm_login(): return True

def get_protection_groups():
    # TODO: Implement with SRM REST API or pyVmomi
    return [{"name": "AppGroup1", "type": "Array"}, {"name": "DBGroup", "type": "VR"}]

def main():
    srm_login()
    groups = get_protection_groups()
    outcsv = "srm_protection_groups.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Type"])
        for g in groups:
            writer.writerow([g["name"], g["type"]])
    logging.info(f"Exported protection groups to {outcsv}")

if __name__ == "__main__":
    main()
