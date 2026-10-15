# Target: vSphere 8.x API generation; vCenter 8.0 Update 3 reference. See docs/compatibility.md.
"""Export provisioned vCPU and memory ratios for ESXi hosts.

Author: Paul Bryant
"""

import argparse
import csv

from vsphere_inventory import vcenter_hosts


def commitment_rows(hosts):
    rows = []
    for host in hosts:
        hardware = getattr(host, "hardware", None)
        cpu_info = getattr(hardware, "cpuInfo", None)
        cores = getattr(cpu_info, "numCpuCores", None)
        memory_bytes = getattr(hardware, "memorySize", None)
        if not cores or not memory_bytes:
            raise ValueError(f"Missing physical capacity for host {host.name!r}")
        vcpus = 0
        memory_mib = 0
        for vm in getattr(host, "vm", None) or []:
            config = getattr(vm, "config", None)
            if config is None or getattr(config, "template", False):
                continue
            vm_hardware = config.hardware
            vcpus += vm_hardware.numCPU
            memory_mib += vm_hardware.memoryMB
        physical_memory_mib = memory_bytes / (1024 ** 2)
        rows.append((
            host.name,
            vcpus,
            cores,
            round(vcpus / cores, 2),
            memory_mib,
            round(physical_memory_mib),
            round(memory_mib / physical_memory_mib, 2),
        ))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="host_overcommitment.csv")
    args = parser.parse_args(argv)
    with vcenter_hosts() as hosts:
        rows = commitment_rows(hosts)
    with open(args.csv, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["HostName", "ProvisionedVCPUs", "PhysicalCores", "VCPUPerCore", "ProvisionedMemoryMiB", "PhysicalMemoryMiB", "MemoryRatio"])
        writer.writerows(rows)
    print(f"Exported provisioned capacity ratios for {len(rows)} hosts to {args.csv}")


if __name__ == "__main__":
    main()
