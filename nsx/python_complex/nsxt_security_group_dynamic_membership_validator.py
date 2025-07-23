"""
nsxt_security_group_dynamic_membership_validator.py

Audits dynamic security groups: fetches real members and flags zero-member or misconfigured groups.

Requires: python-dotenv, requests, pandas
"""

import os, sys, logging, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_group_validator.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS); session.verify = False
requests.packages.urllib3.disable_warnings()

def get_groups():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/domains/default/groups"
    r = session.get(url)
    return r.json().get("results", [])

def get_members(group_id):
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/domains/default/groups/{group_id}/members"
    r = session.get(url)
    return r.json().get("results", [])

def main():
    groups = get_groups()
    out = []
    for g in groups:
        gid = g["id"]
        expr = g.get("expression", [])
        if expr:  # dynamic group
            members = get_members(gid)
            if not members:
                out.append({"Group": g["display_name"], "Issue": "No members"})
    pd.DataFrame(out).to_csv("nsxt_dynamic_group_audit.csv", index=False)
    logging.info("Dynamic group validation done.")

if __name__ == "__main__":
    main()
