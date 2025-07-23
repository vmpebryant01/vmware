"""
get_template_inventory.py

Lists all VM templates in vCenter and exports info to CSV.
Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_template_inventory.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def get_templates():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm?filter.power_states=POWERED_OFF"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error(f"Templates fetch failed: {resp.text}")
        sys.exit("Failed to fetch VMs.")
    return [vm for vm in resp.json()['value'] if vm.get("template", False)]

def main():
    get_session()
    templates = get_templates()
    outcsv = "template_inventory.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "GuestOS", "CPU", "MemoryMB", "Datastores"])
        for tmpl in templates:
            writer.writerow([
                tmpl.get("name", ""),
                tmpl.get("guest_OS", ""),
                tmpl.get("cpu_count", ""),
                tmpl.get("memory_size_MiB", ""),
                ",".join(tmpl.get("datastores", []))
            ])
    logging.info(f"Exported {len(templates)} templates to {outcsv}")

if __name__ == "__main__":
    main()
