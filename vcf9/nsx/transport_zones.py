"""Export transport zones metadata. Author: Paul Bryant."""

from vcf9.expanded_reports import run


def main(argv=None):
    return run("transport_zones", argv)


if __name__ == "__main__":
    raise SystemExit(main())
