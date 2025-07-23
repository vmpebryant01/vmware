"""
get_nsxt_active_sessions.py

Exports all active NSX-T Manager sessions (user, IP, start time, role).
Requires: python-dotenv, requests

Note: API/endpoint support may vary by NSX-T version.
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_active_sessions.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_sessions():
    url = f"https://{NSXT_SERVER}/api/v1/node/sessions"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch sessions: {r.text}")
        return []
    return r.json().get("results", [])

def main():
    sessions = get_sessions()
    outcsv = "nsxt_active_sessions.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["User", "SourceIP", "StartTime", "Role"])
        for s in sessions:
            writer.writerow([
                s.get("username", ""),
                s.get("source_ip", ""),
                s.get("login_time", ""),
                s.get("role", "")
            ])
    logging.info(f"Exported {len(sessions)} active sessions to {outcsv}")

if __name__ == "__main__":
    main()
