"""Export VCF Operations adapter collection state. Author: Paul Bryant."""

from vcf9.report_core import execute, parser_for, require_items


def collect(client, _args):
    path = "/suite-api/api/adapters"
    items = require_items(client.get(path), "adapterInstancesInfoDto", path)
    rows = []
    for item in items:
        key = item.get("resourceKey") or {}
        if not isinstance(key, dict):
            key = {}
        rows.append({"id": item.get("id"), "name": key.get("name"),
                     "adapterKindKey": key.get("adapterKindKey"), "collectorId": item.get("collectorId"),
                     "collectorGroupId": item.get("collectorGroupId"), "lastCollected": item.get("lastCollected"),
                     "lastHeartbeat": item.get("lastHeartbeat"), "numberOfResourcesCollected": item.get("numberOfResourcesCollected")})
    return rows


def main(argv=None):
    parser = parser_for(__doc__, "VCF Operations")
    return execute(parser, "VCF Operations", "adapters.csv",
                   ("id", "name", "adapterKindKey", "collectorId", "collectorGroupId", "lastCollected", "lastHeartbeat", "numberOfResourcesCollected"),
                   collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
