"""Collect vCenter appliance service configuration. Author: Paul Bryant."""

from .http_client import ApiError

RESOURCE_PATHS = {"vcenter": {
    "appliance_dns": "/api/appliance/networking/dns/servers",
    "appliance_ntp": "/api/appliance/ntp",
    "appliance_timesync": "/api/appliance/timesync",
    "appliance_syslog": "/api/appliance/logging/forwarding",
}}
DEFAULT_RESOURCES = {}
ALLOWED_OPERATIONS = set()


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def validate_target(target):
    filters = target.get("filters", {})
    if isinstance(filters, dict) and any(supports(target.get("component"), resource) for resource in filters):
        raise ValueError("Appliance service configuration does not accept filters.")


def _text(value):
    return isinstance(value, str) and bool(value) and len(value) <= 1024 and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def _servers(value):
    return isinstance(value, list) and all(_text(server) for server in value) and len(set(value)) == len(value)


def normalize_config(resource, document):
    """Project the documented configuration, excluding extra response fields."""
    if resource == "appliance_dns":
        if not isinstance(document, dict) or not _text(document.get("mode")) or not _servers(document.get("servers")):
            raise ApiError("DNS configuration did not contain a mode and unique server list.")
        return {"mode": document["mode"], "servers": list(document["servers"])}
    if resource == "appliance_ntp":
        if not _servers(document):
            raise ApiError("NTP configuration did not contain a unique string server list.")
        return {"servers": list(document)}
    if resource == "appliance_timesync":
        if not _text(document):
            raise ApiError("Time synchronization configuration did not contain a mode string.")
        return {"mode": document}
    if resource == "appliance_syslog":
        if not isinstance(document, list):
            raise ApiError("Log forwarding configuration is not an array.")
        servers, seen = [], set()
        for row in document:
            if (not isinstance(row, dict) or not _text(row.get("hostname")) or not _text(row.get("protocol"))
                    or type(row.get("port")) is not int or not 1 <= row["port"] <= 65535):
                raise ApiError("Log forwarding configuration contains invalid server fields.")
            key = (row["hostname"], row["port"], row["protocol"])
            if key in seen:
                raise ApiError("Log forwarding configuration repeats a server.")
            seen.add(key)
            servers.append({field: row[field] for field in ("hostname", "port", "protocol")})
        return {"servers": servers}
    raise ApiError("Unknown appliance service configuration resource.")


def collect_resource(client, resource, page_size=100, max_pages=1000):
    if not supports(client.target.get("component"), resource):
        raise ApiError("Unknown appliance service configuration resource.")
    try:
        validate_target(client.target)
    except ValueError as exc:
        raise ApiError(str(exc)) from None
    if not isinstance(getattr(client, "collection_metadata", None), dict):
        client.collection_metadata = {}
    metadata = {"coverage": "incomplete", "scope": "configured_vcenter_appliance", "evidence_type": "configuration"}
    client.collection_metadata[resource] = metadata
    config = normalize_config(resource, client.get(RESOURCE_PATHS["vcenter"][resource]))
    metadata.update(coverage="complete", record_count=1)
    return [{"id": "configuration", **config}]


def probe_request(target, resource):
    if not supports(target.get("component"), resource):
        return None
    return ("GET", RESOURCE_PATHS["vcenter"][resource], None, None,
            "Configured appliance settings only; no DNS resolution, NTP synchronization, or log-delivery test.")
