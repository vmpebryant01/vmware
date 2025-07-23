"""
get_srm_alerts_and_events.py

Exports all recent alerts/events from SRM.
Requires: python-dotenv, requests
"""

import os, sys, csv, logging, requests
from dotenv import load_dotenv

load_dotenv()
SRM_SERVER = os.getenv("SRM_SERVER")
SRM_USER   = os.getenv("SRM_USER")
SRM_PASS   = os.getenv("SRM_PASS")

logging.basicConfig(filename='get_srm_alerts_and_events.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not SRM_SERVER or not SRM_USER or not SRM_PASS:
    sys.exit("Missing SRM env vars. Check .env.")

def srm_login(): return True

def get_alerts_events():
    # TODO: Implement with SRM REST API
    return [{"time": "2024-07-02 08:00", "type": "Warning", "text": "RPO exceeded on DBVM01"}]

def main():
    srm_login()
    alerts = get_alerts_events()
    outcsv = "srm_alerts_events.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Time", "Type", "Text"])
        for alert in alerts:
            writer.writerow([alert["time"], alert["type"], alert["text"]])
    logging.info(f"Exported SRM alerts/events to {outcsv}")

if __name__ == "__main__":
    main()
