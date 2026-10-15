# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""
report_local_admin_accounts.py

Reports all ESXi host accounts (requires SSH/API access to each host).
For REST only, returns host list as local admin detail requires pyVmomi or direct SSH.

Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='report_local_admin_accounts.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def get_hosts():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/host"
    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        logging.error(f"Host fetch failed: {resp.text}")
        sys.exit("Failed to fetch hosts.")
    return resp.json()['value']

def main():
    raise RuntimeError("Local ESXi account enumeration is not implemented by this example.")
    get_session()
    hosts = get_hosts()
    outcsv = "local_admin_accounts.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["HostName", "IP", "Note"])
        for h in hosts:
            writer.writerow([h.get("name", ""), h.get("host", ""), "Requires SSH/pyVmomi for user dump"])
    logging.info(f"Exported {len(hosts)} hosts to {outcsv}")

if __name__ == "__main__":
    main()
