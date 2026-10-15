"""Export collectors metadata. Author: Paul Bryant."""

from vcf9.expanded_reports import run


def main(argv=None):
    return run("collectors", argv)


if __name__ == "__main__":
    raise SystemExit(main())
