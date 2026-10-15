"""Export NSX Tier-0 and Tier-1 gateway inventory. Author: Paul Bryant."""

from vcf9.report_core import cursor_items, execute, parser_for


def collect(client, _args):
    rows = []
    for tier in ("0", "1"):
        path = f"/policy/api/v1/infra/tier-{tier}s"
        for item in cursor_items(client, path):
            rows.append({"tier": tier, "id": item.get("id"), "display_name": item.get("display_name"),
                         "ha_mode": item.get("ha_mode"), "failover_mode": item.get("failover_mode"),
                         "tier0_path": item.get("tier0_path"), "edge_cluster_path": item.get("edge_cluster_path")})
    return rows


def main(argv=None):
    parser = parser_for(__doc__, "NSX Manager")
    return execute(parser, "NSX Manager", "gateways.csv",
                   ("tier", "id", "display_name", "ha_mode", "failover_mode", "tier0_path", "edge_cluster_path"),
                   collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
