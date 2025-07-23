"""
report_expired_ssl_certificates.py

Scans vCenter and ESXi hosts for SSL certificates near expiration.
Requires: requests, python-dotenv, ssl

Note: Host cert scanning best handled with direct socket/ssl for ESXi.
"""

import os, sys, csv, logging, requests, ssl, socket
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
VCENTER_SERVER = os.getenv("VCENTER_SERVER")
VCENTER_USER = os.getenv("VCENTER_USER")
VCENTER_PASS = os.getenv("VCENTER_PASS")

logging.basicConfig(filename='report_expired_ssl_certificates.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not VCENTER_SERVER:
    sys.exit("Check .env for VCENTER_SERVER.")

def get_cert_expiry(host, port=443):
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=3) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            expires = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
            return expires
    return None

def main():
    hosts = [VCENTER_SERVER]  # Could expand with ESXi hosts via REST or inventory
    outcsv = "ssl_cert_expiry.csv"
    with open(outcsv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Host", "Expires", "DaysLeft"])
        for h in hosts:
            try:
                expires = get_cert_expiry(h)
                days = (expires - datetime.utcnow()).days
                writer.writerow([h, expires.strftime("%Y-%m-%d"), days])
            except Exception as e:
                writer.writerow([h, "Error", str(e)])
    logging.info(f"Exported cert expiry info to {outcsv}")

if __name__ == "__main__":
    main()
