"""Export one VCF Operations resource kind. Author: Paul Bryant."""

from vcf9.report_core import execute, page_items, parser_for


def collect(client, args):
    items = page_items(client, "/suite-api/api/resources", "resourceList", "ops", {"resourceKind": args.resource_kind})
    rows = []
    for item in items:
        key = item.get("resourceKey") or {}
        if not isinstance(key, dict):
            key = {}
        rows.append({"identifier": item.get("identifier"), "name": key.get("name"),
                     "adapterKindKey": key.get("adapterKindKey"), "resourceKindKey": key.get("resourceKindKey"),
                     "creationTime": item.get("creationTime")})
    return rows


def main(argv=None):
    parser = parser_for(__doc__, "VCF Operations")
    parser.add_argument("--resource-kind", required=True, help="Exact resource kind key, such as VirtualMachine")
    return execute(parser, "VCF Operations", "resources.csv",
                   ("identifier", "name", "adapterKindKey", "resourceKindKey", "creationTime"), collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
