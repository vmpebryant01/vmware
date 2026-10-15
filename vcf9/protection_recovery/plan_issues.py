"""Export recovery plan issues metadata. Author: Paul Bryant."""

from vcf9.protection_recovery.reports import run


def main(argv=None):
    return run("plan_issues", argv)


if __name__ == "__main__":
    raise SystemExit(main())
