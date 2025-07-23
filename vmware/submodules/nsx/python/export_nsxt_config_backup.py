"""
export_nsxt_config_backup.py

Triggers an NSX-T manual configuration backup.
Requires: python-dotenv, requests

Note: Downloading backup file may require additional API call or browser/manual.
"""

import os, sys, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='export_nsxt_config_backup.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def trigger_backup():
    url = f"https://{NSXT_SERVER}/api/v1/cluster/backups?action=create"
    r = session.post(url, json={"backup_password": NSXT_PASS})
    if r.status_code not in [200,201]:
        logging.error(f"Failed to trigger config backup: {r.text}")
        sys.exit("Config backup trigger failed.")
    return r.json()

def main():
    backup = trigger_backup()
    logging.info("Backup triggered. Download via NSX-T Manager UI or API.")
    print("Backup triggered. Download via NSX-T Manager UI or API.")

if __name__ == "__main__":
    main()
