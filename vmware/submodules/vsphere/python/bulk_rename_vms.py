"""
bulk_rename_vms.py

Reads a CSV with current/desired VM names and renames VMs in vCenter.
Requires: requests, python-dotenv

Note: REST API does not currently support renaming; placeholder for pyVmomi or PowerCLI.
"""

import os, sys, csv, logging
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='bulk_rename_vms.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

def main():
    in_csv = "vm_rename_map.csv"
    out_csv = "bulk_rename_report.csv"
    # Expected: input CSV with columns old_name,new_name
    with open(in_csv, "r") as src, open(out_csv, "w", newline="") as dst:
        reader = csv.reader(src)
        writer = csv.writer(dst)
        writer.writerow(["OldName", "NewName", "Status"])
        next(reader)  # Skip header
        for row in reader:
            writer.writerow([row[0], row[1], "REST API: Not implemented (use pyVmomi)"])
    logging.info(f"Processed {in_csv}, wrote {out_csv}")

if __name__ == "__main__":
    main()
