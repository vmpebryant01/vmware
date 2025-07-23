"""
remove_old_snapshots.py

Deletes VM snapshots older than a given number of days.
Requires: requests, python-dotenv

WARNING: Deletion is destructive! Use with caution.
"""

import os, sys, logging, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='remove_old_snapshots.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def delete_snapshot(vm_id, snapshot_id):
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm/{vm_id}/snapshots/{snapshot_id}"
    resp = session.delete(url)
    return resp.status_code == 200

def main():
    get_session()
    days = int(input("Delete snapshots older than how many days? "))
    cutoff = datetime.utcnow() - timedelta(days=days)
    vms = get_vms()
    count = 0
    for vm in vms:
        for snap in get_snapshots(vm['vm']):
            snap_time = snap.get('created', "")
            try:
                snap_date = datetime.strptime(snap_time[:19], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                continue
            if snap_date < cutoff:
                ok = delete_snapshot(vm['vm'], snap['snapshot'])
                if ok:
                    logging.info(f"Deleted snapshot {snap['name']} for VM {vm['name']}")
                    count += 1
                else:
                    logging.error(f"Failed to delete {snap['name']} for VM {vm['name']}")
    logging.info(f"Deleted {count} old snapshots.")

if __name__ == "__main__":
    main()
