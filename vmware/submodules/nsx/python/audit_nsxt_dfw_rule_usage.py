"""
audit_nsxt_dfw_rule_usage.py

Audits NSX-T DFW rules for hit count, last used, and logs unused rules for review.
Requires: python-dotenv, requests

Note: Some fields (hit count) may require additional API endpoint or NSX-T manager UI query.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='audit_nsxt_dfw_rule_usage.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_sections():
    url = f"https://{NSXT_SERVER}/api/v1/firewall/sections"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch firewall sections: {r.text}")
        sys.exit("NSX-T firewall section fetch failed.")
    return r.json()["results"]

def main():
    sections = get_sections()
    outcsv = "nsxt_dfw_rule_usage.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Section", "RuleName", "HitCount", "LastHit"])
        for s in sections:
            secid = s["id"]
            secname = s["display_name"]
            r2 = session.get(f"https://{NSXT_SERVER}/api/v1/firewall/sections/{secid}/rules")
            if r2.status_code == 200:
                for rule in r2.json().get("results", []):
                    # Placeholder: HitCount and LastHit require additional API (not available in all NSX-T releases)
                    writer.writerow([secname, rule.get("display_name", ""), "", ""])
    logging.info(f"DFW usage audit written to {outcsv}")

if __name__ == "__main__":
    main()
