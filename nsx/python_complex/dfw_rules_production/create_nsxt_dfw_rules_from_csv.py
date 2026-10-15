# Target: NSX 4.2.x Policy/Manager APIs; 4.2.2.1 reference. See docs/compatibility.md.
"""Preview or apply NSX distributed firewall rules from a CSV file.

Author: Paul Bryant

The default mode validates and prints the plan without contacting NSX.
Use --apply only after reviewing the policy and rule order. Set NSXT_SERVER,
NSXT_USER, and NSXT_PASS in the environment or a local .env file.
"""

import argparse
import csv
from hashlib import sha1
import os
from pathlib import Path
import re
import sys


DEFAULT_CSV = Path(__file__).with_name("dfw_rules_production.csv")
REQUIRED_COLUMNS = {
    "Section", "RuleName", "Source", "Destination", "Service",
    "Action", "Direction", "AppliedTo", "Notes", "Logging",
}
VALID_ACTIONS = {"ALLOW", "DROP", "REJECT"}
VALID_DIRECTIONS = {"IN", "OUT", "IN_OUT"}


def object_id(name):
    """Make a stable path segment without collisions from truncated names."""
    prefix = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-").lower()[:48]
    if not prefix:
        raise ValueError(f"Cannot create an NSX identifier from {name!r}")
    return f"{prefix}-{sha1(name.encode('utf-8')).hexdigest()[:8]}"


def paths(value, prefix):
    """Convert CSV names to policy paths, preserving ANY and full paths."""
    names = [item.strip() for item in value.split(",") if item.strip()]
    if not names or names == ["ANY"]:
        return ["ANY"]
    if "ANY" in names:
        raise ValueError("ANY cannot be combined with named objects")
    return [name if name.startswith("/") else prefix + name for name in names]


def read_plan(csv_path):
    """Validate all rows before any API write and preserve CSV order."""
    policies = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(
            line for line in stream if line.strip() and not line.lstrip().startswith("#")
        )
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")
        for line_number, raw in enumerate(reader, start=2):
            if None in raw:
                raise ValueError(f"Extra CSV fields near row {line_number}")
            row = {key: (value or "").strip() for key, value in raw.items()}
            section = row["Section"]
            name = row["RuleName"]
            action = row["Action"].upper()
            direction = row["Direction"].upper()
            if not section or not name:
                raise ValueError(f"Section and RuleName are required near row {line_number}")
            if action not in VALID_ACTIONS or direction not in VALID_DIRECTIONS:
                raise ValueError(f"Invalid action or direction near row {line_number}")
            policy = policies.setdefault(
                section,
                {"id": object_id(section), "name": section, "rules": []},
            )
            rule_id = object_id(name)
            if any(rule["id"] == rule_id for rule in policy["rules"]):
                raise ValueError(f"Duplicate rule {name!r} in section {section!r}")
            domain_groups = "/infra/domains/default/groups/"
            body = {
                "id": rule_id,
                "resource_type": "Rule",
                "display_name": name,
                "description": row["Notes"],
                "source_groups": paths(row["Source"], domain_groups),
                "destination_groups": paths(row["Destination"], domain_groups),
                "services": paths(row["Service"], "/infra/services/"),
                "scope": paths(row["AppliedTo"], domain_groups),
                "action": action,
                "direction": direction,
                "logged": row["Logging"].lower() in {"1", "true", "yes"},
                "disabled": False,
                "sequence_number": (len(policy["rules"]) + 1) * 10,
            }
            policy["rules"].append(body)
    if not policies:
        raise ValueError("CSV contains no rules")
    return list(policies.values())


def apply_plan(plan):
    from dotenv import load_dotenv
    import requests

    load_dotenv()
    server = os.getenv("NSXT_SERVER")
    user = os.getenv("NSXT_USER")
    password = os.getenv("NSXT_PASS")
    if not all((server, user, password)):
        raise ValueError("Set NSXT_SERVER, NSXT_USER, and NSXT_PASS")
    if "/" in server or "://" in server:
        raise ValueError("NSXT_SERVER must be a hostname, without a URL path")

    session = requests.Session()
    session.auth = (user, password)
    session.verify = os.getenv("NSXT_CA_BUNDLE") or True
    base = f"https://{server}/policy/api/v1/infra/domains/default/security-policies"
    try:
        references = {
            reference
            for policy in plan
            for rule in policy["rules"]
            for field in ("source_groups", "destination_groups", "services", "scope")
            for reference in rule[field]
            if reference != "ANY"
        }
        for reference in sorted(references):
            response = session.get(f"https://{server}/policy/api/v1{reference}", timeout=30)
            response.raise_for_status()

        existing = {}
        for policy in plan:
            policy_url = f"{base}/{policy['id']}"
            response = session.get(policy_url, timeout=30)
            if response.status_code == 404:
                existing[policy["id"]] = False
            else:
                response.raise_for_status()
                if response.json().get("category") != "Application":
                    raise ValueError(f"Existing policy {policy['name']!r} is not Application")
                existing[policy["id"]] = True

        for index, policy in enumerate(plan, start=1):
            policy_url = f"{base}/{policy['id']}"
            if not existing[policy["id"]]:
                response = session.put(
                    policy_url,
                    json={
                        "id": policy["id"],
                        "resource_type": "SecurityPolicy",
                        "display_name": policy["name"],
                        "category": "Application",
                        "stateful": True,
                        "sequence_number": index * 1000,
                    },
                    timeout=30,
                )
                response.raise_for_status()
            for rule in policy["rules"]:
                rule_url = f"{policy_url}/rules/{rule['id']}"
                response = session.patch(rule_url, json=rule, timeout=30)
                response.raise_for_status()
                print(f"Applied {policy['name']} / {rule['display_name']}")
    finally:
        session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--apply", action="store_true", help="Write the validated plan to NSX")
    args = parser.parse_args(argv)
    try:
        plan = read_plan(args.csv)
        for policy in plan:
            print(f"Policy {policy['name']} ({policy['id']})")
            for rule in policy["rules"]:
                print(f"  {rule['sequence_number']}: {rule['display_name']} [{rule['action']}]")
        if args.apply:
            apply_plan(plan)
        else:
            print("Preview only. Rerun with --apply to write these rules.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
