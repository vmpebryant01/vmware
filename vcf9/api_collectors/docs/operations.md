# VCF Operations inventory

Author: Paul Bryant

Configure `component` as `vcf_operations` and `url` as the appliance's HTTPS origin. The collector uses the `/suite-api/api` routes in the [VCF Operations API reference](https://developer.broadcom.com/xapis/vcf-operations-api/latest/).

| Resource | GET route | Response array | Collection behavior |
| --- | --- | --- | --- |
| `resources` | `/suite-api/api/resources` | `resourceList` | Zero-based pages with `page` and `pageSize` |
| `adapters` | `/suite-api/api/adapters` | `adapterInstancesInfoDto` | One request |
| `alerts` | `/suite-api/api/alerts` | `alerts` | Zero-based pages with `page` and `pageSize` |
| `policies` | `/suite-api/api/policies` | `policySummaries` | One request, policy summaries |

The documented collection contracts are [resources](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/get/), [adapters](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/adapters/get/), [alerts](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/alerts/get/), and [policies](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/policies/get/).

## Authentication

For a local account or a supported authentication source, provide `username_env` and `password_env`. Set `auth_source` only when the configured authentication source requires its name. The collector creates an OpsToken with `POST /suite-api/api/auth/token/acquire` and uses `Authorization: OpsToken <token>`, as described in the [token API](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/auth/token/acquire/post/). It releases tokens it created at completion through the documented [release API](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/auth/token/release/post/).

Alternatively, set `token_env` to the environment variable containing an existing token. `token_scheme` defaults to `OpsToken`. Set it to `Bearer` for an identity access token accepted by the installed service. Supplied tokens are not released. Both token schemes are described in the [API overview](https://developer.broadcom.com/xapis/vcf-operations-api/latest/).

Broadcom documents that password-based token generation for VMware Identity Broker users is unsupported in VCF Operations 9.0.x. Use an appropriate supported identity-token flow for that environment; the collector does not perform an interactive identity-provider login. See [Broadcom article 422959](https://knowledge.broadcom.com/external/article/422959/how-to-authenticate-vcf-operations-api-u.html).

Example target using an existing token:

```json
{
  "name": "operations",
  "component": "vcf_operations",
  "url": "https://operations.example.test",
  "token_env": "VCF_OPERATIONS_TOKEN",
  "token_scheme": "OpsToken",
  "resources": ["resources", "adapters", "alerts", "policies"],
  "filters": {
    "resources": {"adapterKind": ["VMWARE"]},
    "policies": {"activesOnly": true}
  }
}
```

## Scope and pagination

Optional `filters` use the query names documented for each resource. For example, resource inventory supports `adapterKind` and `resourceKind`, alerts support `resourceId`, adapters support `adapterKindKey`, and policies support `activesOnly`. The collector manages `page` and `pageSize` itself.

For paged results, the collector checks the documented [`pageInfo.totalCount`](https://developer.broadcom.com/xapis/vcf-operations-api/latest/data-structures/page-info/) when returned. It fails on changed totals, repeated identifiers, invalid page numbers, premature empty pages, or the configured page limit. Without a total, it requests pages until an empty array establishes completion. Collection is limited to the records visible to the configured account and filters. Policy collection contains summaries, not exported policy settings or a policy archive.

Endpoint behavior must be confirmed against the installed VCF Operations version. The supplied tests use local fixtures and do not establish compatibility with a live deployment.
