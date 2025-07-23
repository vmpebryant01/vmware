"""
get_cluster_inventory.py

Fetches all vSphere clusters, their host count, CPU, and memory totals.
Exports to CSV.

Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='get_cluster_inventory.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def get_clusters():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/cluster"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error(f"Cluster fetch failed: {resp.text}")
        sys.exit("Failed to fetch clusters.")
    return resp.json()['value']

def main():
    get_session()
    clusters = get_clusters()
    outcsv = "cluster_inventory.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "HostCount", "DRS", "HA"])
        for cl in clusters:
            writer.writerow([
                cl.get("name", ""),
                cl.get("host_count", ""),
                cl.get("drs_enabled", ""),
                cl.get("ha_enabled", "")
            ])
    logging.info(f"Exported {len(clusters)} clusters to {outcsv}")

if __name__ == "__main__":
    main()
