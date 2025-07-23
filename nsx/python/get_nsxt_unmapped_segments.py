"""
get_nsxt_unmapped_segments.py

Exports all NSX-T segments not mapped to any gateway (orphaned/unmapped).
Requires: python-dotenv, requests

Note: This is a compliance/cleanup script for unused segments.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_unmapped_segments.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_segments():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/segments"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch segments: {r.text}")
        sys.exit("NSX-T segment fetch failed.")
    return r.json()["results"]

def main():
    segs = get_segments()
    outcsv = "nsxt_unmapped_segments.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "GatewayPath"])
        for s in segs:
            if not s.get("gateway_path"):
                writer.writerow([s.get("display_name", ""), ""])
    logging.info(f"Exported unmapped segments to {outcsv}")

if __name__ == "__main__":
    main()
