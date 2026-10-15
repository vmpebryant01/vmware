"""Export VCF Automation catalog item availability. Author: Paul Bryant."""

from vcf9.report_core import execute, page_items, parser_for


def collect(client, _args):
    items = page_items(client, "/catalog/api/items", "content", "automation")
    return [{"id": item.get("id"), "name": item.get("name"), "isRequestable": item.get("isRequestable"),
             "global": item.get("global"), "visibleProjectCount": len(item["projectIds"]) if isinstance(item.get("projectIds"), list) else None,
             "createdAt": item.get("createdAt"), "lastUpdatedAt": item.get("lastUpdatedAt")}
            for item in items]


def main(argv=None):
    parser = parser_for(__doc__, "VCF Automation")
    return execute(parser, "VCF Automation", "catalog.csv",
                   ("id", "name", "isRequestable", "global", "visibleProjectCount", "createdAt", "lastUpdatedAt"),
                   collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
