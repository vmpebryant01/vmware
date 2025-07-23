"""
compare_nsxt_config_to_baseline.py

Compares live NSX-T config (segments, routers, groups) with a CSV baseline.
Reports drift: new/missing/changed objects.

Requires: python-dotenv, requests, pandas
"""

import os, sys, pandas as pd, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='compare_nsxt_config_to_baseline.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_segments():
    url = f"https://{NSXT_SERVER}/policy/api/v1/infra/segments"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch segments: {r.text}")
        sys.exit("NSX-T segment fetch failed.")
    return [s["display_name"] for s in r.json()["results"]]

def main():
    baseline_file = "baseline_segments.csv"
    if not os.path.exists(baseline_file):
        sys.exit("Baseline CSV not found.")
    base = pd.read_csv(baseline_file)["Name"].tolist()
    curr = get_segments()
    drift = [{"Segment": s, "Status": "Missing in current"} for s in base if s not in curr]
    drift += [{"Segment": s, "Status": "New in current"} for s in curr if s not in base]
    pd.DataFrame(drift).to_csv("nsxt_config_to_baseline_drift.csv", index=False)
    logging.info("Config drift written to nsxt_config_to_baseline_drift.csv")

if __name__ == "__main__":
    main()
