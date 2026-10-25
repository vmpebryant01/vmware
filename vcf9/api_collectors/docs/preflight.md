# Read-only preflight

Author: Paul Bryant

Preflight checks the selected targets before a full collection. It uses the configured authentication and trusted TLS settings, probes reported component versions where a verified endpoint is available, and sends a single representative GET for each selected resource. It closes sessions created by the collector through the normal cleanup workflow.

```powershell
python .\collect.py --config .\config.json --preflight --output .\inventory
```

The result contains per-target connectivity, TLS, authentication, version, capability, and cleanup observations. It exports only approved version fields and probe results. Inventory response bodies, credentials, tokens, and raw error messages are excluded.

## Reading the result

| Observation | Meaning |
| --- | --- |
| `reachable` connectivity and `verified` TLS | An HTTPS operation completed using the configured trust settings. |
| `session_established` authentication | The configured credentials established a product session, before any independent inventory permission check. |
| `configured` authentication | Credentials or an external token were configured; a protected request has not yet confirmed access. |
| `verified` authentication | A protected request succeeded. This does not establish access to every object or operation. |
| `accessible` capability | One GET succeeded for the stated representative resource scope. |
| `not_probed` capability | No request was sent, for example because explicit scope identifiers were missing. |
| `access_denied` | HTTP 401 or 403. Confirm authentication, site context, and permissions. |
| `endpoint_not_found` | HTTP 404. This is not classified as proof that an API is unsupported. |
| `tls_error` | The transport classified a TLS setup or validation error. |
| `network_error` | The transport classified a connection or network error. |
| `query_failure` | Another request or response failure occurred. |

The overall status is `incomplete` when an actual probe, authentication operation, or cleanup fails. It is `partial` when probes were skipped without an actual error. Skipped probes appear as `not_probed` with scope limitations. Start and completion timestamps use UTC. An optional `configured_version` is an operator-supplied value and remains separate from the detected version fields.

## Version observations

| Component | Version GET | Exported fields |
| --- | --- | --- |
| SDDC Manager | `/v1/system/appliance-info` | `version`. |
| vCenter | `/api/appliance/system/version` | `version`, `build`. |
| NSX | `/api/v1/node` | `node_version`, `product_version`. |
| VCF Operations | `/suite-api/api/versions/current` | `major`, `minor`, `minorMinor`, `patch`, `buildNumber`, `releaseName`. |

The version remains unknown for HCX, VCF Fleet, VCF Automation, Live Site Recovery, and vSphere Replication. A configured version string is not substituted for a detected version. A failed version request does not stop the independent protected capability probes. Version requests alone do not mark authentication as verified.

The vCenter version fields come from its [appliance system version API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/appliance/system/version/get/).

NSX's node endpoint requires no permissions, so its successful response does not validate the supplied authentication. Only a successful protected inventory probe establishes access in this preflight. See the [NSX node API](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ReadNodeProperties.html), [SDDC appliance information](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/system/appliance-info/get/), and [Operations version API](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/versions/current/get/).

## Scope and request limits

Paged APIs request the first page with one record. The preflight does not follow cursors, enumerate domains or pairings, inspect all returned objects, validate full pagination, or run complete resource collectors.

For certificate metadata, supply explicit `domain_ids`; only the first ID is probed. Firewall rules use the first configured `policy_ids` entry. Recovery resources require an explicit `pairing_id`, and mappings use the first configured `srm_ids` entry. Recovery probes follow the existing approved remote-session authentication workflow where needed, without discovering additional pairings or appliances.

Operations metrics use only the first configured resource ID and statistic key, requesting one latest sample. Relationship preflight checks only the first resource and the `PARENT` direction. It does not query measurement-unit metadata or establish complete relationship coverage.

Fleet component preflight requests `/fleet-lcm/v1/components` with `pageNumber=1`, `pageSize=1`, `includeConsumptionVsp=true`, and `includeVcdMigrator=true`. Component node and status probes remain `not_probed` because preflight does not discover component IDs.

vCenter and HCX list methods without a documented page-size selector receive one request, which can return more than one record. Existing configured vCenter filters are preserved. APIs with broader unpaginated collection methods retain their normal response-size limit.

Preflight is a current access observation. It does not certify product compatibility, every permission, inventory completeness, certificate health, security posture, or recovery readiness. No live infrastructure was used for the included offline tests.
