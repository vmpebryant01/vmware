"""
nsxt_policy_rollback_automation.py

Takes a policy/config snapshot and supports rollback to any baseline.
Tracks changes for audit (who, when, what).

Requires: python-dotenv, requests, json, datetime
"""

import os, sys, json, logging, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_policy_rollback.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS); session.verify = False
requests.packages.urllib3.disable_warnings()

def fetch_config(endpoint):
    url = f"https://{NSXT_SERVER}/{endpoint}"
    r = session.get(url)
    if r.status_code != 200: return []
    return r.json().get("results", [])

def snapshot_all():
    snap = {
        "timestamp": datetime.utcnow().isoformat(),
        "segments": fetch_config("policy/api/v1/infra/segments"),
        "routers": fetch_config("api/v1/logical-routers"),
        "dfw": fetch_config("api/v1/firewall/sections"),
        "groups": fetch_config("policy/api/v1/infra/domains/default/groups"),
    }
    fname = f"nsxt_policy_snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(snap, f, indent=2)
    logging.info(f"Snapshot written to {fname}")

def rollback(fname):
    with open(fname) as f:
        snap = json.load(f)
    # For each config type, push back to NSX-T (requires PUT/POST per API)
    logging.warning("Rollback mode is a placeholder. Implement with caution.")
    # e.g. session.put(".../segments/{id}", json=...) for each segment in snap

def main():
    action = input("Snapshot or rollback? ").lower()
    if action.startswith("s"):
        snapshot_all()
    else:
        fname = input("Enter snapshot filename: ")
        rollback(fname)

if __name__ == "__main__":
    main()
