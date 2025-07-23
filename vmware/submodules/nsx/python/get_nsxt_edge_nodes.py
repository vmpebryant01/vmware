"""
get_nsxt_edge_nodes.py

Connects to NSX-T Manager and exports all Edge Nodes (name, ID, status, mgmt IP, role, capacity).
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_edge_nodes.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_edges():
    url = f"https://{NSXT_SERVER}/api/v1/edge-nodes"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch edge nodes: {r.text}")
        sys.exit("NSX-T edge node fetch failed.")
    return r.json()["results"]

def main():
    edges = get_edges()
    outcsv = "nsxt_edge_nodes.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "NodeId", "MgmtIp", "DeploymentType", "FormFactor"])
        for e in edges:
            writer.writerow([e.get("display_name", ""),
                             e.get("id", ""),
                             e.get("mgmt_ip_addresses", [""])[0],
                             e.get("deployment_type", ""),
                             e.get("form_factor", "")])
    logging.info(f"Exported {len(edges)} edge nodes to {outcsv}")

if __name__ == "__main__":
    main()
