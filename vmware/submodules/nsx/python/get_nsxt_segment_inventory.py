"""
get_nsxt_segment_inventory.py

Exports all NSX-T segments, with details for inventory and compliance.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_segment_inventory.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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
    outcsv = "nsxt_segment_inventory.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "TransportZone", "VLAN", "Type", "State"])
        for s in segs:
            writer.writerow([
                s.get("display_name", ""),
                s.get("transport_zone_path", ""),
                s.get("vlan_ids", [""])[0] if "vlan_ids" in s else "",
                s.get("type", ""),
                s.get("admin_state", "")
            ])
    logging.info(f"Exported {len(segs)} segments to {outcsv}")

if __name__ == "__main__":
    main()
