# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""
audit_vm_encryption.py

Reports VM encryption status, storage policy, and vTPM presence.
Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='audit_vm_encryption.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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
    raise RuntimeError("Encryption, storage policy, and vTPM fields are not collected by this example.")
    get_session()
    vms = get_vms()
    outcsv = "vm_encryption_audit.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Encrypted", "StoragePolicy", "vTPM"])
        for vm in vms:
            # Encryption status, policy, vTPM presence require deeper query (pyVmomi recommended).
            # Here, output placeholders.
            writer.writerow([vm.get("name", ""), "", "", ""])
    logging.info(f"Exported {len(vms)} VMs to {outcsv}")

if __name__ == "__main__":
    main()
