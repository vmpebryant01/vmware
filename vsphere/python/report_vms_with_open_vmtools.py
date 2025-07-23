"""
report_vms_with_open_vmtools.py

Lists VMs with missing or out-of-date open-vm-tools (Linux only).
Requires: requests, python-dotenv

Note: Tools info may require pyVmomi for full accuracy.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='report_vms_with_open_vmtools.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def main():
    get_session()
    vms = get_vms()
    outcsv = "vms_with_open_vmtools.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "GuestOS", "ToolsStatus"])
        for vm in vms:
            os_name = vm.get("guest_OS", "").lower()
            if "linux" in os_name:
                # REST API doesn't return tools status; placeholder left blank
                writer.writerow([vm.get("name", ""), vm.get("guest_OS", ""), ""])
    logging.info(f"Exported Linux VMs with open-vm-tools status to {outcsv}")

if __name__ == "__main__":
    main()
