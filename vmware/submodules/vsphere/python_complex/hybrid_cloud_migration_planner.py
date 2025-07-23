"""
hybrid_cloud_migration_planner.py

Discovers vSphere VMs, matches with Azure/AWS/GCP.
Assesses cloud readiness, estimates migration wave/target SKU/cost.
Outputs migration plan and dashboard.

Requires: python-dotenv, requests, (cloud SDKs: azure, boto3, google-cloud)
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER   = os.getenv("VCENTER_USER")
VCENTER_PASS   = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='hybrid_cloud_migration_planner.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not VCENTER_SERVER or not VCENTER_USER or not VCENTER_PASS:
    sys.exit("Missing vCenter env vars. Check .env.")

def get_vms():
    # In production, gather from vCenter
    return [
        {"name": "WEB01", "guest_OS": "Windows Server 2016", "memory_size_MiB": 4096, "cpu_count": 2},
        {"name": "DB01",  "guest_OS": "Ubuntu Linux",        "memory_size_MiB": 8192, "cpu_count": 4},
        {"name": "APP01", "guest_OS": "Windows Server 2012", "memory_size_MiB": 16384,"cpu_count": 8}
    ]

def assess_cloud_ready(vm):
    # Simple rule: supported OS, <=32GB RAM, <=8 vCPU
    supported = any(s in vm["guest_OS"] for s in ["Windows", "Ubuntu", "Red Hat", "CentOS"])
    mem_gb = vm["memory_size_MiB"] // 1024
    ready = supported and mem_gb <= 32 and vm["cpu_count"] <= 8
    return ready

def plan_migration_wave(vm):
    # Example: critical VMs = wave 1, others wave 2
    if "DB" in vm["name"]:
        return "Wave 1"
    return "Wave 2"

def estimate_cloud_cost(vm):
    # Placeholder; use Azure/AWS pricing SDK for real estimate
    mem_gb = vm["memory_size_MiB"] // 1024
    return 100 + mem_gb * 5 + vm["cpu_count"] * 10

def main():
    vms = get_vms()
    outcsv = "hybrid_migration_plan.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["VM", "GuestOS", "MemoryGB", "CPUs", "CloudReady", "Wave", "EstCloudCostUSD"])
        for vm in vms:
            ready = assess_cloud_ready(vm)
            wave = plan_migration_wave(vm)
            cost = estimate_cloud_cost(vm)
            writer.writerow([
                vm["name"], vm["guest_OS"], vm["memory_size_MiB"] // 1024, vm["cpu_count"],
                "Yes" if ready else "No", wave, cost
            ])
    logging.info(f"Migration plan exported to {outcsv}")

if __name__ == "__main__":
    main()
