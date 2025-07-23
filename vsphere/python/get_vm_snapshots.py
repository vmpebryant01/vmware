"""
get_vm_snapshots.py

Exports all VM snapshots with VM, name, created, description.

Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_vm_snapshots.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    logging.error("Missing environment variables.")
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.verify = False

def get_session():
    resp = session.post(
        f"https://{VCENTER_SERVER}/rest/com/vmware/cis/session",
        auth=(VCENTER_USER, VCENTER_PASS))
    if resp.status_code != 200:
        logging.error(f"Login failed: {resp.text}")
        sys.exit("Failed to login to vCenter.")
    return resp.json()['value']

def get_vms():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error(f"VMs fetch failed: {resp.text}")
        sys.exit("Failed to fetch VMs.")
    return resp.json()['value']

def get_snapshots(vm_id):
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm/{vm_id}/snapshots"
    resp = session.get(url)
    if resp.status_code != 200:
        return []
    return resp.json().get('value', [])

def main():
    get_session()
    vms = get_vms()
    outcsv = "vm_snapshots.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", "Snapshot", "Description", "Created"])
        for vm in vms:
            snaps = get_snapshots(vm['vm'])
            for snap in snaps:
                writer.writerow([
                    vm['name'],
                    snap.get('name', ""),
                    snap.get('description', ""),
                    snap.get('created', "")
                ])
    logging.info("Exported VM snapshots to vm_snapshots.csv")

if __name__ == "__main__":
    main()
