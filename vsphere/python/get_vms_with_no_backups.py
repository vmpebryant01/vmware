"""
get_vms_with_no_backups.py

Reports VMs with no backup tags or missing backup-related notes.
Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_vms_with_no_backups.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    logging.error("Missing environment variables.")
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

session = requests.Session()

def get_session():
    resp = session.post(
        f"https://{VCENTER_SERVER}/rest/com/vmware/cis/session",
        auth=(VCENTER_USER, VCENTER_PASS), timeout=30)
    if resp.status_code != 200:
        logging.error(f"Login failed: {resp.text}")
        sys.exit("Failed to login to vCenter.")
    token = resp.json()['value']
    session.headers['vmware-api-session-id'] = token
    return token

def get_vms():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm"
    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        logging.error(f"VM fetch failed: {resp.text}")
        sys.exit("Failed to fetch VMs.")
    return resp.json()['value']

def main():
    raise RuntimeError("Backup status needs a backup platform integration; this example cannot identify unprotected VMs.")
    get_session()
    vms = get_vms()
    outcsv = "vms_no_backups.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "PowerState", "Notes", "Tags"])
        for vm in vms:
            notes = vm.get("notes", "")
            # Tag fetch would require another API call per VM; left as placeholder.
            tags = ""
            if "backup" not in notes.lower():
                writer.writerow([vm.get("name", ""), vm.get("power_state", ""), notes, tags])
    logging.info(f"Exported VMs with no backup info to {outcsv}")

if __name__ == "__main__":
    main()
