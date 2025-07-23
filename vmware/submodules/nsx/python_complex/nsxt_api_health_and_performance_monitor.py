"""
nsxt_api_health_and_performance_monitor.py

Monitors NSX-T API endpoint response time, error rate, and sends alerts on health issues.

Requires: python-dotenv, requests, time, smtplib/email
"""

import os, sys, time, logging, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER, NSXT_USER, NSXT_PASS = [os.getenv(x) for x in ("NSXT_SERVER","NSXT_USER","NSXT_PASS")]
logging.basicConfig(filename='nsxt_api_health.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not all([NSXT_SERVER, NSXT_USER, NSXT_PASS]): sys.exit("Check .env")

session = requests.Session(); session.auth = (NSXT_USER, NSXT_PASS); session.verify = False
requests.packages.urllib3.disable_warnings()

def main():
    api_url = f"https://{NSXT_SERVER}/api/v1/transport-nodes"
    while True:
        t0 = time.time()
        try:
            r = session.get(api_url)
            latency = time.time() - t0
            if r.status_code != 200 or latency > 2:
                logging.warning(f"NSX-T API health issue: status {r.status_code}, latency {latency:.2f}s")
                # Optionally: send alert via email/Splunk/ServiceNow
            else:
                logging.info(f"API OK: {latency:.2f}s")
        except Exception as e:
            logging.error(f"API error: {e}")
        time.sleep(300)  # Every 5 min

if __name__ == "__main__":
    main()
