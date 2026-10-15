"""Export SDDC Manager service status and versions. Author: Paul Bryant."""

from vcf9.report_core import execute, parser_for


def collect(client, _args):
    return client.get_pages("/v1/vcf-services")


def main(argv=None):
    parser = parser_for(__doc__, "SDDC Manager")
    return execute(parser, "SDDC Manager", "services.csv", ("id", "name", "version", "status"), collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
