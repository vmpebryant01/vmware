"""Export VCF Operations alert metadata. Author: Paul Bryant."""

from vcf9.report_core import execute, page_items, parser_for


def collect(client, _args):
    return page_items(client, "/suite-api/api/alerts", "alerts", "ops")


def main(argv=None):
    parser = parser_for(__doc__, "VCF Operations")
    return execute(parser, "VCF Operations", "alerts.csv",
                   ("alertId", "resourceId", "alertDefinitionName", "alertLevel", "status", "startTimeUTC", "updateTimeUTC", "cancelTimeUTC"),
                   collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
