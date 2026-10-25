# Migration, firewall, and deployment request observations

Author: Paul Bryant

These optional resources support the three saved-run reports below. Existing collection defaults are unchanged. Enable each resource explicitly in its target configuration, collect a completed run, and write reports outside the input run directory. The contracts have offline tests; live product responses have not been verified in this project.

## HCX migrations

Select `"resources": ["migrations"]` on an existing HCX target. Collection calls the [HCX migration query](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/migrations/post/) with `action=query`, a fixed `includeArchived: true` filter, and record offsets. Broadcom also identifies the exact query action in its [HCX API article](https://knowledge.broadcom.com/external/article/404980/hcx-api-calls-do-not-provide-mobility-gr.html). The [paging schema](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/data-structures/queryMigrationsRequest_paging/) defines the record offset and page size.

Only the fixed query action and body are permitted through the collector transport. Start, cancel, retry, archive, and other migration actions are not permitted. Collection requires the documented `data.items` response envelope and continues until an empty page, including after short pages. Repeated IDs, malformed responses, errors, or an exhausted request budget leave coverage incomplete. Legacy response envelopes are rejected.

```powershell
python report_hcx_migrations.py --run runs/current --output reports/migrations.json
python report_hcx_migrations.py --run runs/current --previous runs/earlier --stalled-minutes 30 --output reports/migrations-interval.json
```

A single snapshot shows selected migration state and progress only. A possible stall requires the same endpoint and archival scope, matching migration identity, two explicitly active transfer observations, unchanged available progress values, and a sufficient saved observation interval. It is an investigation candidate, not proof of a stuck migration. Missing progress, a counter decrease, completion, waiting state, or scope changes prevent that conclusion. Raw error messages, migration configuration, usernames, and request inputs are omitted.

HCX start and end timestamps remain raw numeric values. Their units are not established by the cited schema, so `duration_seconds` defaults to null with `timestamp_basis: "unit_not_verified"`. If the deployment's timestamp unit is independently known, supply `--hcx-time-unit seconds` or `--hcx-time-unit milliseconds`. Valid completed migrations use start-to-end duration; explicitly active transfers use start-to-saved-observation duration. Negative, future, conflicting, or missing times leave duration unknown. Output records identify the operator-supplied unit; the script never guesses units from digit counts.

## NSX rule statistics

Select `rule_statistics` and explicit `policy_ids`. The collector reads rules only within those policies, following the documented [rule listing](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListSecurityRules.html) cursor. To avoid discovery, provide `rule_ids` as a mapping with exactly the selected policy IDs as keys:

```json
{
  "resources": ["rule_statistics"],
  "domain_id": "default",
  "site_id": "default",
  "enforcement_point_id": "default",
  "policy_ids": ["application-policy"],
  "rule_ids": {
    "application-policy": ["web-rule", "database-rule"]
  }
}
```

The [statistics request](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_GetRuleStatistics.html) uses an explicit enforcement point path derived from the target's site and enforcement point IDs. Its [enforcement point response](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/types_RuleStatisticsForEnforcementPoint.html) contains nested statistics. The [statistics schema](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/types_RuleStatistics.html) distinguishes realized rules with `internal_rule_id` and provides native byte, packet, hit, session, and L7 counts.

Records retain each enforcement point, container cluster, realized rule, logical router, and segment context separately. They are never summed into a policy total. Missing counters remain null. The statistics method does not document cursor request parameters; an advertised truncated statistics response fails instead of silently exporting partial data. Scope metadata preserves resolved rule IDs even when no statistics are returned.

```powershell
python report_nsx_rule_usage.py --run runs/current --previous runs/earlier --output reports/rule-usage.json
```

Comparison requires matching endpoint, resolved policy and rule scope, positive observation interval, and exact statistics context. Counter decreases are marked as possible resets or replacements. The API documents no reset timestamp, so even a positive difference can be affected by an undetected reset. Zero or unchanged counts never establish that a rule is unused. Missing prior observations leave the interval unknown.

## Automation deployment requests

Select `deployment_requests` and a nonempty `deployment_ids` list on an `all_apps` or `vm_apps` target. Both the [All Apps request endpoint](https://developer.broadcom.com/xapis/all-apps-org-policy/latest/deployment/api/deployments/deploymentId/requests/get/) and [VM Apps request endpoint](https://developer.broadcom.com/xapis/vm-apps-org-policies/latest/deployment/api/deployments/deploymentId/requests/get/) document deployment-scoped request listing with zero-based page and size parameters. Other API families are rejected for this resource.

```json
{
  "api_family": "vm_apps",
  "resources": ["deployment_requests"],
  "deployment_ids": ["deployment-identifier"]
}
```

Collection preserves selected action IDs, request status, timestamps, and task counts. It omits inputs, outputs, raw details, and requesting users. Scope metadata lists queried deployments even for empty results. Repeated IDs, foreign deployment IDs, inconsistent pagination, or request failures prevent a complete result.

```powershell
python report_automation_requests.py --run runs/current --long-running-minutes 60 --output reports/deployment-requests.json
```

The [Request schema](https://developer.broadcom.com/xapis/vm-apps-org-policies/latest/data-structures/Request/) defines terminal and nonterminal status values and creation/completion timestamps. The report evaluates nonterminal age at the saved collection time and distinguishes waiting requests. An old saved run does not create a new live age alarm. A threshold flag is an investigation prompt, not a service-level violation. Unknown status, conflicting completion data, or invalid times remain unassessed and make the report partial.

All three reports include author, schema version, report type, status, records, limitations, and scope evidence. Empty resources keep their scope evidence. A partial report contains usable observations with stated gaps; it must not be interpreted as a complete inventory of unselected components or scopes. Collection is not an atomic snapshot across multiple requests. `max_pages` bounds logical collection requests across discovery and child requests; transport retries may add HTTP attempts.
