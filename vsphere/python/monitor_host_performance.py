"""
monitor_host_performance.py

Exports basic ESXi host hardware info. For deep performance metrics, pyVmomi or vROps API required.

Requires: requests, python-dotenv
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='monitor_host_performance.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def get_hosts():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/host"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error(f"Host fetch failed: {resp.text}")
        sys.exit("Failed to fetch hosts.")
    return resp.json()['value']

def main():
    get_session()
    hosts = get_hosts()
    outcsv = "host_performance.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "CPU", "MemoryMB", "Status"])
        for h in hosts:
            writer.writerow([h.get("name", ""), h.get("cpu_count", ""), h.get("memory_size_MiB", ""), h.get("connection_state", "")])
    logging.info(f"Exported {len(hosts)} hosts to {outcsv}")

if __name__ == "__main__":
    main()
