"""
get_expired_snapshots.py

Finds all VM snapshots older than a given threshold (days).
Exports to CSV.

Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_expired_snapshots.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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
        logging.error(f"VM fetch failed: {resp.text}")
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
    days = int(input("Enter days threshold for expired snapshots: "))
    cutoff = datetime.utcnow() - timedelta(days=days)
    vms = get_vms()
    outcsv = "expired_snapshots.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", "Snapshot", "Created"])
        for vm in vms:
            for snap in get_snapshots(vm['vm']):
                snap_time = snap.get('created', "")
                try:
                    snap_date = datetime.strptime(snap_time[:19], "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    continue
                if snap_date < cutoff:
                    writer.writerow([vm['name'], snap.get('name', ""), snap_time])
    logging.info(f"Exported expired snapshots to {outcsv}")

if __name__ == "__main__":
    main()
