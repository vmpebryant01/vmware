# VCF Automation inventory

Author: Paul Bryant

The `vcf_automation` component collects organization or provider inventory using one explicitly selected API family. Configure a separate target for each family and authorization context you need. Authentication uses an already issued bearer access token supplied through `token_env`; the collector makes only GET requests for this component.

## API families and release scope

| `api_family` | Default resources | Public contract used |
| --- | --- | --- |
| `all_apps` | `projects`, `blueprints`, `deployments` | Current VCF Automation All Apps Org API references, published in the 9.1 and 9.1.1 documentation families. |
| `vm_apps` | `projects`, `blueprints`, `deployments`, `cloud_accounts`, `cloud_zones`, `fabric_networks` | Current VCF Automation VM Apps Org references, including its explicitly documented IaaS service. |
| `provider` | `organizations`, `regions`, `provider_zones`, `supervisor_namespaces`, `virtual_private_clouds` | Provider Infrastructure API with an explicitly configured 9.x API version. Modern region, zone, namespace summary, and VPC methods are marked as added in 9.0.0. |

These are documented contracts, not a claim of successful testing against every VCF 9.x release. No live VCF Automation endpoint has been tested. Confirm the selected endpoints and requested API version against your installed release.

The All Apps and VM Apps services are separate product API families, even where they expose similarly named routes. IaaS cloud accounts, cloud zones, and fabric networks are enabled only for `vm_apps`. They are not used as substitutes for All Apps Supervisor or provider infrastructure inventory. The [All Apps organization API index](https://developer.broadcom.com/xapis/org-management-all-apps-org/latest/) and [VM Apps organization API index](https://developer.broadcom.com/xapis/org-management-vm-apps-org/latest/) identify the respective services.

This component does not enumerate the complete Kubernetes-style VCF Automation Consumption API, every Supervisor object, or every organization through tenant credentials. Broadcom documents a separate [Consumption API](https://developer.broadcom.com/xapis/cci-api/latest/) and explains that VCF Automation 9.0.x tenant Kubernetes OpenAPI schemas can be obtained from the tenant context in its [OpenAPI guidance](https://knowledge.broadcom.com/external/article/436633/vcfa-rest-api-endpoints-are-not-included.html). The availability of those schemas for a particular deployment has not been verified here.

## Configuration examples

Add the required targets to the main configuration's `targets` array. Replace the example endpoints and version values with those for your environment. Omit `resources` to use the selected family's defaults, or select a nonempty subset of the resources listed above.

An All Apps organization target:

```json
{
  "name": "automation-all-apps",
  "component": "vcf_automation",
  "url": "https://automation.example.com",
  "api_family": "all_apps",
  "token_env": "VCFA_ALL_APPS_ACCESS_TOKEN",
  "verify_tls": true,
  "resources": ["projects", "blueprints", "deployments"]
}
```

A VM Apps organization target:

```json
{
  "name": "automation-vm-apps",
  "component": "vcf_automation",
  "url": "https://automation.example.com",
  "api_family": "vm_apps",
  "token_env": "VCFA_VM_APPS_ACCESS_TOKEN",
  "verify_tls": true
}
```

A provider target:

```json
{
  "name": "automation-provider",
  "component": "vcf_automation",
  "url": "https://automation.example.com",
  "api_family": "provider",
  "api_version": "9.1.1",
  "token_env": "VCFA_PROVIDER_ACCESS_TOKEN",
  "verify_tls": true
}
```

For provider targets, `api_version` is required and becomes the `Accept` header, for example `application/json;version=9.1.1`. Choose a version supported by the installed service. The optional provider-only `org_id` sets `X-VMWARE-VCLOUD-TENANT-CONTEXT` for a specific organization context. Omitting it preserves the supplied token's normal provider visibility. See the [provider authentication, context, and versioning rules](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/).

Tenant services use the organization context associated with the supplied access token. The provider `api_version` option is not accepted for `all_apps` or `vm_apps`, whose services have separate API version schemes. Credentials and refresh tokens are not accepted as substitutes for an access token.

## Supplying access tokens

Obtain an access token through the supported VCF Automation authentication flow for the intended tenant or provider context. A tenant API token is a refresh credential, not the access token required by this collector. Follow the authentication guidance in the relevant [organization API documentation](https://developer.broadcom.com/xapis/org-management-all-apps-org/latest/) or [provider documentation](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/).

For an All Apps target in PowerShell, enter the issued access token without an `Authorization:` label or `Bearer ` prefix:

```powershell
$accessToken = Read-Host "Issued All Apps bearer access token" -AsSecureString
$env:VCFA_ALL_APPS_ACCESS_TOKEN = [System.Net.NetworkCredential]::new("", $accessToken).Password
try {
    python .\collect.py --config .\config.json --output .\inventory --target automation-all-apps
} finally {
    Remove-Item Env:VCFA_ALL_APPS_ACCESS_TOKEN -ErrorAction SilentlyContinue
    Remove-Variable accessToken -ErrorAction SilentlyContinue
}
```

Use the corresponding environment variable for other targets. The token is temporarily present in the process environment. The collector does not renew or revoke caller-owned tokens. An expired token fails authentication at the API; supply a fresh access token and rerun.

## Endpoints and pagination

| Resource | GET path | Pagination |
| --- | --- | --- |
| `projects` | `/project-service/api/projects` | Zero-based `page`, `size`; `content` records. Viewer and Supervisor-only projects are included when permitted by the account. |
| `blueprints` | `/blueprint/api/blueprints` | Zero-based `page`, `size`; draft blueprint `content` records. |
| `deployments` | `/deployment/api/deployments` | Zero-based `page`, `size`; `content` records. |
| `cloud_accounts` | `/iaas/api/cloud-accounts` | `$top`, `$skip`, `$count=true`; `content` records. |
| `cloud_zones` | `/iaas/api/zones` | `$top`, `$skip`; `content` records. |
| `fabric_networks` | `/iaas/api/fabric-networks` | `$top`, `$skip`, `$count=true`; `content` records. |
| `organizations` | `/cloudapi/1.0.0/orgs` | One-based `page`, `pageSize` capped at 128; `values` records. |
| `regions` | `/cloudapi/v1/regions` | Same provider pagination. |
| `provider_zones` | `/cloudapi/v1/zones` | Same provider pagination. |
| `supervisor_namespaces` | `/cloudapi/v1/namespaceSummaries` | Same provider pagination; namespace summaries created through Provider Management. |
| `virtual_private_clouds` | `/cloudapi/v1/vpcs` | Same provider pagination. |

Provider method pages describe a minimum and default page value of 1 while also containing inconsistent "zero offset" prose. The collector follows the explicit minimum of 1 and reports a conflicting returned page number as an error. It does not silently switch numbering schemes.

Collection checks available total and page counts, detects repeated pages and resource identifiers, and fails when pagination stops early or exceeds `max_pages`. A short page alone does not establish completion. IaaS offsets advance by the actual number of returned records. These checks do not create a point-in-time snapshot while the platform is changing.

The exported inventory covers only records visible to the token and selected API family. Blueprint content and deployment inputs can contain embedded configuration; field-name redaction cannot remove secrets inside arbitrary strings. Treat these exports as sensitive inventory. This is not a configuration backup or a full tenant content export.

## Public method references

- All Apps: [projects](https://developer.broadcom.com/xapis/all-apps-org-projects/latest/project-service/api/projects/get/), [draft blueprints](https://developer.broadcom.com/xapis/all-apps-org-blueprint/latest/blueprint/api/blueprints/get/), and [deployments](https://developer.broadcom.com/xapis/all-apps-org-instances/latest/deployment/api/deployments/get/).
- VM Apps: [projects](https://developer.broadcom.com/xapis/vm-apps-org-project/latest/project-service/api/projects/get/), [draft blueprints](https://developer.broadcom.com/xapis/vm-apps-org-blueprint/latest/blueprint/api/blueprints/get/), [deployments](https://developer.broadcom.com/xapis/vm-apps-org-deployment/latest/deployment/api/deployments/get/), [cloud accounts](https://developer.broadcom.com/xapis/vm-apps-org-provisioning-service/latest/iaas/api/cloud-accounts/get/), [cloud zones](https://developer.broadcom.com/xapis/vm-apps-org-provisioning-service/latest/iaas/api/zones/get/), and [fabric networks](https://developer.broadcom.com/xapis/vm-apps-org-provisioning-service/latest/iaas/api/fabric-networks/get/).
- Provider: [organizations](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/cloudapi/1.0.0/orgs/get/), [regions](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/cloudapi/v1/regions/get/), [zones](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/cloudapi/v1/zones/get/), [namespace summaries](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/cloudapi/v1/namespaceSummaries/get/), and [VPCs](https://developer.broadcom.com/xapis/provider-infrastructure-apis/latest/cloudapi/v1/vpcs/get/).
