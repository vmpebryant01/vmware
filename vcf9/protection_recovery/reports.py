"""Fifteen recovery inventory reports. Author: Paul Bryant."""

from __future__ import annotations

from dataclasses import dataclass

from vcf9.protection_recovery.dr_core import dr_items, execute_dr, path_id
from vcf9.report_core import select_scalar


@dataclass(frozen=True)
class RecoveryReport:
    path: str
    columns: tuple[str, ...]
    fields: tuple[str, ...]
    required: tuple[str, ...] = ()


PAIR = ("pairing-id",)
PAIR_SRM = ("pairing-id", "srm-id")
PAIR_GROUP = ("pairing-id", "group-id")
PAIR_PLAN = ("pairing-id", "plan-id")
ISSUE_COLUMNS = ("pairing_id", "entity", "entity_name", "issue_type", "status", "timestamp", "description")
ISSUE_FIELDS = ("$pairing_id", "entity", "entity_name", "issue_type", "status", "timestamp", "description")
MAP_COLUMNS = ("pairing_id", "srm_id", "id", "primary_object_name", "secondary_object_name", "reverse_mapping_type")
MAP_FIELDS = ("$pairing_id", "$srm_id", "id", "primary_object_name", "secondary_object_name", "reverse_mapping_type")

REPORTS = {
    "pairings": RecoveryReport("/pairings",
        ("pairing_id", "local_vcenter", "local_status", "remote_vcenter", "remote_status"),
        ("pairing_id", "local_vc_server.name", "local_vc_server.server_status", "remote_vc_server.name", "remote_vc_server.server_status")),
    "pairing_issues": RecoveryReport("/pairings/{pairing_id}/issues", ISSUE_COLUMNS, ISSUE_FIELDS, PAIR),
    "srms": RecoveryReport("/pairings/{pairing_id}/srms",
        ("pairing_id", "id", "name", "url", "server_status", "version", "build_number"),
        ("$pairing_id", "id", "name", "url", "server_status", "version", "build_number"), PAIR),
    "srm_issues": RecoveryReport("/pairings/{pairing_id}/srms/{srm_id}/issues",
        ("srm_id",) + ISSUE_COLUMNS, ("$srm_id",) + ISSUE_FIELDS, PAIR_SRM),
    "protection_groups": RecoveryReport("/pairings/{pairing_id}/protection-management/groups",
        ("pairing_id", "id", "name", "protected_site_name", "recovery_site_name", "total_vms", "replication_type", "recovery_status", "status"),
        ("$pairing_id", "id", "name", "protected_site_name", "recovery_site_name", "total_vms", "replication_type", "recovery_status", "status"), PAIR),
    "group_issues": RecoveryReport("/pairings/{pairing_id}/protection-management/groups/{group_id}/issues",
        ("group_id",) + ISSUE_COLUMNS, ("$group_id",) + ISSUE_FIELDS, PAIR_GROUP),
    "group_vms": RecoveryReport("/pairings/{pairing_id}/protection-management/groups/{group_id}/vms",
        ("pairing_id", "group_id", "id", "name", "template", "inside_vapp"),
        ("$pairing_id", "$group_id", "id", "name", "template", "inside_vapp"), PAIR_GROUP),
    "recovery_plans": RecoveryReport("/pairings/{pairing_id}/recovery-management/plans",
        ("pairing_id", "id", "name", "status", "protected_site_name", "recovery_site_name", "progress", "is_running"),
        ("$pairing_id", "id", "name", "status", "protected_site_name", "recovery_site_name", "progress", "is_running"), PAIR),
    "plan_issues": RecoveryReport("/pairings/{pairing_id}/recovery-management/plans/{plan_id}/issues",
        ("plan_id",) + ISSUE_COLUMNS, ("$plan_id",) + ISSUE_FIELDS, PAIR_PLAN),
    "plan_protection_groups": RecoveryReport("/pairings/{pairing_id}/recovery-management/plans/{plan_id}/protection-groups",
        ("pairing_id", "plan_id", "group_id", "group_name", "total_vms", "status"),
        ("$pairing_id", "$plan_id", "id", "name", "total_vms", "status"), PAIR_PLAN),
    "folder_mappings": RecoveryReport("/pairings/{pairing_id}/srms/{srm_id}/inventory-mappings/folders",
        MAP_COLUMNS, MAP_FIELDS, PAIR_SRM),
    "network_mappings": RecoveryReport("/pairings/{pairing_id}/srms/{srm_id}/inventory-mappings/networks",
        MAP_COLUMNS, MAP_FIELDS, PAIR_SRM),
    "resource_mappings": RecoveryReport("/pairings/{pairing_id}/srms/{srm_id}/inventory-mappings/resources",
        MAP_COLUMNS, MAP_FIELDS, PAIR_SRM),
    "storage_policy_mappings": RecoveryReport("/pairings/{pairing_id}/srms/{srm_id}/inventory-mappings/storage-policies",
        MAP_COLUMNS, MAP_FIELDS, PAIR_SRM),
    "test_network_mappings": RecoveryReport("/pairings/{pairing_id}/srms/{srm_id}/inventory-mappings/test-networks",
        ("pairing_id", "srm_id", "id", "target_network", "test_network", "test_network_name"),
        ("$pairing_id", "$srm_id", "id", "target_network", "test_network", "test_network_name"), PAIR_SRM),
}


def collect(name: str, client, args):
    report = REPORTS[name]
    parameters = {}
    for required in report.required:
        key = required.replace("-", "_")
        parameters[key] = path_id(getattr(args, key), required)
    path = report.path.format(**parameters)
    items = dr_items(client, path)
    return [{column: select_scalar(item, field, args) for column, field in zip(report.columns, report.fields)} for item in items]


def run(name: str, argv=None) -> int:
    report = REPORTS[name]
    description = f"Export recovery {name.replace('_', ' ')} metadata. Author: Paul Bryant."
    return execute_dr(description, f"{name}.csv", report.required, report.columns,
                      lambda client, args: collect(name, client, args), argv)
