"""Export NSX distributed firewall policy inventory. Author: Paul Bryant."""

import re
from urllib.parse import quote

from vcf9.report_core import cursor_items, execute, parser_for

DOMAIN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def collect(client, args):
    if not DOMAIN_ID.fullmatch(args.domain_id) or args.domain_id in (".", ".."):
        raise ValueError("--domain-id must be a simple NSX domain identifier")
    path = f"/policy/api/v1/infra/domains/{quote(args.domain_id, safe='')}/security-policies"
    items = cursor_items(client, path, {"include_rule_count": "true"})
    return [{"domain_id": args.domain_id, "id": item.get("id"), "display_name": item.get("display_name"),
             "category": item.get("category"), "sequence_number": item.get("sequence_number"),
             "rule_count": item.get("rule_count"), "_last_modified_time": item.get("_last_modified_time")}
            for item in items]


def main(argv=None):
    parser = parser_for(__doc__, "NSX Manager")
    parser.add_argument("--domain-id", required=True, help="NSX policy domain identifier")
    return execute(parser, "NSX Manager", "security_policies.csv",
                   ("domain_id", "id", "display_name", "category", "sequence_number", "rule_count", "_last_modified_time"),
                   collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
