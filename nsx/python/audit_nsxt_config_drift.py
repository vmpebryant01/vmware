"""
audit_nsxt_config_drift.py

Compares current NSX-T config with a baseline export, flags drift/new/missing objects.
Requires: python-dotenv, requests, pandas

Note: Baseline must be exported as CSV previously.
"""

import os, sys, csv, logging, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='audit_nsxt_config_drift.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_current_segments():
    url = f"https://{NSXT_SERVER}/api/v1/logical-switches"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch segments: {r.text}")
        sys.exit("NSX-T segment fetch failed.")
    return [s["display_name"] for s in r.json()["results"]]

def main():
    baseline_csv = "baseline_segments.csv"
    if not os.path.exists(baseline_csv):
        sys.exit("Baseline file not found.")
    base = pd.read_csv(baseline_csv)["Name"].tolist()
    curr = get_current_segments()
    drift = [{"Segment": s, "Status": "Missing in current"} for s in base if s not in curr]
    drift += [{"Segment": s, "Status": "New in current"} for s in curr if s not in base]
    df = pd.DataFrame(drift)
    outcsv = "nsxt_config_drift.csv"
    df.to_csv(outcsv, index=False)
    logging.info(f"Config drift report written to {outcsv}")

if __name__ == "__main__":
    main()
