# HCX and protection and recovery inventory

Author: Paul Bryant

Use these targets for HCX workload inventory and the Live Site Recovery and vSphere Replication API gateways. Configure each appliance explicitly. The collector keeps requests on the configured HTTPS origin and does not connect to URLs found in returned inventory.

Broadcom distinguishes VMware HCX 4.11.x from the VCF Operations HCX 9.0.x appliance stream. Product version numbers alone do not establish API compatibility. Check the documentation for the installed appliance before selecting resources. [Broadcom HCX appliance guidance](https://knowledge.broadcom.com/external/article/437122/unable-to-activate-vmware-cloud-foundati.html).

The recovery collectors use `/api/rest/srm/v2` and `/api/rest/vr/v2`. Broadcom documents these gateway paths in its [Live Site Recovery example](https://knowledge.broadcom.com/external/article/377916) and [vSphere Replication guidance](https://knowledge.broadcom.com/external/article/327270/requesting-info-on-vms-using-vr-rest-api.html). The earlier [SRM v1](https://developer.broadcom.com/xapis/vmware-live-site-recovery-v1-api/latest/) and [VR v1](https://developer.broadcom.com/xapis/vsphere-replication-v1-api/latest/) references direct clients to v2. These collectors do not select v1 automatically. This is API contract coverage, with offline tests; it is not a claim that every HCX, Live Site Recovery, vSphere Replication, or VCF Protection and Recovery release has been tested.

## HCX

Set `component` to `hcx` and use the HCX workload management HTTPS endpoint. This collector uses the workload APIs, whose documented paths differ from the appliance management APIs on port 9443. [Workload API login](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/sessions/post/), [appliance management login](https://developer.broadcom.com/xapis/hcx-manager-appliance-management-apis/latest/api/admin/v1/sessions/post/).

| Resource | GET path | Response collection | Documentation |
| --- | --- | --- | --- |
| `site_pairings` | `/hybridity/api/cloudConfigs` | `data.items` | [Site pairings](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/cloudConfigs/get/) |
| `compute_profiles` | `/hybridity/api/interconnect/computeProfiles` | `items` | [Compute profiles](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/interconnect/computeProfiles/get/) |
| `service_meshes` | `/hybridity/api/interconnect/serviceMesh` | `items` | [Service meshes](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/interconnect/serviceMesh/get/) |
| `appliances` | `/hybridity/api/interconnect/appliances` | `items` | [Interconnect appliances](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/interconnect/appliances/get/) |
| `network_extensions` | `/hybridity/api/l2NetworkExtensions` | `items` | [Network extensions](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/l2NetworkExtensions/get/) |

All five resources are selected by default. These GET operations document all-items collections without pagination parameters. The collector sends no page parameters and rejects responses that indicate unsupported pagination. Migration execution, migration history queries, and appliance configuration changes are outside this HCX inventory scope.

The default `auth_source` is `credentials`. Set `username_env` and `password_env` to the names of process environment variables containing the HCX account credentials. The collector sends them to `POST /hybridity/api/sessions`, reads the returned `x-hm-authorization` response header, and uses that header for GET requests. [HCX session creation](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/hybridity/api/sessions/post/).

Alternatively, set `auth_source` to `session_token` and `token_env` to an existing HCX session token environment variable, or use `auth_source: "vcf_sso"` with a VCF SSO bearer access token in `token_env`. These modes do not create a new session. The published workload reference provides session creation without a logout operation, so the HCX collector discards its local token at completion and relies on the server's session lifetime. Manage externally supplied tokens through their owning authentication workflow. [HCX authentication](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/api-security-schema/).

Example target:

```json
{
  "name": "hcx01",
  "component": "hcx",
  "url": "https://hcx.example.com",
  "auth_source": "credentials",
  "username_env": "HCX_USERNAME",
  "password_env": "HCX_PASSWORD",
  "verify_tls": true
}
```

## Live Site Recovery and vSphere Replication

Use `component: "live_site_recovery"` for protection groups and recovery plans, and `component: "vsphere_replication"` for replication inventory. Both use the configured appliance's HTTPS origin. `api_version` may be omitted or set to `v2`.

| Component | Resource | GET path relative to its gateway | Documentation |
| --- | --- | --- | --- |
| `live_site_recovery` | `pairings` | `/pairings` | [SRM pairings](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/get/) |
| `live_site_recovery` | `protection_groups` | `/pairings/{pairing_id}/protection-management/groups` | [Protection groups](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/protection-management/groups/get/) |
| `live_site_recovery` | `recovery_plans` | `/pairings/{pairing_id}/recovery-management/plans` | [Recovery plans](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/recovery-management/plans/get/) |
| `vsphere_replication` | `pairings` | `/pairings` | [VR pairings](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/pairings/get/) |
| `vsphere_replication` | `replications` | `/pairings/{pairing_id}/replications` | [Replications](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/pairings/pairing_id/replications/get/) |

For local pairing discovery, specify `resources: ["pairings"]` with `username_env` and `password_env`. Login uses HTTP Basic credentials for `POST {gateway}/session`; its `session_id` response becomes the `x-dr-session` header. The collector attempts `DELETE {gateway}/session` for sessions it creates. [Live Site Recovery login](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/session/post/), [logout](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/session/delete/), [vSphere Replication login](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/session/post/), [logout](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/session/delete/).

To collect protection groups, recovery plans, or replications with credential authentication, supply one explicit `pairing_id` and both `remote_username_env` and `remote_password_env`. Broadcom's workflow authenticates to the remote site before collecting paired inventory. The collector confirms that the pairing is visible, then sends those remote credentials only to that pairing's documented `remote-session` operation through the configured local appliance. It does not reuse local credentials for remote login. Configure separate named targets for separate pairing scopes. [Live Site Recovery remote login](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/remote-session/post/), [vSphere Replication remote login](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/pairings/pairing_id/remote-session/post/).

For an externally managed session, use `auth_source: "session_token"` and `token_env`. That session must already be authenticated to the required local and remote sites. The collector does not log out externally supplied sessions. With no `pairing_id`, this mode collects pair-scoped records for all pairings visible to that session.

Example target for one protection and recovery pairing:

```json
{
  "name": "recovery01",
  "component": "live_site_recovery",
  "url": "https://recovery.example.com",
  "username_env": "RECOVERY_LOCAL_USERNAME",
  "password_env": "RECOVERY_LOCAL_PASSWORD",
  "pairing_id": "replace-with-visible-pairing-id",
  "remote_username_env": "RECOVERY_REMOTE_USERNAME",
  "remote_password_env": "RECOVERY_REMOTE_PASSWORD",
  "resources": ["pairings", "protection_groups", "recovery_plans"],
  "verify_tls": true
}
```

Recovery collection follows numeric `offset` and `limit`, reads the `list` envelope, checks `_meta.total`, and rejects `_meta.errors` so partial results do not become successful exports. Short pages do not end collection by themselves. Server-provided pagination URLs are never followed. `max_pages` bounds each list operation, including pairing discovery and each pairing's resource list. The exported pair-scoped records include `pairing_id` to identify their scope. [Recovery list contract](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/pairings/pairing_id/protection-management/groups/get/), [replication list contract](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/pairings/pairing_id/replications/get/).

Replication requests set `extended_info=true` because the default response omits or defaults several replication status and configuration fields. `source_vc_guid` is an optional target setting that filters replications by source vCenter. When set, it narrows the exported scope. [Replication list options](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/pairings/pairing_id/replications/get/).

These collectors enumerate inventory and status. They do not run recovery plans, test recovery, reprotection, replication reconfiguration, or migration operations. Exports remain subject to the configured account's permissions and the selected API and pairing scopes.
