"""
auto_remove_stale_templates.py

Identifies VM templates not used in X months and flags (optionally deletes) them.
Requires: requests, python-dotenv

Note: Actual template removal must be done via PowerCLI or pyVmomi.
"""

import os, sys, csv, logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='auto_remove_stale_templates.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

def main():
    months = int(input("Flag templates unused in how many months? "))
    cutoff = datetime.utcnow() - timedelta(days=months*30)
    outcsv = "stale_templates.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["TemplateName", "LastDeployed", "Status"])
        writer.writerow(["(REST unsupported)", "", "Use PowerCLI/pyVmomi for logic"])
    logging.info(f"Template stale report placeholder written to {outcsv}")

if __name__ == "__main__":
    main()
