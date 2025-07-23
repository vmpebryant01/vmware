"""
monitor_vcenter_api_health.py

Monitors vCenter REST API response time and error rate.
Requires: requests, python-dotenv
"""

import os, sys, time, logging, requests
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='monitor_vcenter_api_health.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([VCENTER_SERVER, VCENTER_USER, VCENTER_PASS]):
    sys.exit("Check .env for VCENTER_SERVER, VCENTER_USER, VCENTER_PASS.")

requests.packages.urllib3.disable_warnings()

def main():
    session = requests.Session()
    session.verify = False
    start = time.time()
    try:
        resp = session.post(f"https://{VCENTER_SERVER}/rest/com/vmware/cis/session", auth=(VCENTER_USER, VCENTER_PASS))
        elapsed = time.time() - start
        if resp.status_code == 200:
            logging.info(f"vCenter API healthy, login in {elapsed:.2f}s")
        else:
            logging.error(f"API error ({resp.status_code}): {resp.text}")
    except Exception as e:
        logging.error(f"API health check failed: {e}")

if __name__ == "__main__":
    main()
