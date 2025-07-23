"""
nsxt_vcenter_cmdb_depmap_enriched.py

- Maps NSX-T VMs to vCenter and CMDB for full dependency mapping
- Enriches with vCenter tags and VM notes
- Supports filtering output by AppOwner, AppName, or Environment

Requires: python-dotenv, requests, pandas, networkx, matplotlib, openpyxl
"""

import os, sys, requests, pandas as pd, logging
from dotenv import load_dotenv

try:
    import networkx as nx
    import matplotlib.pyplot as plt
except ImportError:
    print("Please install networkx and matplotlib: pip install networkx matplotlib")
    sys.exit(1)

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER   = os.getenv("VCENTER_USER")
VCENTER_PASS   = os.getenv("VCENTER_PASS")
CMDB_URL    = os.getenv("CMDB_URL")
CMDB_USER   = os.getenv("CMDB_USER")
CMDB_PASS   = os.getenv("CMDB_PASS")

logging.basicConfig(filename='nsxt_vc_cmdb_depmap_enriched.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
for v in [NSXT_SERVER, NSXT_USER, NSXT_PASS, VCENTER_SERVER, VCENTER_USER, VCENTER_PASS, CMDB_URL, CMDB_USER, CMDB_PASS]:
    if not v: sys.exit("Check .env for all NSXT/vCenter/CMDB variables.")

requests.packages.urllib3.disable_warnings()

def nsx_session():
    s = requests.Session()
    s.auth = (NSXT_USER, NSXT_PASS)
    s.verify = False
    return s

def vc_session():
    s = requests.Session()
    s.verify = False
    r = s.post(f"https://{VCENTER_SERVER}/rest/com/vmware/cis/session", auth=(VCENTER_USER, VCENTER_PASS))
    if r.status_code != 200:
        logging.error(f"vCenter login failed: {r.text}")
        sys.exit("vCenter login failed")
    return s

def cmdb_session():
    s = requests.Session()
    s.auth = (CMDB_USER, CMDB_PASS)
    s.verify = False
    return s

def get_nsx_vms(session):
    r = session.get(f"https://{NSXT_SERVER}/api/v1/fabric/virtual-machines")
    return r.json().get("results", []) if r.status_code == 200 else []

def get_segments(session):
    r = session.get(f"https://{NSXT_SERVER}/policy/api/v1/infra/segments")
    return r.json().get("results", []) if r.status_code == 200 else []

def get_vcenter_vms(vc_session):
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm"
    r = vc_session.get(url)
    if r.status_code != 200:
        logging.error(f"vCenter VM fetch failed: {r.text}")
        sys.exit("Failed to get vCenter VMs")
    return r.json()["value"]

def get_vcenter_vm_tags(vc_session, vm_id):
    # Tags: REST API v7.0+/tagging (needs tag service); fallback = ""
    tag_url = f"https://{VCENTER_SERVER}/rest/com/vmware/cis/tagging/tag-assignment?~action=list-attached-tags"
    payload = {"object_id": {"id": vm_id, "type": "VirtualMachine"}}
    r = vc_session.post(tag_url, json=payload)
    if r.status_code == 200 and r.json().get("value"):
        tag_ids = r.json()["value"]
        tags = []
        for tid in tag_ids:
            tinfo = vc_session.get(f"https://{VCENTER_SERVER}/rest/com/vmware/cis/tagging/tag/id:{tid}")
            if tinfo.status_code == 200:
                tags.append(tinfo.json().get("value", {}).get("name", tid))
        return ",".join(tags)
    return ""

def get_vcenter_vm_notes(vc_session, vm_id):
    url = f"https://{VCENTER_SERVER}/rest/vcenter/vm/{vm_id}"
    r = vc_session.get(url)
    if r.status_code == 200:
        return r.json().get("value", {}).get("notes", "")
    return ""

def get_cmdb_data(cmdb_session, vm_name):
    url = f"{CMDB_URL}/api/now/table/cmdb_ci_vmware_instance"
    r = cmdb_session.get(url, params={"name": vm_name})
    if r.status_code != 200 or not r.json().get("result"):
        return {}
    res = r.json()["result"][0]
    return {
        "AppOwner": res.get("owned_by", ""),
        "AppName": res.get("u_application", ""),
        "Environment": res.get("u_environment", ""),
        "BusinessService": res.get("business_service", ""),
    }

def get_flows(nsx_sess, vm_id, count=1000):
    url = f"https://{NSXT_SERVER}/api/v1/flow-monitoring/queries"
    query = {
        "resource_type": "FlowQuery",
        "query": {
            "start_time": 0,
            "end_time": 9999999999,
            "filters": [{
                "resource_type": "FlowFilter",
                "target": "VM",
                "field": "SOURCE",
                "value": vm_id
            }]
        },
        "page_size": count
    }
    r = nsx_sess.post(url, json=query)
    if r.status_code != 200:
        logging.warning(f"No flow data for VM {vm_id}: {r.text}")
        return []
    return r.json().get("results", [])

def filter_records(records, owner, app, env):
    def match(val, filt):
        return (not filt) or (filt.lower() in (val or "").lower())
    return [
        r for r in records
        if match(r.get("AppOwner",""), owner) and match(r.get("AppName",""), app) and match(r.get("Environment",""), env)
    ]

def main():
    s_nsx = nsx_session()
    s_vc = vc_session()
    s_cmdb = cmdb_session()

    nsx_vms = get_nsx_vms(s_nsx)
    segments = get_segments(s_nsx)
    segmap = {s["path"]: s["display_name"] for s in segments}
    vcenter_vms = get_vcenter_vms(s_vc)
    vcenter_map = {vm["instance_uuid"]: vm for vm in vcenter_vms if "instance_uuid" in vm}

    records, G = [], nx.DiGraph()
    print("Enter filter (leave blank for all):")
    owner = input("AppOwner contains: ").strip()
    app   = input("AppName contains: ").strip()
    env   = input("Environment contains: ").strip()

    for nsx_vm in nsx_vms:
        name = nsx_vm.get("display_name", nsx_vm.get("external_id", ""))
        uuid = nsx_vm.get("instance_id", "") or nsx_vm.get("external_id", "")
        seg_path = nsx_vm.get("logical_switch_id", "")
        segment = segmap.get(seg_path, seg_path)
        vc_vm = vcenter_map.get(uuid)
        if not vc_vm: continue
        vm_id = vc_vm["vm"]
        tags = get_vcenter_vm_tags(s_vc, vm_id)
        notes = get_vcenter_vm_notes(s_vc, vm_id)
        cmdb_info = get_cmdb_data(s_cmdb, vc_vm.get("name", name))
        flows = get_flows(s_nsx, nsx_vm.get("external_id", ""))
        peers = set()
        for flow in flows:
            dst_vm_id = flow.get("destination_vm_id", "")
            if dst_vm_id and dst_vm_id != nsx_vm.get("external_id", ""):
                peers.add(dst_vm_id)
                G.add_edge(name, dst_vm_id)
        record = {
            "VM": name,
            "Segment": segment,
            "vCenterName": vc_vm.get("name",""),
            "PowerState": vc_vm.get("power_state", ""),
            "CPU": vc_vm.get("cpu_count", ""),
            "MemoryMB": vc_vm.get("memory_size_MiB", ""),
            "Tags": tags,
            "Notes": notes,
            "AppOwner": cmdb_info.get("AppOwner", ""),
            "AppName": cmdb_info.get("AppName", ""),
            "Environment": cmdb_info.get("Environment", ""),
            "BusinessService": cmdb_info.get("BusinessService", ""),
            "Peers": ",".join(peers)
        }
        records.append(record)
        G.add_node(name)

    # Apply filter
    filtered = filter_records(records, owner, app, env)
    df = pd.DataFrame(filtered)
    df.to_excel("nsxt_vcenter_cmdb_depmap_filtered.xlsx", index=False)
    df.to_csv("nsxt_vcenter_cmdb_depmap_filtered.csv", index=False)
    logging.info(f"Filtered dependency map exported for {len(filtered)} VMs.")

    # Draw graph for filtered set
    plt.figure(figsize=(14,10))
    subG = G.subgraph([r["VM"] for r in filtered])
    nx.draw_networkx(subG, with_labels=True, node_size=800, node_color="lightgreen", font_size=10, edge_color="gray")
    plt.title("NSX-T + vCenter + CMDB VM Dependency Graph (Filtered)")
    plt.tight_layout()
    plt.savefig("nsxt_vcenter_cmdb_depgraph_filtered.png", dpi=200)
    plt.close()
    logging.info("Dependency graph PNG (filtered) exported.")

if __name__ == "__main__":
    main()
