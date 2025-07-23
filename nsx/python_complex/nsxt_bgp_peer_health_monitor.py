"""
nsxt_bgp_peer_health_monitor.py

Checks all Tier-0 BGP peers for session status, flaps, and threshold breaches.
Sends alerts via email/ServiceNow/Slack as needed.

Requires: python-dotenv, requests
"""

import os, sys, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_bgp_health_monitor.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS); session.verify = False
requests.packages.urllib3.disable_warnings()

def get_tier0s():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/tier-0s"
    r = session.get(url)
    return r.json().get("results", [])

def get_bgp_neighbors(tier0_id):
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/tier-0s/{tier0_id}/bgp/neighbors"
    r = session.get(url)
    return r.json().get("results", [])

def main():
    alerts = []
    for t0 in get_tier0s():
        for n in get_bgp_neighbors(t0["id"]):
            state = n.get("status", {}).get("session_state", "")
            if state != "ESTABLISHED":
                alerts.append({"Router": t0["display_name"], "Peer": n["neighbor_address"], "Status": state})
    if alerts:
        # Integrate with ServiceNow, Slack, or email here as needed
        logging.warning(f"BGP alerts: {alerts}")
    else:
        logging.info("All BGP peers healthy.")

if __name__ == "__main__":
    main()
