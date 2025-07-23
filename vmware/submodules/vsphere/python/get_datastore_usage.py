"""
get_datastore_usage.py

Exports all datastores with name, type, free/capacity/used space.

Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_datastore_usage.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def get_datastores():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/datastore"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error(f"Datastore fetch failed: {resp.text}")
        sys.exit("Failed to fetch datastores.")
    return resp.json()['value']

def main():
    get_session()
    ds = get_datastores()
    outcsv = "datastore_usage.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Type", "CapacityGB", "FreeGB"])
        for d in ds:
            writer.writerow([
                d.get("name", ""),
                d.get("type", ""),
                round(d.get("capacity", 0) / (1024**3), 2) if d.get("capacity") else "",
                round(d.get("free_space", 0) / (1024**3), 2) if d.get("free_space") else ""
            ])
    logging.info(f"Exported {len(ds)} datastores to {outcsv}")

if __name__ == "__main__":
    main()
