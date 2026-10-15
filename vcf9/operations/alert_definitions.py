"""Export alert definitions metadata. Author: Paul Bryant."""

from vcf9.expanded_reports import run


def main(argv=None):
    return run("alert_definitions", argv)


if __name__ == "__main__":
    raise SystemExit(main())
