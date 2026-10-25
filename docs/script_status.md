# Script status

Author: Paul Bryant

All files below passed syntax parsing or compilation in the repository checks. No script was validated against a live vCenter, NSX, or Site Recovery system here. Unit-tested means selected local logic has tests; it does not establish end-to-end behavior. A listed adapter requirement means the script stops when a required external integration is unavailable.

See [historical version scope](compatibility.md) for the intended product generation and [representative workflows](workflows.md) for selected examples.

## API inventory collectors

The [collection guide](../vcf9/api_collectors/README.md) and its product notes link the public API contracts and collection limits. These Python entry scripts share local tests for documented response handling and exports. Live API behavior and compatibility with the installed component builds remain unverified.

| Entry script | Scope and verification |
| --- | --- |
| [`collect.py`](../vcf9/api_collectors/collect.py) | All configured target types; shared collection behavior tested offline |
| [`collect_vcf.py`](../vcf9/api_collectors/collect_vcf.py) | SDDC Manager and vCenter inventory; request, pagination, and failure handling tested offline |
| [`collect_hcx.py`](../vcf9/api_collectors/collect_hcx.py) | HCX inventory; product response handling tested offline |
| [`collect_nsx.py`](../vcf9/api_collectors/collect_nsx.py) | NSX inventory; cursor pagination and response handling tested offline |
| [`collect_vcf_operations.py`](../vcf9/api_collectors/collect_vcf_operations.py) | VCF Operations inventory; token handling and paged collections tested offline |
| [`collect_vcf_automation.py`](../vcf9/api_collectors/collect_vcf_automation.py) | VCF Automation inventory; product response handling tested offline |
| [`collect_vcf_protection_recovery.py`](../vcf9/api_collectors/collect_vcf_protection_recovery.py) | Protection and Recovery inventory; product response handling tested offline |

## Historical examples

| Script | Evidence and current limit |
| --- | --- |
| [`nsx/python_complex/dependency_mapping/nsxt_vcenter_cmdb_depmap_enriched.py`](../nsx/python_complex/dependency_mapping/nsxt_vcenter_cmdb_depmap_enriched.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/dfw_rules_production/create_nsxt_dfw_rules_from_csv.py`](../nsx/python_complex/dfw_rules_production/create_nsxt_dfw_rules_from_csv.py) | Selected logic unit-tested; live behavior unverified |
| [`nsx/python_complex/nsxt_api_health_and_performance_monitor.py`](../nsx/python_complex/nsxt_api_health_and_performance_monitor.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_bgp_peer_health_monitor.py`](../nsx/python_complex/nsxt_bgp_peer_health_monitor.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_certificate_expiry_and_renewal_audit.py`](../nsx/python_complex/nsxt_certificate_expiry_and_renewal_audit.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_firewall_rule_effectiveness_analyzer.py`](../nsx/python_complex/nsxt_firewall_rule_effectiveness_analyzer.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_full_config_audit_and_drift_report.py`](../nsx/python_complex/nsxt_full_config_audit_and_drift_report.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_global_security_posture_dashboard.py`](../nsx/python_complex/nsxt_global_security_posture_dashboard.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_policy_rollback_automation.py`](../nsx/python_complex/nsxt_policy_rollback_automation.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_security_group_dynamic_membership_validator.py`](../nsx/python_complex/nsxt_security_group_dynamic_membership_validator.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_segment_and_vlan_inventory_sync.py`](../nsx/python_complex/nsxt_segment_and_vlan_inventory_sync.py) | Static check only; live behavior unverified |
| [`nsx/python_complex/nsxt_topology_map_exporter.py`](../nsx/python_complex/nsxt_topology_map_exporter.py) | Static check only; live behavior unverified |
| [`nsx/python/audit_nsxt_config_drift.py`](../nsx/python/audit_nsxt_config_drift.py) | Static check only; live behavior unverified |
| [`nsx/python/audit_nsxt_dfw_rule_usage.py`](../nsx/python/audit_nsxt_dfw_rule_usage.py) | Static check only; live behavior unverified |
| [`nsx/python/compare_nsxt_config_to_baseline.py`](../nsx/python/compare_nsxt_config_to_baseline.py) | Static check only; live behavior unverified |
| [`nsx/python/export_nsxt_config_backup.py`](../nsx/python/export_nsxt_config_backup.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_active_sessions.py`](../nsx/python/get_nsxt_active_sessions.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_api_version.py`](../nsx/python/get_nsxt_api_version.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_edge_nodes.py`](../nsx/python/get_nsxt_edge_nodes.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_events_and_alarms.py`](../nsx/python/get_nsxt_events_and_alarms.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_firewall_rules.py`](../nsx/python/get_nsxt_firewall_rules.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_gateway_service_health.py`](../nsx/python/get_nsxt_gateway_service_health.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_logical_routers.py`](../nsx/python/get_nsxt_logical_routers.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_logical_switches.py`](../nsx/python/get_nsxt_logical_switches.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_overlay_tunnel_status.py`](../nsx/python/get_nsxt_overlay_tunnel_status.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_security_groups.py`](../nsx/python/get_nsxt_security_groups.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_segment_inventory.py`](../nsx/python/get_nsxt_segment_inventory.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_tier0_routing_summary.py`](../nsx/python/get_nsxt_tier0_routing_summary.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_transport_nodes.py`](../nsx/python/get_nsxt_transport_nodes.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_unmapped_segments.py`](../nsx/python/get_nsxt_unmapped_segments.py) | Static check only; live behavior unverified |
| [`nsx/python/get_nsxt_vrf_instances.py`](../nsx/python/get_nsxt_vrf_instances.py) | Static check only; live behavior unverified |
| [`nsx/python/nsxt_daily_compliance_report.py`](../nsx/python/nsxt_daily_compliance_report.py) | Static check only; live behavior unverified |
| [`nsx/scripts/Compare-NSXTConfigDrift.ps1`](../nsx/scripts/Compare-NSXTConfigDrift.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Export-NSXTConfigBackup.ps1`](../nsx/scripts/Export-NSXTConfigBackup.ps1) | Static check only; live behavior unverified |
| [`nsx/scripts/Export-NSXTFirewallChangeLog.ps1`](../nsx/scripts/Export-NSXTFirewallChangeLog.ps1) | Stops pending API integration; static check only |
| [`nsx/scripts/Get-NSXTActiveAlarms.ps1`](../nsx/scripts/Get-NSXTActiveAlarms.ps1) | Stops pending API integration; static check only |
| [`nsx/scripts/Get-NSXTApiVersion.ps1`](../nsx/scripts/Get-NSXTApiVersion.ps1) | Static check only; live behavior unverified |
| [`nsx/scripts/Get-NSXTDFWRuleUsage.ps1`](../nsx/scripts/Get-NSXTDFWRuleUsage.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTDFWSectionAudit.ps1`](../nsx/scripts/Get-NSXTDFWSectionAudit.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTDFWShadowRules.ps1`](../nsx/scripts/Get-NSXTDFWShadowRules.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTDriftEvents.ps1`](../nsx/scripts/Get-NSXTDriftEvents.ps1) | Stops pending API integration; static check only |
| [`nsx/scripts/Get-NSXTEdgeNodes.ps1`](../nsx/scripts/Get-NSXTEdgeNodes.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTFirewallRules.ps1`](../nsx/scripts/Get-NSXTFirewallRules.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTGatewayServiceHealth.ps1`](../nsx/scripts/Get-NSXTGatewayServiceHealth.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTInventory.ps1`](../nsx/scripts/Get-NSXTInventory.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTLogicalRouters.ps1`](../nsx/scripts/Get-NSXTLogicalRouters.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTLogicalSwitches.ps1`](../nsx/scripts/Get-NSXTLogicalSwitches.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTOverlayTunnelStatus.ps1`](../nsx/scripts/Get-NSXTOverlayTunnelStatus.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTRoutingAdjacency.ps1`](../nsx/scripts/Get-NSXTRoutingAdjacency.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTSecurityGroups.ps1`](../nsx/scripts/Get-NSXTSecurityGroups.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTStaleEdgeNodes.ps1`](../nsx/scripts/Get-NSXTStaleEdgeNodes.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTTier0RoutingSummary.ps1`](../nsx/scripts/Get-NSXTTier0RoutingSummary.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTTransportNodes.ps1`](../nsx/scripts/Get-NSXTTransportNodes.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTUnappliedSecurityTags.ps1`](../nsx/scripts/Get-NSXTUnappliedSecurityTags.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTUnusedSegments.ps1`](../nsx/scripts/Get-NSXTUnusedSegments.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Get-NSXTVRFInstances.ps1`](../nsx/scripts/Get-NSXTVRFInstances.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/Import-NSXTFirewallRulesFromCSV.ps1`](../nsx/scripts/Import-NSXTFirewallRulesFromCSV.ps1) | Static check only; live behavior unverified |
| [`nsx/scripts/Import-NSXTSegmentsFromCSV.ps1`](../nsx/scripts/Import-NSXTSegmentsFromCSV.ps1) | Static check only; live behavior unverified |
| [`nsx/scripts/New-NSXTDailyComplianceReport.ps1`](../nsx/scripts/New-NSXTDailyComplianceReport.ps1) | External cmdlets required; static check only |
| [`nsx/scripts/New-NSXTFirewallRuleTemplate.ps1`](../nsx/scripts/New-NSXTFirewallRuleTemplate.ps1) | Static check only; live behavior unverified |
| [`nsx/scripts/New-NSXTSegmentTemplate.ps1`](../nsx/scripts/New-NSXTSegmentTemplate.ps1) | Static check only; live behavior unverified |
| [`nsx/scripts/Test-NSXTConnectivity.ps1`](../nsx/scripts/Test-NSXTConnectivity.ps1) | External cmdlets required; static check only |
| [`srm/python_complex/srm_compliance_readiness_auditor.py`](../srm/python_complex/srm_compliance_readiness_auditor.py) | Stops pending API integration; static check only |
| [`srm/python_complex/srm_dr_cross_reconciliation.py`](../srm/python_complex/srm_dr_cross_reconciliation.py) | Stops pending API integration; static check only |
| [`srm/python_complex/srm_proactive_health_drift_monitor.py`](../srm/python_complex/srm_proactive_health_drift_monitor.py) | Stops pending API integration; static check only |
| [`srm/python_complex/srm_recovery_plan_test_scheduler.py`](../srm/python_complex/srm_recovery_plan_test_scheduler.py) | Stops pending API integration; static check only |
| [`srm/python_complex/srm_wave_failover_orchestration.py`](../srm/python_complex/srm_wave_failover_orchestration.py) | Stops pending API integration; static check only |
| [`srm/python/audit_srm_replication_status.py`](../srm/python/audit_srm_replication_status.py) | Stops pending API integration; static check only |
| [`srm/python/automate_srm_failback_process.py`](../srm/python/automate_srm_failback_process.py) | Stops pending API integration; static check only |
| [`srm/python/automated_srm_compliance_audit.py`](../srm/python/automated_srm_compliance_audit.py) | Stops pending API integration; static check only |
| [`srm/python/cleanup_stale_srm_mappings.py`](../srm/python/cleanup_stale_srm_mappings.py) | Stops pending API integration; static check only |
| [`srm/python/correlate_srm_vms_with_vcenter.py`](../srm/python/correlate_srm_vms_with_vcenter.py) | Stops pending API integration; static check only |
| [`srm/python/cross_system_srm_dr_reconciliation.py`](../srm/python/cross_system_srm_dr_reconciliation.py) | Stops pending API integration; static check only |
| [`srm/python/export_srm_configuration.py`](../srm/python/export_srm_configuration.py) | Stops pending API integration; static check only |
| [`srm/python/get_srm_alerts_and_events.py`](../srm/python/get_srm_alerts_and_events.py) | Stops pending API integration; static check only |
| [`srm/python/get_srm_failover_history.py`](../srm/python/get_srm_failover_history.py) | Stops pending API integration; static check only |
| [`srm/python/get_srm_protected_vms.py`](../srm/python/get_srm_protected_vms.py) | Stops pending API integration; static check only |
| [`srm/python/get_srm_protection_groups.py`](../srm/python/get_srm_protection_groups.py) | Stops pending API integration; static check only |
| [`srm/python/get_srm_recovery_plans.py`](../srm/python/get_srm_recovery_plans.py) | Stops pending API integration; static check only |
| [`srm/python/monitor_srm_bandwidth_usage.py`](../srm/python/monitor_srm_bandwidth_usage.py) | Stops pending API integration; static check only |
| [`srm/python/monitor_srm_health.py`](../srm/python/monitor_srm_health.py) | Stops pending API integration; static check only |
| [`srm/python/report_srm_vm_recovery_point_objectives.py`](../srm/python/report_srm_vm_recovery_point_objectives.py) | Stops pending API integration; static check only |
| [`srm/python/schedule_daily_srm_compliance_report.py`](../srm/python/schedule_daily_srm_compliance_report.py) | Stops pending API integration; static check only |
| [`srm/python/srm_failover_and_test_automation.py`](../srm/python/srm_failover_and_test_automation.py) | Stops pending API integration; static check only |
| [`srm/python/srm_servicenow_integration.py`](../srm/python/srm_servicenow_integration.py) | Stops pending API integration; static check only |
| [`srm/python/srm_test_recovery_scheduler.py`](../srm/python/srm_test_recovery_scheduler.py) | Stops pending API integration; static check only |
| [`srm/python/verify_srm_vm_mappings.py`](../srm/python/verify_srm_vm_mappings.py) | Stops pending API integration; static check only |
| [`srm/scripts/Audit-SRMReplicationStatus.ps1`](../srm/scripts/Audit-SRMReplicationStatus.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Compare-SRMtoCMDB.ps1`](../srm/scripts/Compare-SRMtoCMDB.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Correlate-SRMVMsWithBackup.ps1`](../srm/scripts/Correlate-SRMVMsWithBackup.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Detect-SRMConfigDrift.ps1`](../srm/scripts/Detect-SRMConfigDrift.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Export-SRMConfig.ps1`](../srm/scripts/Export-SRMConfig.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Export-SRMRecoveryPlanSteps.ps1`](../srm/scripts/Export-SRMRecoveryPlanSteps.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMAlertEvents.ps1`](../srm/scripts/Get-SRMAlertEvents.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMBandwidthUsage.ps1`](../srm/scripts/Get-SRMBandwidthUsage.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMDriftEvents.ps1`](../srm/scripts/Get-SRMDriftEvents.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMFailbackCandidates.ps1`](../srm/scripts/Get-SRMFailbackCandidates.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMFailoverHistory.ps1`](../srm/scripts/Get-SRMFailoverHistory.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMFailoverTestSchedule.ps1`](../srm/scripts/Get-SRMFailoverTestSchedule.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMHealthStatus.ps1`](../srm/scripts/Get-SRMHealthStatus.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMHealthSummary.ps1`](../srm/scripts/Get-SRMHealthSummary.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMProtectedVMs.ps1`](../srm/scripts/Get-SRMProtectedVMs.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMProtectionGroupLag.ps1`](../srm/scripts/Get-SRMProtectionGroupLag.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMProtectionGroups.ps1`](../srm/scripts/Get-SRMProtectionGroups.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMRecoveryPlans.ps1`](../srm/scripts/Get-SRMRecoveryPlans.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMReplicationHealth.ps1`](../srm/scripts/Get-SRMReplicationHealth.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMSnapshotConsistency.ps1`](../srm/scripts/Get-SRMSnapshotConsistency.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMTestResultsToExcel.ps1`](../srm/scripts/Get-SRMTestResultsToExcel.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Get-SRMUnmappedVMs.ps1`](../srm/scripts/Get-SRMUnmappedVMs.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Invoke-SRMComplianceAudit.ps1`](../srm/scripts/Invoke-SRMComplianceAudit.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Invoke-SRMFailback.ps1`](../srm/scripts/Invoke-SRMFailback.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Invoke-SRMRecoveryPlanApproval.ps1`](../srm/scripts/Invoke-SRMRecoveryPlanApproval.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Invoke-SRMTestRecoveryPlan.ps1`](../srm/scripts/Invoke-SRMTestRecoveryPlan.ps1) | External cmdlets required; static check only |
| [`srm/scripts/New-SRMDailyHealthReport.ps1`](../srm/scripts/New-SRMDailyHealthReport.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Remove-StaleSRMVMs.ps1`](../srm/scripts/Remove-StaleSRMVMs.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Send-SRMEventToServiceNow.ps1`](../srm/scripts/Send-SRMEventToServiceNow.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Set-SRMTestRecoverySchedule.ps1`](../srm/scripts/Set-SRMTestRecoverySchedule.ps1) | Static check only; live behavior unverified |
| [`srm/scripts/Start-SRMFailover.ps1`](../srm/scripts/Start-SRMFailover.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Start-SRMMultiWaveFailover.ps1`](../srm/scripts/Start-SRMMultiWaveFailover.ps1) | External cmdlets required; static check only |
| [`srm/scripts/Test-SRMScheduledRecoveryPlan.ps1`](../srm/scripts/Test-SRMScheduledRecoveryPlan.ps1) | External cmdlets required; static check only |
| [`vsphere/python_complex/automated_vm_lifecycle_compliance.py`](../vsphere/python_complex/automated_vm_lifecycle_compliance.py) | Static check only; live behavior unverified |
| [`vsphere/python_complex/automated_vsphere_cmdb_reconciliation.py`](../vsphere/python_complex/automated_vsphere_cmdb_reconciliation.py) | Static check only; live behavior unverified |
| [`vsphere/python_complex/cross_platform_backup_compliance_validator.py`](../vsphere/python_complex/cross_platform_backup_compliance_validator.py) | Static check only; live behavior unverified |
| [`vsphere/python_complex/hybrid_cloud_migration_planner.py`](../vsphere/python_complex/hybrid_cloud_migration_planner.py) | Static check only; live behavior unverified |
| [`vsphere/python_complex/vm_automated_rightsizing_predictive.py`](../vsphere/python_complex/vm_automated_rightsizing_predictive.py) | Static check only; live behavior unverified |
| [`vsphere/python/analyze_vmtools_guest_metrics.py`](../vsphere/python/analyze_vmtools_guest_metrics.py) | Static check only; live behavior unverified |
| [`vsphere/python/audit_user_permissions.py`](../vsphere/python/audit_user_permissions.py) | Static check only; live behavior unverified |
| [`vsphere/python/audit_vm_encryption.py`](../vsphere/python/audit_vm_encryption.py) | Static check only; live behavior unverified |
| [`vsphere/python/auto_generate_vm_rightsizing_report.py`](../vsphere/python/auto_generate_vm_rightsizing_report.py) | Static check only; live behavior unverified |
| [`vsphere/python/auto_remove_stale_templates.py`](../vsphere/python/auto_remove_stale_templates.py) | Static check only; live behavior unverified |
| [`vsphere/python/bulk_rename_vms.py`](../vsphere/python/bulk_rename_vms.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/check_unencrypted_vmotion.py`](../vsphere/python/check_unencrypted_vmotion.py) | Static check only; live behavior unverified |
| [`vsphere/python/check_vm_replicas_and_drs.py`](../vsphere/python/check_vm_replicas_and_drs.py) | Static check only; live behavior unverified |
| [`vsphere/python/compare_vcenter_vs_cmdb_inventory.py`](../vsphere/python/compare_vcenter_vs_cmdb_inventory.py) | Static check only; live behavior unverified |
| [`vsphere/python/cross_reference_azure_arc_vms.py`](../vsphere/python/cross_reference_azure_arc_vms.py) | Static check only; live behavior unverified |
| [`vsphere/python/detect_orphaned_and_inaccessible_vms.py`](../vsphere/python/detect_orphaned_and_inaccessible_vms.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/export_vcenter_events.py`](../vsphere/python/export_vcenter_events.py) | Static check only; live behavior unverified |
| [`vsphere/python/export_vms_to_excel_with_tags.py`](../vsphere/python/export_vms_to_excel_with_tags.py) | Static check only; live behavior unverified |
| [`vsphere/python/find_vms_with_iso_attached.py`](../vsphere/python/find_vms_with_iso_attached.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/generate_vm_lifecycle_report.py`](../vsphere/python/generate_vm_lifecycle_report.py) | Static check only; live behavior unverified |
| [`vsphere/python/get_all_vm_info.py`](../vsphere/python/get_all_vm_info.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_cluster_inventory.py`](../vsphere/python/get_cluster_inventory.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_datastore_usage.py`](../vsphere/python/get_datastore_usage.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_expired_snapshots.py`](../vsphere/python/get_expired_snapshots.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_host_patch_compliance.py`](../vsphere/python/get_host_patch_compliance.py) | Static check only; live behavior unverified |
| [`vsphere/python/get_host_summary.py`](../vsphere/python/get_host_summary.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_template_inventory.py`](../vsphere/python/get_template_inventory.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_vcenter_audit_events.py`](../vsphere/python/get_vcenter_audit_events.py) | Static check only; live behavior unverified |
| [`vsphere/python/get_vm_snapshots.py`](../vsphere/python/get_vm_snapshots.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_vm_tools_status.py`](../vsphere/python/get_vm_tools_status.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/get_vms_with_no_backups.py`](../vsphere/python/get_vms_with_no_backups.py) | Static check only; live behavior unverified |
| [`vsphere/python/inventory_vms_by_custom_attribute.py`](../vsphere/python/inventory_vms_by_custom_attribute.py) | Static check only; live behavior unverified |
| [`vsphere/python/monitor_host_overcommitment.py`](../vsphere/python/monitor_host_overcommitment.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/monitor_host_performance.py`](../vsphere/python/monitor_host_performance.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/monitor_vcenter_api_health.py`](../vsphere/python/monitor_vcenter_api_health.py) | Static check only; live behavior unverified |
| [`vsphere/python/monitor_vm_performance.py`](../vsphere/python/monitor_vm_performance.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/remediate_guest_time_sync.py`](../vsphere/python/remediate_guest_time_sync.py) | Static check only; live behavior unverified |
| [`vsphere/python/remove_old_snapshots.py`](../vsphere/python/remove_old_snapshots.py) | Selected logic unit-tested; live behavior unverified |
| [`vsphere/python/report_datastore_compliance.py`](../vsphere/python/report_datastore_compliance.py) | Static check only; live behavior unverified |
| [`vsphere/python/report_expired_ssl_certificates.py`](../vsphere/python/report_expired_ssl_certificates.py) | Static check only; live behavior unverified |
| [`vsphere/python/report_local_admin_accounts.py`](../vsphere/python/report_local_admin_accounts.py) | Static check only; live behavior unverified |
| [`vsphere/python/report_vms_with_open_vmtools.py`](../vsphere/python/report_vms_with_open_vmtools.py) | Static check only; live behavior unverified |
| [`vsphere/python/scheduled_vm_health_checks.py`](../vsphere/python/scheduled_vm_health_checks.py) | Static check only; live behavior unverified |
| [`vsphere/python/set_vm_hw_version_policy.py`](../vsphere/python/set_vm_hw_version_policy.py) | Static check only; live behavior unverified |
| [`vsphere/python/sync_vm_tags_to_cmdb.py`](../vsphere/python/sync_vm_tags_to_cmdb.py) | Static check only; live behavior unverified |
| [`vsphere/python/sync_vmware_tags_to_aws_ec2.py`](../vsphere/python/sync_vmware_tags_to_aws_ec2.py) | Static check only; live behavior unverified |
| [`vsphere/python/tag_cloud_eligible_vms.py`](../vsphere/python/tag_cloud_eligible_vms.py) | Static check only; live behavior unverified |
| [`vsphere/python/verify_vm_backup_status.py`](../vsphere/python/verify_vm_backup_status.py) | Static check only; live behavior unverified |
| [`vsphere/python/vsphere_inventory.py`](../vsphere/python/vsphere_inventory.py) | Static check only; live behavior unverified |
| [`vsphere/scripts/Analyze-VMThinProvisionedGrowth.ps1`](../vsphere/scripts/Analyze-VMThinProvisionedGrowth.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Audit-UserSessionHistory.ps1`](../vsphere/scripts/Audit-UserSessionHistory.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Audit-VMEncryption.ps1`](../vsphere/scripts/Audit-VMEncryption.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Bulk-ApplyTagToVMsByQuery.ps1`](../vsphere/scripts/Bulk-ApplyTagToVMsByQuery.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Check-SDRSRecommendations.ps1`](../vsphere/scripts/Check-SDRSRecommendations.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Check-VMBackupTools.ps1`](../vsphere/scripts/Check-VMBackupTools.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Clean-OrphanedVMs.ps1`](../vsphere/scripts/Clean-OrphanedVMs.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Collect-vCenterEvents.ps1`](../vsphere/scripts/Collect-vCenterEvents.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Configure-DRSRules.ps1`](../vsphere/scripts/Configure-DRSRules.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Configure-HostSyslog.ps1`](../vsphere/scripts/Configure-HostSyslog.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Disable-SSHForHosts.ps1`](../vsphere/scripts/Disable-SSHForHosts.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Disable-UnusedNICs.ps1`](../vsphere/scripts/Disable-UnusedNICs.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Enable-SSHForHosts.ps1`](../vsphere/scripts/Enable-SSHForHosts.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Enable-VMLogging.ps1`](../vsphere/scripts/Enable-VMLogging.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Export-VMsToExcelWithCustomFields.ps1`](../vsphere/scripts/Export-VMsToExcelWithCustomFields.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Find-StaleTemplates.ps1`](../vsphere/scripts/Find-StaleTemplates.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Find-VMsWithISOAttached.ps1`](../vsphere/scripts/Find-VMsWithISOAttached.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-AllVMInfo.ps1`](../vsphere/scripts/Get-AllVMInfo.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-ClusterDrsStatus.ps1`](../vsphere/scripts/Get-ClusterDrsStatus.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-ClusterInventory.ps1`](../vsphere/scripts/Get-ClusterInventory.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-DatastorePerformance.ps1`](../vsphere/scripts/Get-DatastorePerformance.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-DatastoreUsage.ps1`](../vsphere/scripts/Get-DatastoreUsage.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-ExpiredSnapshots.ps1`](../vsphere/scripts/Get-ExpiredSnapshots.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-GuestOSReport.ps1`](../vsphere/scripts/Get-GuestOSReport.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostCoreDumps.ps1`](../vsphere/scripts/Get-HostCoreDumps.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostFirmwareVersions.ps1`](../vsphere/scripts/Get-HostFirmwareVersions.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostHardwareStatus.ps1`](../vsphere/scripts/Get-HostHardwareStatus.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostLogs.ps1`](../vsphere/scripts/Get-HostLogs.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostNetworkHealth.ps1`](../vsphere/scripts/Get-HostNetworkHealth.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostPatchCompliance.ps1`](../vsphere/scripts/Get-HostPatchCompliance.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostPerformance.ps1`](../vsphere/scripts/Get-HostPerformance.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-HostSummary.ps1`](../vsphere/scripts/Get-HostSummary.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-NetworkAdapters.ps1`](../vsphere/scripts/Get-NetworkAdapters.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-ResourcePools.ps1`](../vsphere/scripts/Get-ResourcePools.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-SnapshotReport.ps1`](../vsphere/scripts/Get-SnapshotReport.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-TaskHistory.ps1`](../vsphere/scripts/Get-TaskHistory.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-TemplateInventory.ps1`](../vsphere/scripts/Get-TemplateInventory.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMDisks.ps1`](../vsphere/scripts/Get-VMDisks.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMHWCompatibility.ps1`](../vsphere/scripts/Get-VMHWCompatibility.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMLogBundle.ps1`](../vsphere/scripts/Get-VMLogBundle.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMNetworkMappings.ps1`](../vsphere/scripts/Get-VMNetworkMappings.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMsNoBackups.ps1`](../vsphere/scripts/Get-VMsNoBackups.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMsWithoutTags.ps1`](../vsphere/scripts/Get-VMsWithoutTags.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMsWithSnapshotsOlderThanXDays.ps1`](../vsphere/scripts/Get-VMsWithSnapshotsOlderThanXDays.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMTagCompliance.ps1`](../vsphere/scripts/Get-VMTagCompliance.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Get-VMToolsStatus.ps1`](../vsphere/scripts/Get-VMToolsStatus.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Monitor-ClusterHealth.ps1`](../vsphere/scripts/Monitor-ClusterHealth.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Monitor-HostOvercommitment.ps1`](../vsphere/scripts/Monitor-HostOvercommitment.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Monitor-VMPerformance.ps1`](../vsphere/scripts/Monitor-VMPerformance.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Move-VMToResourcePool.ps1`](../vsphere/scripts/Move-VMToResourcePool.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/New-VMFromTemplate.ps1`](../vsphere/scripts/New-VMFromTemplate.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Remediate-HostCompliance.ps1`](../vsphere/scripts/Remediate-HostCompliance.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Remove-OldSnapshots.ps1`](../vsphere/scripts/Remove-OldSnapshots.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Report-LocalAdminAccounts.ps1`](../vsphere/scripts/Report-LocalAdminAccounts.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Report-VMsWithSnapshotsAndReplication.ps1`](../vsphere/scripts/Report-VMsWithSnapshotsAndReplication.ps1) | External cmdlets required; static check only |
| [`vsphere/scripts/Resize-VMDisks.ps1`](../vsphere/scripts/Resize-VMDisks.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Set-AdvancedSettings.ps1`](../vsphere/scripts/Set-AdvancedSettings.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Set-HostDNS.ps1`](../vsphere/scripts/Set-HostDNS.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Set-VMCPULimit.ps1`](../vsphere/scripts/Set-VMCPULimit.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Set-VMNotes.ps1`](../vsphere/scripts/Set-VMNotes.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Set-VMResourceLimits.ps1`](../vsphere/scripts/Set-VMResourceLimits.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Set-VMTag.ps1`](../vsphere/scripts/Set-VMTag.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Start-ClusterVMs.ps1`](../vsphere/scripts/Start-ClusterVMs.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Stop-IdleVMs.ps1`](../vsphere/scripts/Stop-IdleVMs.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Tag-CloudEligibleVMs.ps1`](../vsphere/scripts/Tag-CloudEligibleVMs.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Update-ClusterSettings.ps1`](../vsphere/scripts/Update-ClusterSettings.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Update-HostNTP.ps1`](../vsphere/scripts/Update-HostNTP.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Update-VMToolsOnAllVMs.ps1`](../vsphere/scripts/Update-VMToolsOnAllVMs.ps1) | Static check only; live behavior unverified |
| [`vsphere/scripts/Validate-vMotionReadiness.ps1`](../vsphere/scripts/Validate-vMotionReadiness.ps1) | Static check only; live behavior unverified |
