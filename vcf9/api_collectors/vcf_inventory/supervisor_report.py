"""Summarize saved Supervisor state and namespace quotas. Author: Paul Bryant."""

import math

from .assurance_reports import _resource, _targets
from .exports import sanitize
from .supervisor import SELECTORS


def _number(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def _capacity(stats, threshold):
    if not isinstance(stats, dict):
        stats = {}
    result = {}
    for metric in ("cpu", "memory", "storage"):
        used, capacity = stats.get(metric + "_used"), stats.get(metric + "_capacity")
        valid = _number(used) and _number(capacity) and capacity > 0
        percent = 100 * used / capacity if valid else None
        result[metric] = {"used_native": used if _number(used) else None,
                          "capacity_native": capacity if _number(capacity) else None,
                          "unit": "MHz" if metric == "cpu" else "MiB",
                          "used_percent": round(percent, 4) if percent is not None else None,
                          "max_used_percent": threshold,
                          "threshold_exceeded": percent > threshold if percent is not None else None,
                          "availability": "available" if valid else "unknown"}
    return result


def _saved_scope(document, resource):
    if document is None:
        return None
    collection = document.get("collection", {})
    values = collection.get(SELECTORS[resource])
    if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value for value in values) or len(set(values)) != len(values):
        return None
    queried = collection.get("queried_ids")
    if (not isinstance(queried, list) or any(not isinstance(value, str) or not value for value in queried)
            or len(queried) != len(values) or set(queried) != set(values)):
        return None
    return set(values)


def _index(document, resource):
    scope = _saved_scope(document, resource)
    if scope is None:
        return {}, set()
    field = "namespace_id" if resource == "namespaces" else "supervisor_id"
    result, ambiguous = {}, set()
    for row in document["records"]:
        identity = row.get(field)
        if not isinstance(identity, str) or identity not in scope:
            continue
        if identity in result or identity in ambiguous:
            result.pop(identity, None)
            ambiguous.add(identity)
        else:
            result[identity] = row
    return result, scope


def build_supervisor_report(run, max_used_percent=80):
    if type(max_used_percent) not in (int, float) or not math.isfinite(max_used_percent) or not 0 <= max_used_percent <= 100:
        raise ValueError("max_used_percent must be a finite number from 0 to 100.")
    report = {"author": "Paul Bryant", "schema_version": "1.0", "report_type": "supervisor_health", "status": "success",
              "records": [], "limitations": [
                  "Native configuration, Kubernetes and condition statuses are preserved; condition polarity is not inferred from its type.",
                  "Report success describes evidence completeness, not a healthy Supervisor or namespace.",
                  "Only explicitly selected identifiers are covered. Supervisor IDs and cluster IDs are distinct and are never joined by name.",
                  "Supervisor CPU usage and capacity are MHz; memory and storage are MiB. Percentages divide same-metric usage by capacity. Namespace quota values retain native units.",
                  "Namespace storage limits are in mebibytes. A missing limit means no limit for that storage policy; total namespace usage is not attributed to individual policies.",
                  "Separate GET responses describe their saved collection times and are not an atomic snapshot.",
              ]}

    def partial(message):
        report["status"] = "partial"
        if message not in report["limitations"]:
            report["limitations"].append(message)

    for target in _targets(run, {"vcenter"}):
        documents = {resource: _resource(run, target, resource) for resource in SELECTORS}
        indexes = {resource: _index(document, resource) for resource, document in documents.items()}
        for resource, document in documents.items():
            if document is not None:
                field = "namespace_id" if resource == "namespaces" else "supervisor_id"
                if (any(not isinstance(row.get(field), str) or row[field] not in indexes[resource][1] for row in document["records"])
                        or len(indexes[resource][0]) != len(document["records"])):
                    partial("Some records had invalid, duplicate or out-of-scope identifiers and were excluded.")
        # A missing resource still gets an unknown record if its companion recorded a scope.
        supervisors = indexes["supervisor_summaries"][1] | indexes["supervisor_conditions"][1]
        context = {"target": target["name"], "component": "vcenter", "endpoint": target["endpoint"]}
        for identity in sorted(supervisors):
            summary = indexes["supervisor_summaries"][0].get(identity)
            conditions = indexes["supervisor_conditions"][0].get(identity)
            record = {**context, "record_type": "supervisor", "supervisor_id": identity,
                      "summary_availability": "available" if summary else "unknown",
                      "conditions_availability": "available" if conditions else "unknown",
                      "summary_collected_at": documents["supervisor_summaries"].get("collected_at") if summary else None,
                      "conditions_collected_at": documents["supervisor_conditions"].get("collected_at") if conditions else None,
                      "name": summary.get("name") if summary else None,
                      "config_status": summary.get("config_status") if summary else None,
                      "kubernetes_status": summary.get("kubernetes_status") if summary else None,
                      "messages": summary.get("messages") if summary else None,
                      "conditions": conditions.get("conditions") if conditions else None,
                      "capacity": _capacity(summary.get("stats") or {} if summary else {}, max_used_percent)}
            valid_conditions = (isinstance(record["conditions"], list) and bool(record["conditions"])
                                and all(isinstance(condition, dict) and isinstance(condition.get("type"), str)
                                        and condition["type"] and isinstance(condition.get("status"), str)
                                        and condition["status"] for condition in record["conditions"]))
            if (not summary or not conditions or not isinstance(record["config_status"], str) or not record["config_status"]
                    or not isinstance(record["kubernetes_status"], str) or not record["kubernetes_status"] or not valid_conditions):
                partial("Some selected Supervisors lack a summary, status or nonempty conditions; missing evidence is unknown.")
            if any(value["availability"] != "available" for value in record["capacity"].values()):
                partial("Some Supervisor capacity percentages could not be calculated from positive capacity and nonnegative usage.")
            report["records"].append(record)
        namespace_rows, namespaces = indexes["namespaces"]
        for identity in sorted(namespaces):
            row = namespace_rows.get(identity)
            record = {**context, "record_type": "namespace", "namespace_id": identity,
                      "availability": "available" if row else "unknown", "cluster_id": row.get("cluster") if row else None,
                      "collected_at": documents["namespaces"].get("collected_at") if row else None,
                      "config_status": row.get("config_status") if row else None, "stats_native": row.get("stats") if row else None,
                      "resource_spec_native": row.get("resource_spec") if row else None,
                      "storage_specs": row.get("storage_specs") if row else None,
                      "messages": row.get("messages") if row else None}
            if (not row or not isinstance(record["config_status"], str) or not record["config_status"]
                    or not isinstance(record["stats_native"], dict)
                    or not all(_number(record["stats_native"].get(metric + "_used")) for metric in ("cpu", "memory", "storage"))):
                record["availability"] = "unknown"
                if isinstance(record["stats_native"], dict):
                    record["stats_native"] = {metric + "_used": record["stats_native"].get(metric + "_used")
                                              if _number(record["stats_native"].get(metric + "_used")) else None
                                              for metric in ("cpu", "memory", "storage")}
                partial("Some selected namespaces lack configuration status or runtime statistics.")
            report["records"].append(record)
        for resource in SELECTORS:
            key = (target["name"], "vcenter", resource)
            if key in run.get("unavailable", {}) or documents[resource] is not None and _saved_scope(documents[resource], resource) is None:
                report["records"].append({**context, "record_type": "collection", "resource": resource,
                                          "availability": "unknown", "observation": "resource_unavailable_or_scope_missing"})
                partial("A requested resource failed or lacked its saved explicit scope; identifiers were not guessed.")
    if not report["records"]:
        partial("No complete, explicitly scoped Supervisor or namespace evidence was available.")
    return sanitize(report)
