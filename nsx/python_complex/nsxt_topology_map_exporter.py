# Target: NSX 4.2.x Policy/Manager APIs; 4.2.2.1 reference. See docs/compatibility.md.
"""
nsxt_topology_map_exporter.py

Generates a topology map/graph of NSX-T segments, routers, edge nodes, and policies.
Exports to PNG/PDF.

Requires: python-dotenv, requests, graphviz/networkx
"""

import os, sys, logging, requests, graphviz
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_topology_map.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS)

def get_segments():
    r = session.get(f"https://{NSXT_SERVER}/policy/api/v1/infra/segments", timeout=30)
    return r.json().get("results", []) if r.status_code == 200 else []

def get_routers():
    r = session.get(f"https://{NSXT_SERVER}/api/v1/logical-routers", timeout=30)
    return r.json().get("results", []) if r.status_code == 200 else []

def main():
    segs = get_segments(); routers = get_routers()
    dot = graphviz.Digraph(comment='NSX-T Topology')
    for r in routers: dot.node(r.get("display_name",""), shape="doublecircle")
    for s in segs:
        dot.node(s.get("display_name","", timeout=30), shape="box")
        # Placeholder: in production, link segments to routers as per config
    # For example: dot.edge("Web-Segment", "Tier-1-Router")
    dot.render("nsxt_topology_map", format="png")
    logging.info("Topology map exported.")

if __name__ == "__main__":
    main()
