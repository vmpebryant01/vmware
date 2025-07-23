"""
monitor_host_overcommitment.py

Checks for CPU/memory overcommitment on hosts (vCPUs/cores, Mem/phys mem).
Requires: requests, python-dotenv

For true overcommit/usage, use vROps API or pyVmomi.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='monitor_host_overcommitment.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
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

def get_vms():
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm"
    resp = session.get(url)
    if resp.status_code != 200:
        logging.error(f"VM fetch failed: {resp.text}")
        sys.exit("Failed to fetch VMs.")
    return resp.json()['value']

def main():
    get_session()
    hosts = get_hosts()
    vms = get_vms()
    outcsv = "host_overcommitment.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["HostName", "vCPUCommit", "MemCommit"])
        for host in hosts:
            vms_on_host = [vm for vm in vms if vm.get("host") == host.get("host")]
            total_vcpus = sum([vm.get("cpu_count", 0) or 0 for vm in vms_on_host])
            total_mem = sum([vm.get("memory_size_MiB", 0) or 0 for vm in vms_on_host])
            host_cores = host.get("cpu_count", 0) or 1
            host_mem = host.get("memory_size_MiB", 0) or 1
            vcpu_commit = round(total_vcpus / host_cores, 2) if host_cores else 0
            mem_commit = round(total_mem / host_mem, 2) if host_mem else 0
            writer.writerow([host.get("name", ""), vcpu_commit, mem_commit])
    logging.info(f"Exported host overcommitment data to {outcsv}")

if __name__ == "__main__":
    main()
