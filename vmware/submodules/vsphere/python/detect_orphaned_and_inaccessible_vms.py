"""
detect_orphaned_and_inaccessible_vms.py

Identifies VMs in orphaned or inaccessible states.
Requires: requests, python-dotenv

Note: Full orphaned/inaccessible status may need pyVmomi.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='detect_orphaned_and_inaccessible_vms.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.verify = False

def get_session():
    resp = session.post(f"https://{VCENTER_SERVER}/rest/com/vmware/cis/session", auth=(VCENTER_USER, VCENTER_PASS))
    if resp.status_code != 200:
        logging.error("Login failed: %s", resp.text)
        sys.exit("Failed to login to vCenter.")
    return resp.json()['value']

def get_vms():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error("VM fetch failed: %s", resp.text)
        sys.exit("Failed to fetch VMs.")
    return resp.json()['value']

def main():
    get_session()
    vms = get_vms()
    outcsv = "orphaned_inaccessible_vms.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "PowerState", "StatusNote"])
        for vm in vms:
            # REST cannot directly detect orphaned/inaccessible; placeholder below.
            if vm.get("power_state", "").upper() in ["ORPHANED", "INACCESSIBLE"]:
                writer.writerow([vm.get("name", ""), vm.get("power_state", ""), "Orphaned/Inaccessible"])
    logging.info("Exported orphaned/inaccessible VM report.")

if __name__ == "__main__":
    main()
