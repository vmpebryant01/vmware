"""
get_nsxt_transport_nodes.py

Exports all NSX-T transport nodes (name, id, type, IP, status).
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_transport_nodes.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_transport_nodes():
    url = f"https://{NSXT_SERVER}/api/v1/transport-nodes"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch transport nodes: {r.text}")
        sys.exit("NSX-T transport node fetch failed.")
    return r.json()["results"]

def main():
    nodes = get_transport_nodes()
    outcsv = "nsxt_transport_nodes.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Id", "NodeType", "Ip", "Status"])
        for n in nodes:
            writer.writerow([n.get("display_name", ""),
                             n.get("id", ""),
                             n.get("node_type", ""),
                             n.get("host_switch_spec", {}).get("ip_addresses", [""])[0],
                             n.get("status", "")])
    logging.info(f"Exported {len(nodes)} transport nodes to {outcsv}")

if __name__ == "__main__":
    main()
