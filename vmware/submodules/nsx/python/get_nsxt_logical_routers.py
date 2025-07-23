"""
get_nsxt_logical_routers.py

Exports all Tier-0 and Tier-1 routers: name, id, type, status, edge cluster.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_logical_routers.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_routers():
    url = f"https://{NSXT_SERVER}/api/v1/logical-routers"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch routers: {r.text}")
        sys.exit("NSX-T router fetch failed.")
    return r.json()["results"]

def main():
    routers = get_routers()
    outcsv = "nsxt_logical_routers.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Id", "Type", "Status", "EdgeClusterId"])
        for r in routers:
            writer.writerow([r.get("display_name", ""),
                             r.get("id", ""),
                             r.get("router_type", ""),
                             r.get("status", ""),
                             r.get("edge_cluster_id", "")])
    logging.info(f"Exported {len(routers)} routers to {outcsv}")

if __name__ == "__main__":
    main()
