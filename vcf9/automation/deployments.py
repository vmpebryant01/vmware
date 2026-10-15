"""Export VCF Automation deployment status. Author: Paul Bryant."""

from vcf9.report_core import execute, page_items, parser_for


def collect(client, _args):
    items = page_items(client, "/deployment/api/deployments", "content", "automation")
    rows = []
    for item in items:
        last_request = item.get("lastRequest")
        rows.append({"id": item.get("id"), "name": item.get("name"), "projectId": item.get("projectId"),
                     "createdAt": item.get("createdAt"), "lastUpdatedAt": item.get("lastUpdatedAt"),
                     "leaseExpireAt": item.get("leaseExpireAt"), "deleted": item.get("deleted"),
                     "lastRequestStatus": last_request.get("status") if isinstance(last_request, dict) else ""})
    return rows


def main(argv=None):
    parser = parser_for(__doc__, "VCF Automation")
    return execute(parser, "VCF Automation", "deployments.csv",
                   ("id", "name", "projectId", "createdAt", "lastUpdatedAt", "leaseExpireAt", "deleted", "lastRequestStatus"),
                   collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
