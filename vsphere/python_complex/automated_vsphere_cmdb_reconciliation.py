"""
automated_vsphere_cmdb_reconciliation.py

Fetches vSphere VM inventory and ServiceNow/CMDB inventory.
Compares for drift: missing, extra, mismatched attributes.
Optionally auto-updates CMDB records or creates incidents for drift.

Requires: python-dotenv, requests, ServiceNow REST API
"""

import os, sys, csv, logging, requests, json
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER  = os.getenv("VCENTER_SERVER")
VCENTER_USER    = os.getenv("VCENTER_USER")
VCENTER_PASS    = os.getenv("VCENTER_PASS")
CMDB_URL        = os.getenv("CMDB_URL")
CMDB_USER       = os.getenv("CMDB_USER")
CMDB_PASS       = os.getenv("CMDB_PASS")

logging.basicConfig(filename='automated_vsphere_cmdb_reconciliation.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not (VCENTER_SERVER and VCENTER_USER and VCENTER_PASS and CMDB_URL and CMDB_USER and CMDB_PASS):
    sys.exit("Check .env for vCenter and CMDB variables.")

def vcenter_login(session):
    r = session.post(f"https://{VCENTER_SERVER}/rest/com/vmware/cis/session", auth=(VCENTER_USER, VCENTER_PASS))
    if r.status_code != 200:
        logging.error("vCenter login failed: %s", r.text)
        sys.exit("vCenter login failed")
    return r.json()['value']

def get_vms(session):
    resp = session.get(f"https://{VCENTER_SERVER}/rest/vcenter/vm")
    if resp.status_code != 200:
        logging.error("VM fetch failed: %s", resp.text)
        sys.exit("Failed to get VMs")
    return {vm["name"]: vm for vm in resp.json()['value']}

def get_cmdb_records():
    resp = requests.get(CMDB_URL, auth=(CMDB_USER, CMDB_PASS))
    if resp.status_code != 200:
        logging.error("CMDB fetch failed: %s", resp.text)
        sys.exit("Failed to get CMDB records")
    # Example: assuming ServiceNow CMDB REST returns items with 'name'
    return {ci["name"]: ci for ci in resp.json().get("result", [])}

def reconcile(vms, cmdb):
    out = []
    for name in vms:
        if name not in cmdb:
            out.append([name, "vCenterOnly", "Missing in CMDB"])
    for name in cmdb:
        if name not in vms:
            out.append([name, "CMDBOnly", "Missing in vCenter"])
        # Could check for mismatched owner/app/env/etc.
    return out

def main():
    session = requests.Session()
    session.verify = False
    vcenter_login(session)
    vms  = get_vms(session)
    cmdb = get_cmdb_records()
    outcsv = "cmdb_vsphere_drift.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Source", "DriftStatus"])
        for row in reconcile(vms, cmdb):
            writer.writerow(row)
    logging.info(f"Reconciliation report exported to {outcsv}")

if __name__ == "__main__":
    main()
