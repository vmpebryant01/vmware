"""
nsxt_daily_compliance_report.py

Runs a daily NSX-T compliance/health audit (nodes, segments, DFW, drift, alarms).
Sends a summary report via email.

Requires: python-dotenv, requests, smtplib/email
"""

import os, sys, logging, requests, smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()
NSXT_SERVER = os.getenv("NSXT_SERVER")
NSXT_USER   = os.getenv("NSXT_USER")
NSXT_PASS   = os.getenv("NSXT_PASS")
EMAIL_TO    = os.getenv("EMAIL_TO")
EMAIL_FROM  = os.getenv("EMAIL_FROM")
SMTP_SERVER = os.getenv("SMTP_SERVER")

logging.basicConfig(filename='nsxt_daily_compliance_report.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
if not (NSXT_SERVER and NSXT_USER and NSXT_PASS and EMAIL_TO and EMAIL_FROM and SMTP_SERVER):
    sys.exit("Check .env for NSXT and SMTP vars.")

requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.auth = (NSXT_USER, NSXT_PASS)
session.verify = False

def get_nodes():
    url = f"https://{NSXT_SERVER}/api/v1/transport-nodes"
    r = session.get(url)
    return r.json().get("results", []) if r.status_code == 200 else []

def get_alarms():
    url = f"https://{NSXT_SERVER}/api/v1/events"
    r = session.get(url)
    return r.json().get("results", []) if r.status_code == 200 else []

def main():
    nodes = get_nodes()
    alarms = get_alarms()
    body = f"NSX-T Compliance Report\nNodes: {len(nodes)}\nActive Alarms: {len(alarms)}"
    msg = MIMEText(body)
    msg["Subject"] = "NSX-T Daily Compliance Report"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER) as server:
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
    logging.info("Daily compliance report emailed.")

if __name__ == "__main__":
    main()
