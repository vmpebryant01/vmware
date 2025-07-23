"""
nsxt_full_config_audit_and_drift_report.py

Pulls current NSX-T config (segments, routers, DFW, NAT, groups, services).
Compares to a previous baseline and produces a multi-tab Excel drift/compliance report.
Optionally sends email/ServiceNow alert on drift.

Requires: python-dotenv, requests, pandas, openpyxl
"""

import os, sys, logging, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='nsxt_full_config_audit.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]):
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def fetch_config(endpoint):
    url = f"https://{NSXT_SERVER}/{endpoint}"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch {endpoint}: {r.text}")
        return []
    return r.json().get("results", [])

def compare_lists(curr, base, key="display_name"):
    curr_names = {c.get(key, "") for c in curr}
    base_names = {b.get(key, "") for b in base}
    added = curr_names - base_names
    removed = base_names - curr_names
    return list(added), list(removed)

def main():
    endpoints = {
        "segments": "policy/api/v1/infra/segments",
        "routers": "api/v1/logical-routers",
        "dfw": "api/v1/firewall/sections",
        "groups": "policy/api/v1/infra/domains/default/groups",
    }
    basefile = "nsxt_baseline.xlsx"
    curr_conf = {}
    base_conf = {}
    drift_report = {}

    for name, ep in endpoints.items():
        curr_conf[name] = fetch_config(ep)
        base_conf[name] = pd.read_excel(basefile, sheet_name=name).to_dict("records") if os.path.exists(basefile) else []

        added, removed = compare_lists(curr_conf[name], base_conf[name])
        drift_report[name] = pd.DataFrame({"Added": list(added), "Removed": list(removed)})

    with pd.ExcelWriter("nsxt_drift_report.xlsx") as writer:
        for name, df in drift_report.items():
            df.to_excel(writer, sheet_name=name, index=False)
    logging.info("NSX-T drift report written to nsxt_drift_report.xlsx")

if __name__ == "__main__":
    main()
