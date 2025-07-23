"""
get_nsxt_vrf_instances.py

Exports all NSX-T VRF instances and their parent Tier-0s.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_vrf_instances.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_vrfs():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/tier-0s"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch Tier-0s: {r.text}")
        sys.exit("VRF fetch failed.")
    return [t0 for t0 in r.json().get("results", []) if t0.get("vrf_config")]

def main():
    vrfs = get_vrfs()
    outcsv = "nsxt_vrf_instances.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VRF", "ParentTier0", "Status"])
        for v in vrfs:
            writer.writerow([
                v.get("display_name", ""),
                v.get("vrf_config", {}).get("parent_tier0_path", ""),
                v.get("state", "")
            ])
    logging.info(f"Exported {len(vrfs)} VRF instances to {outcsv}")

if __name__ == "__main__":
    main()
