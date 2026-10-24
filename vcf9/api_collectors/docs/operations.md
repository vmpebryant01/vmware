# VCF Operations inventory

Author: Paul Bryant

Configure `component` as `vcf_operations` and `url` as the appliance's HTTPS origin. The collector uses the `/suite-api/api` routes in the [VCF Operations API reference](https://developer.broadcom.com/xapis/vcf-operations-api/latest/).

| Resource | GET route | Response array | Collection behavior |
| --- | --- | --- | --- |
| `resources` | `/suite-api/api/resources` | `resourceList` | Zero-based pages with `page` and `pageSize` |
| `adapters` | `/suite-api/api/adapters` | `adapterInstancesInfoDto` | One request |
| `alerts` | `/suite-api/api/alerts` | `alerts` | Zero-based pages with `page` and `pageSize` |
| `policies` | `/suite-api/api/policies` | `policySummaries` | One request, policy summaries |
| `latest_metrics` | `/suite-api/api/resources/stats/latest` | `values` with nested `stat-list.stat` | Optional, explicitly scoped resources and metric keys |
| `relationships` | `/suite-api/api/resources/{id}/relationships` | `resourceList` | Optional, paged parents and children for explicitly scoped resources |

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

## Selected latest metrics

Select `latest_metrics` in `resources`, and provide both `resource_ids` and `stat_keys` as nonempty arrays of unique strings. These options restrict collection to the requested Operations resource identifiers and exact metric keys. Neither scoped collector is included in the default resources, so an ordinary inventory run does not start querying metrics across the environment.

```json
{
  "name": "operations-metrics",
  "component": "vcf_operations",
  "url": "https://operations.example.test",
  "token_env": "VCF_OPERATIONS_TOKEN",
  "resources": ["latest_metrics", "relationships"],
  "resource_ids": ["replace-with-operations-resource-id"],
  "stat_keys": ["cpu|usage_average"]
}
```

Use identifiers returned by Operations resource inventory and metric keys applicable to that resource kind. The example metric key is illustrative. Each array is limited to 1,000 entries by the collector. Metric requests use the documented repeated `resourceId` and `statKey` query parameters and request `maxSamples=1`. Resources are queried individually so a response can be checked against its exact requested scope. [Latest stats API](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/stats/latest/get/).

Each returned metric record retains the API's `timestamps`, `data`, `statKey`, `intervalUnit`, and any additional series fields. The collector adds `resource_id`, `resource_name`, `stat_key`, and `unit`. Sample timestamps remain the values returned by the API; the file collection time does not replace the measurement timestamp. `maxSamples=1` requests the most recent sample, which may still be old if the resource has stopped publishing. No freshness guarantee or unit conversion is inferred.

The latest-stats response does not document measurement units. To obtain them, the collector reads the selected [resource's adapter kind and resource kind](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/id/get/), then requests the corresponding [attribute metadata](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/adapterkinds/adapterKindKey/resourcekinds/resourceKindKey/statkeys/get/) for the selected keys. `unit` is populated only from an exact attribute-metadata key match. It is `null` when the service supplies no matching unit. An additional series `unit` field is preserved separately as `reported_series_unit`; a nonempty value that conflicts with the attribute metadata fails collection. The API's `intervalUnit` describes the sample interval and is retained separately from the measurement unit.

When a requested resource and metric key has no returned samples, its output record contains empty `timestamps` and `data` arrays and `availability: "no_samples_returned"`. It contains no fabricated zero or current timestamp. Record counts therefore include these explicit missing-sample records. Mismatched sample-array lengths, unexpected resources or metric keys, and malformed unit metadata cause collection errors.

## Resource relationships

Select `relationships` and provide `resource_ids`. The collector issues separate `relationshipType=PARENT` and `relationshipType=CHILD` requests using the documented [relationships API](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/id/relationships/get/). Every record contains the source `resource_id`, its `relationship_type`, the `related_resource_id`, and the related resource details as returned by Operations. The direction describes the related resource relative to the requested source, so a `PARENT` row identifies a parent of `resource_id`.

Each direction uses zero-based `page` and `pageSize`, checks `pageInfo.totalCount` when present, and rejects incomplete or repeated results. Without a total, requests continue until an empty page. `max_pages` bounds each resource and direction separately. These records describe Operations parent and child relationships visible to the account; they do not infer relationships from similar names or represent every possible relationship type.
