"""
srm_servicenow_integration.py

Integrates SRM protection/failover events with ServiceNow for ticketing/compliance.
Pushes new events/incidents to ServiceNow via REST API.

Requires: python-dotenv, requests
"""

import os, sys, logging, requests
from dotenv import load_dotenv

load_dotenv()
SRM_SERVER   = os.getenv("SRM_SERVER")
SRM_USER     = os.getenv("SRM_USER")
SRM_PASS     = os.getenv("SRM_PASS")
SERVICENOW_URL = os.getenv("SERVICENOW_URL")
SERVICENOW_USER= os.getenv("SERVICENOW_USER")
SERVICENOW_PASS= os.getenv("SERVICENOW_PASS")

logging.basicConfig(filename='srm_servicenow_integration.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
for v in [SRM_SERVER, SRM_USER, SRM_PASS, SERVICENOW_URL, SERVICENOW_USER, SERVICENOW_PASS]:
    if not v:
        sys.exit("Missing env vars. Check .env.")

def create_snow_incident(short_desc, desc):
    resp = requests.post(
        f"{SERVICENOW_URL}/api/now/table/incident",
        auth=(SERVICENOW_USER, SERVICENOW_PASS),
        json={"short_description": short_desc, "description": desc})
    if resp.status_code not in [200,201]:
        logging.error(f"Failed to create SNOW incident: {resp.text}")
    else:
        logging.info(f"SNOW incident created: {resp.json().get('result', {}).get('number')}")

def main():
    # TODO: Get SRM events (failover, protection, test)
    event = {"type": "FailoverTest", "group": "AppGroup1", "status": "Success", "time": "2024-07-01T08:00:00"}
    short_desc = f"SRM Event: {event['type']} for {event['group']}"
    desc = f"Event details: {event}"
    create_snow_incident(short_desc, desc)
    print("ServiceNow incident submitted.")

if __name__ == "__main__":
    main()
