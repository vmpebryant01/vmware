"""
tag_cloud_eligible_vms.py

Flags and exports VMs suitable for cloud migration (based on OS, size, power status).
Requires: requests, python-dotenv

Note: Tagging in vSphere REST API may be limited—this script identifies and exports; manual tagging may be needed.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='tag_cloud_eligible_vms.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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
    outcsv = "cloud_eligible_vms.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "GuestOS", "MemoryGB", "PowerState", "CloudEligible"])
        for vm in vms:
            eligible = (
                (vm.get("guest_OS","").lower().startswith("windows") or vm.get("guest_OS","").lower().startswith("linux")) and
                int(vm.get("memory_size_MiB",0)) <= 32768 and
                vm.get("power_state", "") == "POWERED_ON"
            )
            writer.writerow([vm.get("name", ""), vm.get("guest_OS", ""), int(vm.get("memory_size_MiB",0)) // 1024, vm.get("power_state", ""), "Yes" if eligible else "No"])
    logging.info(f"Exported cloud-eligible VMs to {outcsv}")

if __name__ == "__main__":
    main()
