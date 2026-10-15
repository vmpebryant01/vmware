# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Export ESXi host hardware and runtime summary fields.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_hosts


def host_rows(hosts):
    rows = []
    for host in hosts:
        summary = getattr(host, "summary", None)
        hardware = getattr(summary, "hardware", None)
        runtime = getattr(summary, "runtime", None)
        memory_bytes = getattr(hardware, "memorySize", None)
        rows.append((
            host.name,
            str(getattr(runtime, "connectionState", "")),
            str(getattr(runtime, "powerState", "")),
            getattr(hardware, "vendor", None) or "",
            getattr(hardware, "model", None) or "",
            getattr(hardware, "numCpuCores", None),
            memory_bytes // (1024 * 1024) if memory_bytes is not None else "",
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="host_summary.csv")
    args = parser.parse_args(argv)
    with vcenter_hosts() as hosts:
        rows = host_rows(hosts)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "ConnectionState", "PowerState", "Vendor", "Model", "CPUCores", "MemoryMB"])
        writer.writerows(rows)
    print(f"Exported {len(rows)} hosts to {args.csv}")


if __name__ == "__main__":
    main()
