"""
get_nsxt_api_version.py

Prints the NSX-T API version and build info for compliance and documentation.
Requires: python-dotenv, requests
"""

import os, sys, logging, requests
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")

logging.basicConfig(filename='get_nsxt_api_version.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not NSXT_SERVER or not NSXT_USER or not NSXT_PASS:
    sys.exit("Check .env for NSXT_SERVER, NSXT_USER, NSXT_PASS")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_version():
    url = f"https://{NSXT_SERVER}/api/v1/node/version"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch version: {r.text}")
        sys.exit("Version fetch failed.")
    return r.json()

def main():
    v = get_version()
    print(f"NSX-T API Version: {v.get('version', '')}, Build: {v.get('build_number', '')}")
    logging.info(f"API version: {v}")

if __name__ == "__main__":
    main()
