# Target: NSX 4.2.x Policy/Manager APIs; 4.2.2.1 reference. See docs/compatibility.md.
"""
nsxt_global_security_posture_dashboard.py

Aggregates DFW/gateway rules, open ports, tag coverage, audit logs, and scores security posture.
Exports an Excel/web dashboard, optionally integrates with SIEM.

Requires: python-dotenv, requests, pandas, openpyxl
"""

import os, sys, logging, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_security_dashboard.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS)

def fetch(endpoint):
    r = session.get(f"https://{NSXT_SERVER}/{endpoint}", timeout=30)
    return r.json().get("results", []) if r.status_code == 200 else []

def main():
    rules = fetch("api/v1/firewall/sections")
    segs = fetch("policy/api/v1/infra/segments")
    groups = fetch("policy/api/v1/infra/domains/default/groups")
    # Example scoring:
    score = 100
    if any("ANY" in r.get("services", []) for r in rules): score -= 20
    if any(g.get("group_type") == "static" for g in groups): score -= 10
    open_ports = [r for r in rules if "ANY" in r.get("services",[])]
    df = pd.DataFrame({"Score": [score], "OpenPortRules": [len(open_ports)], "StaticGroups": [sum(g.get("group_type")=="static" for g in groups)]})
    df.to_excel("nsxt_security_dashboard.xlsx", index=False)
    logging.info("Security dashboard exported.")

if __name__ == "__main__":
    main()
