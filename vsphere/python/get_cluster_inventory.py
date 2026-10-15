# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Export vSphere cluster host count, DRS, and HA configuration.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_clusters


def cluster_rows(clusters):
    rows = []
    for cluster in clusters:
        config = getattr(cluster, "configuration", None)
        drs = getattr(config, "drsConfig", None)
        ha = getattr(config, "dasConfig", None)
        rows.append((
            cluster.name,
            len(getattr(cluster, "host", None) or []),
            getattr(drs, "enabled", None),
            getattr(ha, "enabled", None),
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="cluster_inventory.csv")
    args = parser.parse_args(argv)
    with vcenter_clusters() as clusters:
        rows = cluster_rows(clusters)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "HostCount", "DRSEnabled", "HAEnabled"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} clusters to {args.csv}")


if __name__ == "__main__":
    main()
