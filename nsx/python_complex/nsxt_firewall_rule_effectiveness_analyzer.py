"""
nsxt_firewall_rule_effectiveness_analyzer.py

Analyzes NSX-T firewall rules for hit count, shadowing, and coverage.
Flags unused/shadowed rules and produces a cleanup/recommendation report.

Requires: python-dotenv, requests, pandas
"""

import os, sys, logging, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_firewall_effectiveness.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS); session.verify = False
requests.packages.urllib3.disable_warnings()

def get_dfw_rules():
    url = f"https://{NSXT_SERVER}/api/v1/firewall/sections"
    r = session.get(url); results = []
    for s in r.json().get("results", []):
        secid = s["id"]
        r2 = session.get(f"https://{NSXT_SERVER}/api/v1/firewall/sections/{secid}/rules")
        for rule in r2.json().get("results", []): rule["section"] = s["display_name"]; results.append(rule)
    return results

def main():
    rules = get_dfw_rules()
    recs = []
    for r in rules:
        hit_count = r.get("statistics", {}).get("hit_count", 0)
        shadowed = r.get("shadowing_rule", None)
        if hit_count == 0:
            recs.append({"Section": r["section"], "Rule": r["display_name"], "Action": "Remove/Review", "Reason": "Unused"})
        if shadowed:
            recs.append({"Section": r["section"], "Rule": r["display_name"], "Action": "Fix", "Reason": f"Shadowed by {shadowed}"})
    pd.DataFrame(recs).to_csv("nsxt_firewall_recommendations.csv", index=False)
    logging.info("Firewall effectiveness analysis done.")

if __name__ == "__main__":
    main()
