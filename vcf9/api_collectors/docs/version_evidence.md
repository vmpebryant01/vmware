# Product and server version evidence

Author: Paul Bryant

Preflight and live validation use the same bounded version probes. A probe uses the configured HTTPS origin and the existing client authentication. It makes at most one request after authentication, without discovering another address, logging in to a remote site, or selecting a version from an inventory list. Live validation counts this request against its target request budget. Session setup and cleanup remain the caller's responsibility.

| Target component | Version request | Exported fields and scope |
| --- | --- | --- |
| `sddc_manager` | `GET /v1/system/appliance-info` | `version` for the configured appliance. [Appliance information](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/system/appliance-info/get/) |
| `vcenter` | `GET /api/appliance/system/version` | Appliance `version` and `build`. [vCenter appliance system version API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/appliance/appliance-system-version/) |
| `nsx` | `GET /api/v1/node` | `node_version` and `product_version` for the responding local node. This observation does not establish every cluster member's build. [Node properties](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ReadNodeProperties.html) |
| `vcf_operations` | `GET /suite-api/api/versions/current` | Numeric `major`, `minor`, `minorMinor`, `patch`, and `buildNumber`, when present. Free-text release names are omitted. [Current service version](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/versions/current/get/) |
| `vcf_fleet` | `GET /fleet-lcm/v1/system` | `currentVersion` of the Fleet LCM system. Upgrade target versions and managed component versions are excluded. This field is not presented as an independently verified appliance image build. The existing Fleet bearer token is used. [Fleet LCM system](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/fleet-lcm/v1/system/get/), [system schema](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/data-structures/System/) |
| `live_site_recovery` | `GET /api/rest/srm/v2/server/info` | Local server `version` and `build_number`, using the established `x-dr-session` header. No pairing or remote login is needed for this local request. [Server information](https://developer.broadcom.com/xapis/vmware-live-site-recovery-api/latest/server/info/get/), [v2 gateway example](https://knowledge.broadcom.com/external/article/377916) |
| `vsphere_replication` | `GET /api/rest/vr/v2/info` | Local Replication Management Server `version` and `build_number`, using `x-dr-session`. This does not identify every registered replication server. [Replication Management Server information](https://developer.broadcom.com/xapis/vsphere-replication-api/latest/info/get/), [v2 gateway guidance](https://knowledge.broadcom.com/external/article/327270/requesting-info-on-vms-using-vr-rest-api.html) |
| `hcx` | `POST /hybridity/api/hcspAppliances` | Local manager `version` only. The exact read query is described below. [HCX manager version query](https://knowledge.broadcom.com/external/article/328978/hcx-connector-and-cloud-manager-upgrad.html) |
| `vsan` | `GET /sdk/vim25/{api_version}/ServiceInstance/ServiceInstance/content` | `about.version` and `about.build` identify the vCenter server used for vSAN collection. `about.apiVersion` is exported separately as `server_api_version`. This is not ESX host or vSAN component build evidence. [Service content](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/sdk/vim25/release/ServiceInstance/moId/content/get/), [AboutInfo field meanings](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/data-structures/AboutInfo/) |

The vSAN request uses the target's accepted JSON schema release, including its existing default of `9.0.0.0`. It requires `about.apiType` to identify `VirtualCenter`. A configured schema release or an API version alone cannot become an observed product build. Service content requires `System.Anonymous`, so a successful version request does not by itself verify credentials or permission to read protected inventory.

## HCX local manager query

The HCX probe sends this fixed body with an existing HCX session token:

```json
{"action": "query", "filter": {"local": "true"}}
```

Broadcom publishes this query in the version verification step of its [manager upgrade API article](https://knowledge.broadcom.com/external/article/328978/hcx-connector-and-cloud-manager-upgrad.html). The probe accepts the documented array response only when it contains exactly one object. An empty or multiple-manager response remains `unknown`; the probe does not select an entry by its name or position. Returned names, addresses and system descriptions are discarded. Upgrade notification and upgrade execution operations are outside this query's allowlist.

The published query uses `x-hm-authorization`. Targets using `auth_source: "vcf_sso"` remain `unknown` because that query's VCF SSO token contract is unverified. The [HCX workload API authentication schemes](https://developer.broadcom.com/xapis/hcx-workload-migration-apis/latest/api-security-schema/) do not establish that every older manager operation accepts every newer token scheme. The probe does not create an appliance management session or switch to port 9443. The cited manager article predates HCX 9.x, so this route requires validation against the installed build rather than a blanket compatibility claim.

## Automation API families

`vcf_automation` returns `unknown` for product-build evidence in all three supported families: `all_apps`, `vm_apps`, and `provider`. No version request is sent for these targets. The currently verified public family contracts do not provide a product-build probe implemented here. Organization service API versions and the provider `Accept` header version are API contract selections, not proof of the installed Automation build. For example, the VM Apps Blueprint [about operation](https://developer.broadcom.com/xapis/vm-apps-org-blueprint/latest/blueprint/api/about/get/) returns supported API versions, while [provider versioning](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/) defines request content negotiation. Neither is promoted to an appliance release observation.

An explicitly configured `version` remains operator-supplied context. It never replaces missing server-reported evidence. Fleet inventory may contain a managed Automation component version, but that separate observation is not substituted for a direct response from the Automation target.

## Interpreting results

Every result includes a fixed `scope`. `reported` means a recognized release or build field was observed at that scope. Missing fields, unrecognized version formats, ambiguous local manager results and unimplemented product-build contracts remain `unknown`. HTTP 401 and 403 become `access_denied`; 404 becomes `endpoint_not_found`, without a claim that the product is unsupported. Transport, response contract and request budget failures remain explicit. Recovery responses containing `_meta.errors` cannot become successful version observations.

Only allowlisted version fields are exported. Strings are limited to 128 characters containing numeric segments separated by dots or hyphens. Live validation uses numeric-only mode, which permits dots but excludes hyphens. Operations numeric fields must be nonnegative integers within the supported range. Free-text release labels, error messages, credentials, identifiers and endpoint details are excluded. A legitimate version format outside these rules remains unknown rather than being copied as arbitrary text.

These implementations have offline contract and privacy tests. No live appliance validation evidence is included with them. A result from one account, resource scope, build and time does not establish support for other releases or certify an upgrade combination. Run the [live validator](live_validation.md) against explicitly selected resources to create observed evidence for the environment.
