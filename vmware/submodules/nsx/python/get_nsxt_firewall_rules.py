"""
get_nsxt_firewall_rules.py

Exports all NSX-T distributed and gateway firewall rules.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_firewall_rules.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_dfw_rules():
    url = f"https://{NSXT_SERVER}/api/v1/firewall/sections"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch firewall sections: {r.text}")
        sys.exit("NSX-T firewall section fetch failed.")
    rules = []
    for section in r.json().get("results", []):
        secid = section["id"]
        secname = section["display_name"]
        r2 = session.get(f"https://{NSXT_SERVER}/api/v1/firewall/sections/{secid}/rules")
        if r2.status_code == 200:
            for rule in r2.json().get("results", []):
                rule["section_name"] = secname
                rules.append(rule)
    return rules

def main():
    rules = get_dfw_rules()
    outcsv = "nsxt_firewall_rules.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Section", "RuleName", "Source", "Destination", "Service", "Action", "Direction", "Logging"])
        for r in rules:
            writer.writerow([
                r.get("section_name", ""),
                r.get("display_name", ""),
                ",".join(r.get("source", {}).get("groups", [])),
                ",".join(r.get("destination", {}).get("groups", [])),
                ",".join(r.get("services", [])),
                r.get("action", ""),
                r.get("direction", ""),
                r.get("logged", "")
            ])
    logging.info(f"Exported {len(rules)} firewall rules to {outcsv}")

if __name__ == "__main__":
    main()
