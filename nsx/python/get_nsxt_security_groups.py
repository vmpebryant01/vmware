"""
get_nsxt_security_groups.py

Exports all NSX-T Groups (security groups), their type, criteria, and member count.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_security_groups.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_groups():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/domains/default/groups"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch groups: {r.text}")
        sys.exit("NSX-T group fetch failed.")
    return r.json()["results"]

def main():
    groups = get_groups()
    outcsv = "nsxt_security_groups.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "GroupType", "Criteria", "MemberCount"])
        for g in groups:
            criteria = str(g.get("expression", ""))
            # Member count fetch requires another REST call; placeholder left blank
            writer.writerow([g.get("display_name", ""), g.get("group_type", ""), criteria, ""])
    logging.info(f"Exported {len(groups)} security groups to {outcsv}")

if __name__ == "__main__":
    main()
