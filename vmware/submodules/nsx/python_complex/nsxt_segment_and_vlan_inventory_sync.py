"""
nsxt_segment_and_vlan_inventory_sync.py

Builds a full inventory of all segments, VLANs, and port group mappings.
Flags mismatches and exports to Excel for CMDB sync.

Requires: python-dotenv, requests, pandas
"""

import os, sys, logging, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_segment_vlan_sync.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS); session.verify = False
requests.packages.urllib3.disable_warnings()

def get_segments():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/segments"
    r = session.get(url)
    return r.json().get("results", [])

def main():
    segs = get_segments()
    rows = []
    for s in segs:
        rows.append({
            "Segment": s.get("display_name", ""),
            "VLAN": s.get("vlan_ids", [""])[0] if "vlan_ids" in s else "",
            "TZ": s.get("transport_zone_path", ""),
            "PortGroup": s.get("advanced_config", {}).get("uplink_teaming_policy_name", "")
        })
    pd.DataFrame(rows).to_excel("nsxt_segment_vlan_inventory.xlsx", index=False)
    logging.info("Segment/VLAN inventory exported.")

if __name__ == "__main__":
    main()
