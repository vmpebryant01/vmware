"""Export SDDC Manager depot synchronization status. Author: Paul Bryant."""

from vcf9.report_core import execute, parser_for, require_dict


def collect(client, _args):
    path = "/v1/system/settings/depot/depot-sync-info"
    result = require_dict(client.request_json("GET", path), path)
    return [{"syncStatus": result.get("syncStatus"),
             "lastSyncCompletionTimestamp": result.get("lastSyncCompletionTimestamp"),
             "hasError": bool(result.get("errorMessage"))}]


def main(argv=None):
    parser = parser_for(__doc__, "SDDC Manager")
    return execute(parser, "SDDC Manager", "depot_sync.csv",
                   ("syncStatus", "lastSyncCompletionTimestamp", "hasError"), collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
