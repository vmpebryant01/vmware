"""
get_nsxt_events_and_alarms.py

Exports NSX-T events and alarms from the last N days for audit and compliance.
Requires: python-dotenv, requests

Note: Event API support may vary by NSX-T release.
"""

import os, sys, csv, logging, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_events_and_alarms.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_events():
    url = f"https://{NSXT_SERVER}/api/v1/events"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch events: {r.text}")
        return []
    return r.json().get("results", [])

def main():
    events = get_events()
    outcsv = "nsxt_events_and_alarms.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Time", "Type", "Severity", "Node", "Message"])
        for e in events:
            writer.writerow([
                e.get("event_time", ""),
                e.get("event_type", ""),
                e.get("severity", ""),
                e.get("node_id", ""),
                e.get("event_description", "")
            ])
    logging.info(f"Exported {len(events)} events/alarms to {outcsv}")

if __name__ == "__main__":
    main()
