"""Export datastore capacity and free space from vSphere.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_datastores


def datastore_rows(datastores):
    gib = 1024 ** 3
    rows = []
    for datastore in datastores:
        summary = datastore.summary
        rows.append((
            datastore.name,
            summary.type,
            round(summary.capacity / gib, 2),
            round(summary.freeSpace / gib, 2),
            summary.accessible,
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="datastore_usage.csv")
    args = parser.parse_args(argv)
    with vcenter_datastores() as datastores:
        rows = datastore_rows(datastores)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "Type", "CapacityGiB", "FreeGiB", "Accessible"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} datastores to {args.csv}")


if __name__ == "__main__":
    main()
