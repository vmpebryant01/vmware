"""Definitions for additional VCF 9.1.1 operational reports. Author: Paul Bryant."""

from __future__ import annotations

from dataclasses import dataclass

from vcf9.report_core import cursor_items, execute, page_items, parser_for, require_dict, require_items, safe_path_id, select_scalar


@dataclass(frozen=True)
class Report:
    target: str
    path: str
    columns: tuple[str, ...]
    fields: tuple[str, ...]
    style: str
    key: str = ""
    required: tuple[str, ...] = ()


REPORTS = {
    "segments": Report("NSX Manager", "/policy/api/v1/infra/segments",
                       ("id", "display_name", "connectivity_path", "transport_zone_path", "admin_state", "_last_modified_time"),
                       ("id", "display_name", "connectivity_path", "transport_zone_path", "admin_state", "_last_modified_time"), "cursor"),
    "groups": Report("NSX Manager", "/policy/api/v1/infra/domains/{domain_id}/groups",
                     ("domain_id", "id", "display_name", "group_type", "_last_modified_time"),
                     ("$domain_id", "id", "display_name", "group_type", "_last_modified_time"), "cursor", required=("domain-id",)),
    "segment_ports": Report("NSX Manager", "/policy/api/v1/infra/segments/{segment_id}/ports",
                             ("segment_id", "id", "display_name", "admin_state", "_last_modified_time"),
                             ("$segment_id", "id", "display_name", "admin_state", "_last_modified_time"), "cursor", required=("segment-id",)),
    "transport_zones": Report("NSX Manager", "/policy/api/v1/infra/sites/{site_id}/enforcement-points/{enforcement_point_id}/transport-zones",
                              ("site_id", "enforcement_point_id", "id", "display_name", "tz_type", "is_default"),
                              ("$site_id", "$enforcement_point_id", "id", "display_name", "tz_type", "is_default"),
                              "cursor", required=("site-id", "enforcement-point-id")),
    "security_rules": Report("NSX Manager", "/policy/api/v1/infra/domains/{domain_id}/security-policies/{policy_id}/rules",
                             ("domain_id", "policy_id", "id", "display_name", "action", "direction", "disabled", "logged", "sequence_number"),
                             ("$domain_id", "$policy_id", "id", "display_name", "action", "direction", "disabled", "logged", "sequence_number"),
                             "cursor", required=("domain-id", "policy-id")),
    "alert_definitions": Report("VCF Operations", "/suite-api/api/alertdefinitions",
                                ("id", "name", "adapterKindKey", "resourceKindKey", "waitCycles", "cancelCycles"),
                                ("id", "name", "adapterKindKey", "resourceKindKey", "waitCycles", "cancelCycles"), "ops_page", "alertDefinitions"),
    "policies": Report("VCF Operations", "/suite-api/api/policies",
                       ("id", "name", "defaultPolicy"), ("id", "name", "defaultPolicy"), "list", "policySummaries"),
    "collectors": Report("VCF Operations", "/suite-api/api/collectors",
                         ("id", "name", "state", "local", "dataPersistenceEnabled"),
                         ("id", "name", "state", "local", "dataPersistenceEnabled"), "list", "collector"),
    "collector_groups": Report("VCF Operations", "/suite-api/api/collectorgroups",
                                ("id", "name", "systemDefined", "haEnabled", "lbEnabled", "collectorCount"),
                                ("id", "name", "systemDefined", "haEnabled", "lbEnabled", "#collectorId"), "list", "collectorGroups"),
    "custom_groups": Report("VCF Operations", "/suite-api/api/resources/groups",
                            ("id", "name", "adapterKindKey", "resourceKindKey", "autoResolveMembership"),
                            ("id", "resourceKey.name", "resourceKey.adapterKindKey", "resourceKey.resourceKindKey", "autoResolveMembership"),
                            "list", "groups"),
    "vcenters": Report("SDDC Manager", "/v1/vcenters",
                       ("id", "fqdn", "domain", "version", "status", "vcInstanceId"),
                       ("id", "fqdn", "domain.name", "version", "status", "vcInstanceId"), "sddc_page"),
    "nsx_clusters": Report("SDDC Manager", "/v1/nsxt-clusters",
                           ("id", "vipFqdn", "version", "status", "isShared", "isShareable", "nodeCount"),
                           ("id", "vipFqdn", "version", "status", "isShared", "isShareable", "#nodes"), "sddc_page"),
    "releases": Report("SDDC Manager", "/v1/releases",
                       ("product", "version", "releaseDate", "minCompatibleVcfVersion", "isApplicable", "notApplicableReason"),
                       ("product", "version", "releaseDate", "minCompatibleVcfVersion", "isApplicable", "notApplicableReason"), "sddc_single"),
    "bundles": Report("SDDC Manager", "/v1/bundles",
                      ("id", "type", "version", "severity", "vendor", "description"),
                      ("id", "type", "version", "severity", "vendor", "description"), "sddc_single"),
    "notifications": Report("SDDC Manager", "/v1/notifications",
                            ("type", "severity", "message", "creationTimestamp", "expirationTimestamp"),
                            ("type", "severity", "message.localizedMessage", "creationTimestamp", "expirationTimestamp"),
                            "sddc_list"),
}


def collect(name: str, client, args):
    report = REPORTS[name]
    parameters = {}
    for required in report.required:
        key = required.replace("-", "_")
        parameters[key] = safe_path_id(getattr(args, key), required)
    path = report.path.format(**parameters)
    if report.style == "cursor":
        items = cursor_items(client, path)
    elif report.style == "ops_page":
        items = page_items(client, path, report.key, "ops")
    elif report.style == "list":
        items = require_items(client.get(path), report.key, path)
    elif report.style == "sddc_page":
        items = client.get_pages(path)
    elif report.style == "sddc_single":
        response = require_dict(client.request_json("GET", path), path)
        items = require_items(response, "elements", path)
        metadata = require_dict(response.get("pageMetadata"), path)
        if metadata.get("totalPages") not in (0, 1):
            raise RuntimeError(f"{path} returned multiple pages but has no documented page selector")
    elif report.style == "sddc_list":
        items = client.request_json("GET", path)
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise RuntimeError(f"Unexpected list from {path}")
    else:
        raise ValueError("Unknown report style")
    return [{column: select_scalar(item, field, args) for column, field in zip(report.columns, report.fields)} for item in items]


def run(name: str, argv=None) -> int:
    report = REPORTS[name]
    parser = parser_for(f"Export {name.replace('_', ' ')} metadata. Author: Paul Bryant.", report.target)
    for required in report.required:
        parser.add_argument(f"--{required}", required=True)
    return execute(parser, report.target, f"{name}.csv", report.columns,
                   lambda client, args: collect(name, client, args), argv)
