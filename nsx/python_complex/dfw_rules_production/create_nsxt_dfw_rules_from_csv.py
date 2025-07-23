"""
create_nsxt_dfw_rules_from_csv.py

Reads a CSV of DFW rule definitions and creates rules in NSX-T Policy API (one section at a time).
- Each section is created if not present.
- Each rule is created in the target section.
- Supports: Source/Destination groups, Service(s), Action, Direction, AppliedTo, Notes, Logging.
- Skips commented lines (#).

Requires: python-dotenv, requests, pandas
"""

import os, sys, csv, logging, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

CSV_FILE = "dfw_rules_production.csv"

logging.basicConfig(filename='create_nsxt_dfw_rules.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]):
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_or_create_section(section):
    # Find section by name
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/domains/default/gateway-policies"
    s = session.get(url)
    if s.status_code != 200:
        logging.error(f"Failed to fetch DFW policies: {s.text}")
        sys.exit("Policy fetch failed")
    existing = [x for x in s.json().get("results", []) if x.get("display_name") == section]
    if existing:
        return existing[0]["id"]
    # Create section as a new gateway policy (for demo, use DFW Policy API for "default" domain)
    policy_id = section.replace(" ","-")
    create_url = f"https://{NSXT_SERVER}/policy/api/v1/infra/domains/default/gateway-policies/{policy_id}"
    body = {
        "display_name": section,
        "id": policy_id,
        "category": "Application",
        "stateful": True,
        "sequence_number": 1000  # or use default order
    }
    c = session.put(create_url, json=body)
    if c.status_code not in [200,201]:
        logging.error(f"Failed to create section {section}: {c.text}")
        sys.exit(f"Section create failed for {section}")
    return policy_id

def parse_services(services):
    # For demo: if service is built-in (HTTP, HTTPS, etc), just return as-is, else must use service path
    if not services:
        return []
    return [s.strip() for s in services.split(",") if s.strip()]

def parse_groups(grps):
    # Returns a list of NSX Policy group paths
    if not grps:
        return []
    return [f"/infra/domains/default/groups/{g.strip()}" if not g.strip().startswith("/") else g.strip() for g in grps.split(",")]

def create_rule(section_id, rule):
    rule_id = rule["RuleName"].replace(" ","-")[:30]
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/domains/default/gateway-policies/{section_id}/rules/{rule_id}"
    body = {
        "display_name": rule["RuleName"],
        "id": rule_id,
        "source_groups": parse_groups(rule["Source"]),
        "destination_groups": parse_groups(rule["Destination"]),
        "services": parse_services(rule["Service"]),
        "action": rule["Action"].upper(),
        "direction": rule["Direction"].upper(),
        "notes": rule.get("Notes",""),
        "logged": str(rule.get("Logging","")).lower() in ["true","yes","1"],
        "disabled": False,
        "sequence_number": 0,
    }
    # "applied_tos" (target) group(s)
    if rule.get("AppliedTo"):
        body["applied_tos"] = [{"target_type":"Group","target_id":g.strip()} for g in rule["AppliedTo"].split(",")]
    resp = session.put(url, json=body)
    if resp.status_code not in [200,201]:
        logging.error(f"Rule create failed for {rule['RuleName']}: {resp.text}")
        print(f"Error: {rule['RuleName']} not created ({resp.text})")
    else:
        logging.info(f"Rule created: {rule['RuleName']}")
        print(f"Rule created: {rule['RuleName']}")

def main():
    # Read CSV, skipping comments
    rules = []
    with open(CSV_FILE,"r") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in reader:
            rules.append(row)
    # Group by section
    by_section = {}
    for rule in rules:
        by_section.setdefault(rule["Section"], []).append(rule)
    # Create rules in each section
    for section, ruleset in by_section.items():
        print(f"Processing section: {section}")
        sec_id = get_or_create_section(section)
        for rule in ruleset:
            create_rule(sec_id, rule)
    print("DFW rule import complete.")

if __name__ == "__main__":
    main()
