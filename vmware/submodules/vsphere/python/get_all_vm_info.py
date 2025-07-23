"""
get_all_vm_info.py

Connects to vCenter and exports a detailed VM inventory to CSV.
Requires: requests, python-dotenv
"""

import os
import sys
import csv
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_all_vm_info.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    logging.error("Missing environment variables. Check .env file.")
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

def main():
    get_session()
    vms = get_vms()
    outcsv = "all_vm_info.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "PowerState", "GuestOS", "CPU", "MemoryMB", "VMHost", "Datastores", "Tags"])
        for vm in vms:
            writer.writerow([
                vm.get("name", ""),
                vm.get("power_state", ""),
                vm.get("guest_OS", ""),
                vm.get("cpu_count", ""),
                vm.get("memory_size_MiB", ""),
                vm.get("host", ""),
                ",".join(vm.get("datastores", [])),
                ""  # Tag info requires extra API calls
            ])
    logging.info(f"Exported {len(vms)} VMs to {outcsv}")

if __name__ == "__main__":
    main()
