"""Read-only SDDC Manager 9.1.x certificate and task reports. Author: Paul Bryant."""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from .sddc_inventory import SddcClient, ensure_vcf91, write_csv


CERTIFICATE_COLUMNS = (
    "domain", "resourceType", "resourceName", "issuedTo", "notAfter",
    "numberOfDaysToExpire", "expirationStatus", "isInstalled", "autoRenew",
    "autoRenewStatus", "attention",
)
TASK_COLUMNS = ("id", "name", "type", "status", "creationTimestamp", "completionTimestamp", "resolutionStatus")


def bounded_days(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Enter a whole number of days") from exc
    if number < 1 or number > 3650:
        raise argparse.ArgumentTypeError("Days must be between 1 and 3650")
    return number


def certificate_row(domain_name: str, certificate: dict, expires_within: int) -> dict:
    days = certificate.get("numberOfDaysToExpire")
    days_remaining = days if isinstance(days, int) and not isinstance(days, bool) else None
    status = str(certificate.get("expirationStatus") or "").upper()
    installed = certificate.get("isInstalled") is True
    attention = installed and (
        status in {"EXPIRED", "ABOUT_TO_EXPIRE"}
        or (days_remaining is not None and days_remaining <= expires_within)
    )
    return {
        "domain": domain_name,
        "resourceType": certificate.get("resourceType"),
        "resourceName": certificate.get("resourceName"),
        "issuedTo": certificate.get("issuedTo"),
        "notAfter": certificate.get("notAfter"),
        "numberOfDaysToExpire": days_remaining,
        "expirationStatus": certificate.get("expirationStatus"),
        "isInstalled": certificate.get("isInstalled"),
        "autoRenew": certificate.get("autoRenew"),
        "autoRenewStatus": certificate.get("autoRenewStatus"),
        "attention": attention,
    }


def collect_health(
    client: SddcClient, *, days: int, expires_within: int, now: datetime | None = None
) -> dict[str, object]:
    appliance = ensure_vcf91(client)
    certificates = []
    for domain in client.get_pages("/v1/domains"):
        domain_id = domain.get("id")
        if not isinstance(domain_id, str) or not domain_id:
            raise RuntimeError("A domain is missing its ID")
        path = f"/v1/domains/{quote(domain_id, safe='')}/resource-certificates"
        for certificate in client.get_pages(path):
            certificates.append(certificate_row(str(domain.get("name") or domain_id), certificate, expires_within))

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Current time must include a time zone")
    completed_after = int((current - timedelta(days=days)).timestamp() * 1000)
    tasks = client.get_pages("/v1/tasks", filters={"completedAfter": completed_after})
    failed_tasks = [
        {column: task.get(column) for column in TASK_COLUMNS}
        for task in tasks
        if str(task.get("status") or "").upper() == "FAILED"
    ]
    return {
        "appliance": appliance,
        "collected_utc": current.astimezone(timezone.utc).isoformat(),
        "completed_after": completed_after,
        "expires_within": expires_within,
        "certificates": certificates,
        "failed_tasks": failed_tasks,
    }


def export_health(report: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "report_info.csv",
        ("applianceVersion", "collectedUtc", "tasksCompletedAfterEpochMs", "certificateAttentionDays"),
        [{
            "applianceVersion": report["appliance"].get("version"),
            "collectedUtc": report["collected_utc"],
            "tasksCompletedAfterEpochMs": report["completed_after"],
            "certificateAttentionDays": report["expires_within"],
        }],
    )
    certificates = report["certificates"]
    write_csv(output_dir / "certificates.csv", CERTIFICATE_COLUMNS, certificates)
    write_csv(
        output_dir / "certificate_attention.csv",
        CERTIFICATE_COLUMNS,
        [row for row in certificates if row["attention"]],
    )
    write_csv(output_dir / "failed_tasks.csv", TASK_COLUMNS, report["failed_tasks"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="SDDC Manager DNS name or IPv4 address")
    parser.add_argument("--username", required=True, help="SDDC Manager user name")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ca-bundle", help="PEM file containing the trusted issuing CA")
    parser.add_argument("--days", type=bounded_days, default=30, help="Recent task window (default: 30)")
    parser.add_argument("--expires-within", type=bounded_days, default=60, help="Certificate attention window (default: 60)")
    args = parser.parse_args(argv)
    try:
        client = SddcClient(args.host, args.ca_bundle)
        password = getpass.getpass("SDDC Manager password: ")
        client.authenticate(args.username, password)
        del password
        try:
            report = collect_health(client, days=args.days, expires_within=args.expires_within)
        finally:
            client.access_token = None
        export_health(report, args.output_dir)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Saved four CSV reports in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
