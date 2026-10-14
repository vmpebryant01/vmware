"""Export a point-in-time ESXi host CPU and memory usage sample.

Author: Paul Bryant
"""

import argparse
import csv
from datetime import datetime, timezone

from vsphere_inventory import vcenter_hosts


def performance_rows(hosts, collected_at):
    rows = []
    for host in hosts:
        summary = getattr(host, "summary", None)
        quick = getattr(summary, "quickStats", None)
        rows.append((
            host.name,
            collected_at,
            getattr(quick, "overallCpuUsage", None),
            getattr(quick, "overallMemoryUsage", None),
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="host_performance.csv")
    args = parser.parse_args(argv)
    collected_at = datetime.now(timezone.utc).isoformat()
    with vcenter_hosts() as hosts:
        rows = performance_rows(hosts, collected_at)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "CollectedAtUTC", "CpuUsageMHz", "MemoryUsageMB"])
        writer.writerows(rows)
    print(f"Exported usage samples for {len(rows)} hosts to {args.csv}")


if __name__ == "__main__":
    main()
