# VCF Fleet LCM inventory

Author: Paul Bryant

Set `component` to `vcf_fleet` and configure the HTTPS origin that exposes the Fleet LCM service. The collector reads the [VCF Fleet LCM Service APIs](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/), using the `/fleet-lcm/v1` routes documented below. The route's `v1` identifies the API contract; it is separate from the installed VCF product release.

| Resource | GET route | Response |
| --- | --- | --- |
| `components` | `/fleet-lcm/v1/components` | `components` array and `pageMetadata` |
| `component_nodes` | `/fleet-lcm/v1/components/{componentId}/nodes` | `nodes` array and `pageMetadata`, for each discovered component |
| `component_statuses` | `/fleet-lcm/v1/components/{componentId}/status` | Component identifier and service status, for each discovered component |

These are direct Fleet LCM requests, as specified by the [component list](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/fleet-lcm/v1/components/get/), [node list](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/fleet-lcm/v1/components/componentId/nodes/get/), and [component status](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/fleet-lcm/v1/components/componentId/status/get/) contracts. Status strings are retained as returned; `Unknown` is not converted into a healthy or failed state. Node and status records include `component_id` to identify their parent component.

## Authentication and target

Supply `token_env` naming a process environment variable that holds a bearer JWT accepted by the Fleet service. The collector uses `Authorization: Bearer <token>`, following the published [authentication schema](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/api-security-schema/). It does not acquire, refresh, or revoke that token, and sends no POST, PATCH, PUT, or DELETE requests.

```json
{
  "name": "fleet",
  "component": "vcf_fleet",
  "url": "https://fleet.example.test",
  "token_env": "VCF_FLEET_TOKEN",
  "verify_tls": true,
  "resources": ["components", "component_nodes", "component_statuses"]
}
```

All three resources are selected when `resources` is omitted. Nodes and statuses are queried only for identifiers discovered through the configured Fleet endpoint. Returned component addresses are inventory data; the collector does not connect to them.

## Pagination and scope

The component and node lists use one-based `pageNumber` and `pageSize`. Requests are capped at the documented maximum of 100 entries per page. The component API describes pagination based on SDDC LCMs, so the collector follows `pageMetadata.totalPages` and does not assume that `totalElements` equals the number of component records. It also requests inclusion of consumption VSP clusters and VCD Migrator components through the documented `includeConsumptionVsp` and `includeVcdMigrator` options. [Component list options](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/fleet-lcm/v1/components/get/).

Node collection checks both the page count and the advertised node total when available. Changed metadata, repeated identifiers, invalid page numbers, incomplete node lists, and page limits produce explicit errors. Without a page count, collection continues until an empty page. `max_pages` applies to component discovery and separately to each component's node list. [Node pagination contract](https://developer.broadcom.com/xapis/vcf-fleet-lcm-service-apis/latest/fleet-lcm/v1/components/componentId/nodes/get/).

Results reflect what the configured account can read from the Fleet service. This collector does not refresh upstream inventory, execute lifecycle operations, inspect component configuration secrets, or generate support bundles. Verify endpoint availability and permissions against the installed release. Offline fixture tests do not establish compatibility with a live VCF deployment.
