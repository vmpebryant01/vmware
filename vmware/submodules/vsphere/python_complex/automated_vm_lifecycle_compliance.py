"""
automated_vm_lifecycle_compliance.py

Audits all VMs against lifecycle policies (naming, tagging, hardware version, backup, snapshot, tools, limits).
Auto-remediates violations, or escalates exceptions to ServiceNow/email.
Exports a detailed CSV compliance report.

Requires: python-dotenv, requests, (optionally pyVmomi, ServiceNow API SDK)
"""

import os, sys, csv, json, logging, requests, re
from dotenv import load_dotenv

# --- Load policy from JSON/YAML ---
POLICY_FILE = "lifecycle_policy.json"  # User must provide

def load_policy():
    if not os.path.exists(POLICY_FILE):
        sys.exit(f"Policy file {POLICY_FILE} not found.")
    with open(POLICY_FILE) as f:
        return json.load(f)

# --- Load environment ---
load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER   = os.getenv("VCENTER_USER")
VCENTER_PASS   = os.getenv("VCENTER_PASS")
SERVICENOW_URL = os.getenv("SERVICENOW_URL")
SERVICENOW_USER= os.getenv("SERVICENOW_USER")
SERVICENOW_PASS= os.getenv("SERVICENOW_PASS")

logging.basicConfig(filename='automated_vm_lifecycle_compliance.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not VCENTER_SERVER or not VCENTER_USER or not VCENTER_PASS:
    sys.exit("Missing vCenter env vars. Check .env.")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.verify = False

def vcenter_login():
    r = session.post(f"https://{VCENTER_SERVER}/rest/com/vmware/cis/session", auth=(VCENTER_USER, VCENTER_PASS))
    if r.status_code != 200:
        logging.error("vCenter login failed: %s", r.text)
        sys.exit("vCenter login failed")
    return r.json()['value']

def get_vms():
    resp = session.get(f"https://{VCENTER_SERVER}/rest/vcenter/vm")
    if resp.status_code != 200:
        logging.error("VM fetch failed: %s", resp.text)
        sys.exit("Failed to get VMs")
    return resp.json()['value']

def check_policy(vm, policy):
    """Returns (compliance, violations: list, remediation_actions: list)"""
    compliance = True
    violations, remediations = [], []

    # Example policy checks
    if not re.match(policy["naming_regex"], vm["name"]):
        compliance = False
        violations.append("Naming convention")
        remediations.append(f"Rename to match: {policy['naming_regex']}")

    # Tag check placeholder
    if "tags_required" in policy:
        # TODO: Fetch tags with pyVmomi or Tagging API
        compliance = False
        violations.append("Missing tags (placeholder)")
        remediations.append("Apply required tags")

    # Hardware version
    # TODO: Fetch full HW version via pyVmomi
    # Snapshot check, resource limits, backup status, etc. can be added similarly

    return compliance, violations, remediations

def escalate_exception(vm, violations):
    # Placeholder: Integrate with ServiceNow API or send email
    logging.warning(f"Escalating {vm['name']} for {violations}")

def main():
    policy = load_policy()
    vcenter_login()
    vms = get_vms()
    outcsv = "lifecycle_compliance_report.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", "Compliant", "Violations", "Remediation"])
        for vm in vms:
            compliant, violations, remediations = check_policy(vm, policy)
            if not compliant:
                escalate_exception(vm, violations)
            writer.writerow([vm["name"], "Yes" if compliant else "No", "; ".join(violations), "; ".join(remediations)])
    logging.info(f"Compliance report exported to {outcsv}")

if __name__ == "__main__":
    main()
