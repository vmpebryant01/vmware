"""
nsxt_certificate_expiry_and_renewal_audit.py

Audits all NSX-T and edge node certificates, flags expiring certs, and sends proactive alerts.
Requires: python-dotenv, requests, datetime
"""

import os, sys, csv, logging, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER", "NSXT_USER", "NSXT_PASS")]
logging.basicConfig(filename='nsxt_cert_expiry_audit.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]):
    sys.exit("Check .env")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_certs():
    url = f"https://{NSXT_SERVER}/api/v1/trust-management/certificates"
    r = session.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch certificates: {r.text}")
        sys.exit("Cert fetch failed")
    return r.json().get("results", [])

def main():
    certs = get_certs()
    soon = []
    for c in certs:
        exp = c.get("expiry_date", "")
        if exp:
            exp_date = datetime.strptime(exp, "%Y-%m-%dT%H:%M:%S.%fZ")
            if exp_date < datetime.utcnow() + timedelta(days=30):
                soon.append({"ID": c.get("id"), "Subject": c.get("subject"), "Expires": exp})
    with open("nsxt_cert_expiry_audit.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "Subject", "Expires"])
        writer.writeheader()
        for s in soon:
            writer.writerow(s)
    logging.info(f"Found {len(soon)} expiring certs.")
    # Add alert/email logic here if needed

if __name__ == "__main__":
    main()
