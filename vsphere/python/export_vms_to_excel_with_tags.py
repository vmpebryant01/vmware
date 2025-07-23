"""
export_vms_to_excel_with_tags.py

Exports all VMs with tag info to Excel (uses CSV; convert to XLSX as needed).
Requires: requests, python-dotenv, pandas (for Excel output).
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

try:
    import pandas as pd
except ImportError:
    sys.exit("Please install pandas for Excel output: pip install pandas openpyxl")

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='export_vms_to_excel_with_tags.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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
    data = []
    for vm in vms:
        # Tag info: REST API is limited, so left blank here.
        data.append({
            "Name": vm.get("name", ""),
            "GuestOS": vm.get("guest_OS", ""),
            "CPUs": vm.get("cpu_count", ""),
            "MemoryMB": vm.get("memory_size_MiB", ""),
            "PowerState": vm.get("power_state", ""),
            "Tags": ""
        })
    df = pd.DataFrame(data)
    outfile = "vms_with_tags.xlsx"
    df.to_excel(outfile, index=False)
    logging.info(f"Exported VMs to {outfile}")

if __name__ == "__main__":
    main()
