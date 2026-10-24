# VMware Cloud Foundation API collectors

Author: Paul Bryant

Read-only Python collectors for VCF management inventory, vCenter, HCX, NSX, VCF Operations, VCF Automation, Live Site Recovery, and vSphere Replication. Run one product script or collect several explicitly configured targets together. Each run exports JSON, optional CSV, and a summary identifying failed collections.

The implementation follows the public API contracts linked below. It has offline tests and has not been exercised against live appliances. A VCF product version does not establish the version of every connected component. Confirm the documented methods and authentication policies against each installed build; no blanket compatibility across all VCF 9.x releases is claimed.

## Product scripts

| Script | Information collected |
| --- | --- |
| `collect_vcf.py` | SDDC appliance information, workload domains, clusters, hosts, vCenters, NSX clusters, network pools; vCenter datacenters, clusters, hosts, datastores, networks, VMs |
| `collect_hcx.py` | Site pairings, compute profiles, service meshes, appliances, network extensions |
| `collect_nsx.py` | Segments, Tier-0/Tier-1 gateways, host/edge transport nodes, transport zones, groups, security policies, IP pools |
| `collect_vcf_operations.py` | Monitored resources, adapters, alerts, policy summaries |
| `collect_vcf_automation.py` | Projects, blueprints, deployments; VM Apps cloud accounts, cloud zones and fabric networks; provider organizations, regions, zones, namespace summaries and VPCs |
| `collect_vcf_protection_recovery.py` | Live Site Recovery pairings, protection groups and recovery plans; vSphere Replication pairings and extended replication status |
| `collect.py` | All target types selected in the configuration |

The VCF script selects SDDC Manager and vCenter targets. Protection and Recovery selects both recovery components. Other product scripts restrict collection to their named component. `--target` further narrows the configured target names.

## Setup

Use Python 3.11 or newer inside the parent repository. The standalone package accepts Python 3.10 or newer. No third-party runtime packages are required. Run these commands from this directory, `vcf9/api_collectors` in the repository:

```powershell
Copy-Item .\config.example.json .\config.json
notepad .\config.json
python .\collect.py --config .\config.json --validate-config
```

Replace placeholder HTTPS endpoints, remove targets you do not need, and select resources for each account's authorization scope. Every manager must have its own target entry. The collector does not automatically connect to discovered addresses.

Validation checks configuration structure, product options, and the existence of configured CA bundle files. It does not read secrets or contact appliances. `verify_tls` must be `true` or a trusted PEM CA bundle path. Relative paths resolve against the configuration file's directory. TLS verification cannot be disabled.

## Credentials and tokens

Supply secrets through environment variables, never command arguments or checked-in JSON. Populate only the variables needed by the selected targets. For example, in PowerShell:

```powershell
$credential = Get-Credential -Message "HCX inventory account"
$env:HCX_USERNAME = $credential.UserName
$env:HCX_PASSWORD = $credential.GetNetworkCredential().Password
try {
    python .\collect_hcx.py --config .\config.json --output .\inventory --csv
} finally {
    Remove-Item Env:HCX_USERNAME, Env:HCX_PASSWORD -ErrorAction SilentlyContinue
    Remove-Variable credential -ErrorAction SilentlyContinue
}
```

For an existing Operations token:

```powershell
$token = Read-Host "Issued Operations token" -AsSecureString
$env:VCF_OPERATIONS_TOKEN = [System.Net.NetworkCredential]::new("", $token).Password
try {
    python .\collect_vcf_operations.py --config .\config.json --output .\inventory --csv
} finally {
    Remove-Item Env:VCF_OPERATIONS_TOKEN -ErrorAction SilentlyContinue
    Remove-Variable token -ErrorAction SilentlyContinue
}
```

Use raw tokens without an authorization scheme prefix. Secrets are temporarily available to this process and its child processes. Accounts must be allowed to read the selected resources.

| Component | Authentication |
| --- | --- |
| SDDC Manager | `username_env` and `password_env`; token creation through `/v1/tokens` |
| vCenter | `username_env` and `password_env`; API session creation and cleanup |
| NSX | `username_env` and `password_env`; Basic authentication over verified HTTPS |
| HCX | Credentials, existing workload session, or VCF SSO bearer token selected by `auth_source` |
| VCF Operations | Existing `token_env` with `token_scheme` `OpsToken` or `Bearer`; alternatively local/supported-source credentials with optional `auth_source` |
| VCF Automation | Existing bearer `token_env`; required `api_family`: `all_apps`, `vm_apps`, or `provider` |
| Recovery components | Local credentials or existing session; paired inventory needs an explicitly scoped remote login or a session authenticated at both sites |

See [Operations authentication](docs/operations.md), [Automation API families](docs/automation.md), and [HCX and recovery sessions](docs/hcx_recovery.md). Operations 9.0.x Identity Broker users cannot use the local-account password token flow, as explained in the linked Operations guide. The sample uses an existing OpsToken; choose `Bearer` only for an accepted identity access token.

## Run collections

```powershell
python .\collect_vcf.py --config .\config.json --output .\inventory --csv
python .\collect_nsx.py --config .\config.json --output .\inventory --csv
python .\collect_hcx.py --config .\config.json --output .\inventory --csv
python .\collect_vcf_operations.py --config .\config.json --output .\inventory --csv
python .\collect_vcf_automation.py --config .\config.json --output .\inventory --csv
python .\collect_vcf_protection_recovery.py --config .\config.json --output .\inventory --csv
```

Use `collect.py` for all configured products, `--component` for one target type, or repeated `--target` options for named targets. `--list-resources` prints resource names and API paths without network access. Product scripts show their own resource catalogs.

The main sample collects only local recovery pairings. Identify the required pairing from those results, then adapt [the paired recovery example](examples/protection-recovery.example.json) to collect groups, plans, and replications. Remote credential variables are restricted to its explicit `pairing_id`. The [Automation family example](examples/automation-families.example.json) demonstrates three contexts with distinct token variables. Replace example API versions with values accepted by the installed service.

## Configuration

Top-level settings are `targets`, `timeout_seconds` (30), `retries` (2), `page_size` (100), and `max_pages` (1000). `author` records the configuration author. Timeouts apply to blocking HTTP operations, not the total run duration.

Each target requires a unique `name`, a `component`, and an HTTPS origin `url`. URLs cannot contain credentials, API paths, query strings, or fragments. Optional `resources` selects a nonempty subset of the product catalog. Optional `version` records an operator-supplied value, not an automatically verified compatibility result.

- NSX: `site_id`, `enforcement_point_id`, and `domain_id`, each defaulting to `default`.
- vCenter and Operations: `filters` groups query parameters by resource name. Operations validates documented names; verify vCenter names against the installed API.
- HCX: `auth_source` is `credentials`, `session_token`, or `vcf_sso`.
- Operations: `auth_source` names a configured source for password login; `token_scheme` applies only to existing tokens.
- Automation: `api_family` is required. Provider targets also require `api_version`; optional `org_id` sets organization context.
- Recovery: `auth_source` is `credentials` or `session_token`; only API `v2` is implemented. Paired credential mode requires `pairing_id`, `remote_username_env`, and `remote_password_env`. Replication optionally accepts `source_vc_guid`.

## Output and completeness

Each run creates a unique UTC timestamped folder under `--output`. Target folders contain JSON per successful resource, plus CSV when requested. JSON contains records, count, collection time, endpoint, and scope. `summary.json` reports resource and cleanup failures. Failed resources are not exported as empty successful inventories.

Recognized secret-bearing fields are redacted recursively. CSV flattens objects, serializes lists as JSON, and prefixes formula-like strings with an apostrophe. Redaction cannot remove secrets embedded in arbitrary blueprint text or deployment input strings. Treat exports as sensitive infrastructure information. Do not commit collected data or credentials to Git.

| Exit code | Meaning |
| --- | --- |
| `0` | All selected collections and applicable cleanup completed |
| `2` | Collection or cleanup failed; also used for invalid command syntax |
| `1` | Configuration, selection, or local file access failed |
| `130` | Collection was interrupted |

Paged APIs check available counts and cursors and fail at the configured limit. Collection does not create a point-in-time snapshot of a changing platform. Results cover only objects visible to the account and selected API context.

vCenter list boundaries are 1,000 for [datacenters](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/datacenter/get/), [clusters](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/cluster/get/), and [networks](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/network/get/); 2,500 for [hosts](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/host/get/) and [datastores](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/datastore/get/); and 4,000 for [VMs](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/vm/get/). The collector conservatively rejects responses reaching these boundaries. Collect narrower scopes separately using filters, following [Broadcom's partitioning guidance](https://knowledge.broadcom.com/external/article/301570/obtaining-information-for-more-than-4000.html).

NSX covers local `/infra`, the configured domain, and selected site/enforcement point, without enumerating all project or Global Manager scopes. Legacy transport resources require explicit selection. Automation families have separate permissions and schemas. Recovery collection does not run tests, failovers, or reconfiguration. These are inventory exports, not complete backups, licensing assessments, or security conclusions.

## Connections

Inventory uses documented GETs. Only allowed authentication calls can use other methods. Redirects are refused and ambient proxy configuration is ignored. Requests remain on the configured origin with TLS and hostname verification enabled. Run where managers are directly reachable.

Eligible GETs retry transient transport failures or HTTP 429, 502, 503, and 504 within configured limits. Authentication POSTs are not automatically retried. SDDC Manager and vCenter can reauthenticate once after a 401. Other product 401s fail explicitly to preserve their token and paired-session protocols. Supply a fresh supported token or correct authentication and rerun. Responses exceeding 64 MiB fail explicitly.

## Development

```powershell
python -m unittest discover -s tests -v
python collect.py --config config.example.json --validate-config
```

Tests simulate API responses without contacting appliances. Optional `python -m pip install .` registers `vcf-collect`; direct scripts need no installation. The parent repository's copyright and contribution terms apply.

## Public API documentation

- SDDC Manager: [appliance information](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/system/appliance-info/get/), [tokens](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/tokens/post/), [domains](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/domains/get/), [clusters](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/clusters/get/), [hosts](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/hosts/get/), [vCenters](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/vcenters/get/), [NSX clusters](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/nsxt-clusters/get/), [network pools](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/network-pools/get/).
- vCenter: the list APIs above, [session creation](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/session/post/), and [session cleanup](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/session/delete/).
- NSX: [9.0 API guide](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/9.0.0/), [segments](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListAllInfraSegments.html), [Tier-0](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListTier0s.html), [Tier-1](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListTier1.html), [host transport nodes](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListHostTransportNodes.html), [edge transport nodes](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListPolicyEdgeTransportNode.html), [transport zones](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListTransportZonesForEnforcementPoint.html), [groups](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListGroupForDomain.html), [security policies](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListSecurityPoliciesForDomain.html), [IP pools](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ListIpAddressPools.html).
- Product-specific methods and release details: [HCX and recovery](docs/hcx_recovery.md), [Operations](docs/operations.md), [Automation](docs/automation.md).
