"""
get_vcenter_audit_events.py

Downloads and summarizes vCenter audit/security events (logins, failed auth, privilege changes).
Requires: requests, python-dotenv

Note: REST event support is limited. Use pyVmomi for deep detail.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_vcenter_audit_events.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def get_events():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/event"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error(f"Event fetch failed: {resp.text}")
        return []
    return resp.json().get('value', [])

def main():
    get_session()
    outcsv = "vcenter_audit_events.csv"
    events = get_events()
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Type", "Timestamp", "Message"])
        for ev in events:
            etype = ev.get("type", "")
            if "login" in etype.lower() or "auth" in etype.lower() or "privilege" in etype.lower():
                writer.writerow([etype, ev.get("timestamp", ""), ev.get("message", "")])
    logging.info(f"Exported {len(events)} vCenter audit events to {outcsv}")

if __name__ == "__main__":
    main()
