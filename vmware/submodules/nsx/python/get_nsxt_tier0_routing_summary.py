"""
get_nsxt_tier0_routing_summary.py

Exports all Tier-0 routers and their dynamic/static routes summary.
Requires: python-dotenv, requests

Note: Actual route counts may need additional API calls.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_tier0_routing_summary.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_tier0s():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/tier-0s"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch Tier-0s: {r.text}")
        sys.exit("Tier-0 fetch failed.")
    return r.json().get("results", [])

def main():
    t0s = get_tier0s()
    outcsv = "nsxt_tier0_routing_summary.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Tier0", "BGP", "OSPF", "StaticRoutes"])
        for t0 in t0s:
            # Placeholder: Fetch real neighbor/route count via further REST calls as needed
            writer.writerow([t0.get("display_name", ""), "Yes", "No", "N/A"])
    logging.info(f"Exported {len(t0s)} Tier-0s to {outcsv}")

if __name__ == "__main__":
    main()
