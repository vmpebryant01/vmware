"""Compare saved appliance configuration with explicit baselines. Author: Paul Bryant."""

import re
from urllib.parse import urlsplit

from .assurance_reports import _resource, _targets
from .exports import sanitize
from .http_client import ApiError
from .management_services import normalize_config

SERVICES = {"dns": "appliance_dns", "ntp": "appliance_ntp", "timesync": "appliance_timesync", "syslog": "appliance_syslog"}


def _origin(value):
    if not isinstance(value, str) or any(c.isspace() for c in value) or "\\" in value:
        return False
    try:
        parts = urlsplit(value)
        return (parts.scheme == "https" and bool(parts.hostname) and parts.username is None and parts.password is None
                and parts.path == "" and not parts.query and not parts.fragment
                and (parts.port is None or 1 <= parts.port <= 65535))
    except ValueError:
        return False


def validate_baseline(baseline):
    """Validate exact appliance selectors; no defaults silently apply to other targets."""
    if (not isinstance(baseline, dict) or set(baseline) - {"author", "schema_version", "targets"}
            or baseline.get("schema_version") != "1.0" or not isinstance(baseline.get("targets"), list)
            or not 1 <= len(baseline["targets"]) <= 1000):
        raise ValueError("Service baseline needs schema_version 1.0 and a nonempty targets array.")
    result = {}
    for entry in baseline["targets"]:
        if (not isinstance(entry, dict) or set(entry) - {"target", "endpoint", *SERVICES}
                or not isinstance(entry.get("target"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", entry["target"])
                or not _origin(entry.get("endpoint")) or not any(service in entry for service in SERVICES)):
            raise ValueError("Service baseline entries need an exact target, HTTPS endpoint and one or more service configurations.")
        identity = (entry["target"], entry["endpoint"])
        if identity in result:
            raise ValueError("Service baseline repeats a target and endpoint selector.")
        configurations = {}
        for service, resource in SERVICES.items():
            if service not in entry:
                continue
            config = entry[service]
            fields = {"mode", "servers"} if service == "dns" else {"mode"} if service == "timesync" else {"servers"}
            if not isinstance(config, dict) or set(config) != fields:
                raise ValueError("Service baseline configuration has missing or unknown fields.")
            if service == "syslog" and (not isinstance(config["servers"], list) or any(
                    not isinstance(row, dict) or set(row) != {"hostname", "port", "protocol"} for row in config["servers"])):
                raise ValueError("Syslog baseline servers need hostname, port and protocol only.")
            value = config["servers"] if service in ("ntp", "syslog") else config["mode"] if service == "timesync" else config
            try:
                configurations[service] = normalize_config(resource, value)
            except ApiError as exc:
                raise ValueError(str(exc)) from None
        result[identity] = configurations
    return result


def _canonical(service, config):
    if service == "syslog":
        return tuple(sorted((row["hostname"], row["port"], row["protocol"]) for row in config["servers"]))
    if "servers" in config:
        return (config.get("mode"), tuple(sorted(config["servers"])))
    return config["mode"]


def build_management_services_report(run, baseline=None):
    expected = validate_baseline(baseline) if baseline is not None else {}
    targets = _targets(run, {"vcenter"})
    records, matched = [], set()
    for target in targets:
        identity = (target["name"], target["endpoint"])
        if identity in expected:
            matched.add(identity)
        for service, resource in SERVICES.items():
            document = _resource(run, target, resource)
            expectation = expected.get(identity, {}).get(service)
            row = {"target": target["name"], "component": "vcenter", "endpoint": target["endpoint"],
                   "service": service, "resource": resource, "status": "unknown", "observation": "configuration_unavailable",
                   "collected_at": document.get("collected_at") if document else None,
                   "configured": None, "expected": expectation, "baseline_match": None}
            if document is not None and len(document["records"]) == 1:
                source = document["records"][0]
                value = source.get("servers") if service in ("ntp", "syslog") else source.get("mode") if service == "timesync" else source
                try:
                    configured = normalize_config(resource, value)
                    row["configured"] = configured
                    if expectation is None:
                        row.update(status="observed", observation="configuration_observed_without_baseline")
                    else:
                        agrees = _canonical(service, configured) == _canonical(service, expectation)
                        row.update(status="observed" if agrees else "review", baseline_match=agrees,
                                   observation="baseline_match" if agrees else "baseline_difference")
                except ApiError:
                    row["observation"] = "saved_configuration_invalid"
            records.append(row)
    for target_name, endpoint in sorted(set(expected) - matched):
        records.append({"target": target_name, "component": "vcenter", "endpoint": endpoint, "service": None,
                        "status": "unknown", "observation": "baseline_target_not_in_run", "baseline_match": None})
    limitations = [
        "Settings describe the vCenter appliance at collection time; other components and ESXi hosts are outside this report.",
        "Configured DNS, NTP and log forwarding do not establish resolution, clock synchronization, reachability or log delivery.",
        "NTP server configuration remains present when another synchronization mode is selected; examine timesync separately.",
        "Baseline server order is ignored; names, case, modes, ports and protocols are otherwise compared exactly.",
    ]
    if not records:
        limitations.append("No vCenter appliance targets were available.")
    return sanitize({"author": "Paul Bryant", "schema_version": "1.0", "report_type": "management_services",
                     "status": "partial" if not records or any(row["status"] == "unknown" for row in records) else "success",
                     "records": records, "limitations": limitations})
