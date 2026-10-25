"""Summarize saved vSAN health and physical capacity. Author: Paul Bryant."""

import math
import re

from .exports import sanitize


def _nonnegative_integer(value):
    return type(value) is int and value >= 0


def _objects(health):
    section = health.get("objectHealth")
    if not isinstance(section, dict):
        return {"availability": "not_returned", "states": None, "total_objects": None}
    states = section.get("objectHealthDetail")
    if not isinstance(states, list) or any(not isinstance(row, dict) for row in states):
        return {"availability": "not_returned", "states": None, "total_objects": None}
    valid = all(_nonnegative_integer(row.get("numObjects")) and isinstance(row.get("health"), str) for row in states)
    return {"availability": "available" if valid else "invalid_data", "states": states,
            "total_objects": sum(row["numObjects"] for row in states) if valid else None,
            "object_version_compliance": section.get("objectVersionCompliance"),
            "objects_relayout_bytes": section.get("objectsRelayoutBytes")}


def _disks(health):
    hosts = health.get("physicalDisksHealth")
    if not isinstance(hosts, list) or any(not isinstance(row, dict) for row in hosts):
        return {"availability": "not_returned", "hosts": None, "returned_disk_count": None}
    output, complete, count = [], True, 0
    fields = ("name", "uuid", "summaryHealth", "operationalHealth", "operationalHealthDescription", "capacityHealth",
              "metadataHealth", "congestionHealth", "compLimitHealth", "capacity", "usedCapacity", "reservedCapacity",
              "logicalCapacity", "logicalCapacityUsed")
    for host in hosts:
        disks = host.get("disks")
        returned = isinstance(disks, list) and all(isinstance(row, dict) for row in disks)
        has_error = host.get("error") is not None
        available = returned and not has_error
        complete = complete and available
        if returned:
            count += len(disks)
        output.append({"hostname": host.get("hostname"), "overall_health": host.get("overallHealth"),
                       "availability": "available" if available else "collection_error" if has_error else "not_returned",
                       "collection_error": has_error,
                       "disks": [{key: disk[key] for key in fields if key in disk} for disk in disks] if returned else None})
    return {"availability": "available" if complete else "partial", "hosts": output,
            "returned_disk_count": count if complete else None}


def _capacity(space, threshold):
    total, free = space.get("totalCapacityB"), space.get("freeCapacityB")
    valid = _nonnegative_integer(total) and _nonnegative_integer(free) and free <= total
    used = total - free if valid else None
    percent = used * 100 / total if valid and total else None
    return {"availability": "available" if valid else "not_returned" if free is None else "invalid_data",
            "total_capacity_bytes": total if _nonnegative_integer(total) else None,
            "free_capacity_bytes": free if _nonnegative_integer(free) else None,
            "used_capacity_bytes": used,
            "used_percent": round(percent, 4) if percent is not None else None,
            "max_used_percent": threshold,
            "threshold_exceeded": percent > threshold if percent is not None else None,
            "capacity_health_threshold": space.get("capacityHealthThreshold"),
            "space_overview": space.get("spaceOverview"),
            "effective_space_usage": space.get("effectiveSpaceUsage")}


def build_vsan_report(run, max_used_percent=80):
    """Build a pure report; report status describes data coverage, not health color."""
    if type(max_used_percent) not in (int, float) or not math.isfinite(max_used_percent) or not 0 <= max_used_percent <= 100:
        raise ValueError("max_used_percent must be a finite number from 0 to 100.")
    report = {"author": "Paul Bryant", "schema_version": "1.0", "report_type": "vsan_health", "status": "success",
              "records": [], "limitations": [
                  "Health summaries are cached. health_observed_at is the server's check time and may precede inventory collection.",
                  "Object health is summarized by state; per-object UUID enumeration is not requested.",
                  "Health and capacity come from separate queries and are not an atomic snapshot.",
              ]}

    def partial(message):
        report["status"] = "partial"
        if message not in report["limitations"]:
            report["limitations"].append(message)

    grouped = {}
    for (target, component, resource), document in sorted(run.get("resources", {}).items()):
        if (component != "vsan" or resource not in ("health_summary", "space_usage")
                or (target, component, resource) in run.get("unavailable", {})):
            continue
        expected = document.get("cluster_ids")
        if expected is not None:
            if (not isinstance(expected, list) or not 1 <= len(expected) <= 1000
                    or any(not isinstance(identity, str) or not re.fullmatch(r"domain-c[0-9]{1,18}", identity) for identity in expected)
                    or len(set(expected)) != len(expected)):
                partial("Some saved vSAN cluster scope metadata was invalid and could not establish expected coverage.")
                expected = None
            else:
                for identity in expected:
                    grouped.setdefault((target, identity), {})
        for row in document["records"]:
            identity = row.get("cluster_id")
            if not isinstance(identity, str) or not re.fullmatch(r"domain-c[0-9]{1,18}", identity):
                partial("Some vSAN records lacked a cluster identifier and could not be combined.")
                continue
            if expected is not None and identity not in expected:
                partial("Some vSAN records were outside their saved cluster scope and were excluded.")
                continue
            grouped.setdefault((target, identity), {}).setdefault(resource, []).append({"record": row, "collected_at": document.get("collected_at")})
    for key in run.get("unavailable", {}):
        if key[1] == "vsan" and key[2] in ("health_summary", "space_usage"):
            partial("Some requested vSAN resources were unavailable and were excluded from the report.")
    if not grouped:
        partial("No successful vSAN health or capacity records were available.")
    for (target, identity), sources in sorted(grouped.items()):
        health_rows, space_rows = sources.get("health_summary", []), sources.get("space_usage", [])
        record = {"target": target, "component": "vsan", "cluster_id": identity,
                  "health_availability": "available" if len(health_rows) == 1 else "ambiguous" if health_rows else "not_collected",
                  "health_observed_at": None, "health_collected_at": None, "capacity_collected_at": None,
                  "overall_health": None, "overall_health_description": None,
                  "health_score": None, "object_health": {"availability": "not_collected", "states": None, "total_objects": None},
                  "physical_disks": {"availability": "not_collected", "hosts": None, "returned_disk_count": None},
                  "disk_balance": None, "capacity": _capacity({}, max_used_percent)}
        if len(health_rows) == 1:
            health = health_rows[0]["record"]
            record.update(health_observed_at=health.get("timestamp"), health_collected_at=health_rows[0]["collected_at"],
                          overall_health=health.get("overallHealth"),
                          overall_health_description=health.get("overallHealthDescription"), health_score=health.get("healthScore"),
                          object_health=_objects(health), physical_disks=_disks(health), disk_balance=health.get("diskBalance"))
            if not isinstance(record["overall_health"], str) or not record["overall_health"]:
                record["health_availability"] = "invalid_data"
                partial("Some cluster health status values were absent or invalid.")
            if not isinstance(record["health_observed_at"], str) or not record["health_observed_at"]:
                partial("Some cached health summaries did not provide a check timestamp.")
            if record["object_health"]["availability"] != "available":
                partial("Some object health summaries were absent or invalid; missing objects were not counted as healthy.")
            if record["physical_disks"]["availability"] != "available":
                partial("Some physical-disk health summaries were absent or had host collection errors.")
        else:
            partial("Some cluster health summaries were missing or duplicated and were not inferred from capacity data.")
        if len(space_rows) == 1:
            record["capacity_collected_at"] = space_rows[0]["collected_at"]
            record["capacity"] = _capacity(space_rows[0]["record"], max_used_percent)
            if record["capacity"]["availability"] != "available":
                partial("Some physical capacity fields were absent or invalid; unavailable capacity was not set to zero.")
            elif record["capacity"]["used_percent"] is None:
                partial("A zero total physical capacity prevented calculation of a usage percentage.")
        else:
            record["capacity"]["availability"] = "ambiguous" if space_rows else "not_collected"
            partial("Some cluster capacity summaries were missing or duplicated and could not be calculated.")
        report["records"].append(record)
    return sanitize(report)
