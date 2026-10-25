# vSAN health and capacity

Author: Paul Bryant

The `vsan` component queries a configured vCenter through the Virtual Infrastructure JSON API. It uses the Python standard library and does not require the vSAN SDK. Collection is limited to explicitly configured vCenter cluster managed-object IDs.

| Resource | Query |
| --- | --- |
| `health_summary` | Cached cluster health, object health state counts, physical-disk health, disk balance, network and limit summaries |
| `space_usage` | Physical total and free capacity, space overview, and additional capacity fields returned by the server |

Both resources are selected by default. The queries return one object per requested cluster and do not expose pagination. The documented service singletons and query routes are [vSAN cluster health](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/v-san-service-api/vsan-vc-cluster-health-system/), [health summary query](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/sdk/vim25/release/vsan/VsanVcClusterHealthSystem/moId/VsanQueryVcClusterHealthSummary/post/), [space report service](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/v-san-service-api/vsan-space-report-system/), and [space usage query](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/sdk/vim25/release/vsan/VsanSpaceReportSystem/moId/VsanQuerySpaceUsage/post/).

## Configure and collect

Add this target to the configuration's `targets` array:

```json
{
  "name": "storage-vcenter",
  "component": "vsan",
  "url": "https://vcenter.example.test",
  "username_env": "VSAN_USERNAME",
  "password_env": "VSAN_PASSWORD",
  "verify_tls": true,
  "api_version": "9.0.0.0",
  "cluster_ids": ["domain-c123", "domain-c456"],
  "resources": ["health_summary", "space_usage"]
}
```

Use the native `cluster` IDs from the vCenter [cluster list API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/cluster/get/). Display names and SDDC Manager cluster IDs cannot substitute for these vCenter managed-object IDs. The collector accepts 1 to 1000 unique IDs of the form `domain-c123` and queries only that list.

```console
python collect.py --config config.json --component vsan --preflight
python collect.py --config config.json --component vsan --output inventory --csv
```

Preflight queries the first configured cluster for each selected resource and reports that scope. It does not establish access or health for the remaining clusters. Collection queries every configured cluster. A failed cluster query fails that resource; a partial list is not exported as successful inventory.

The default schema release is `9.0.0.0`; accepted values are `9.0.0.0`, `9.1.0.0`, and `9.1.1.0`. Before sending credentials, the collector reads anonymous `ServiceInstance.content` at the configured origin and requires `about.apiType` to be `VirtualCenter`, a 9.x server API, and a newest server API version at least as high as the configured schema. The [JSON API introduction](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/) documents discovery, and [AboutInfo](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/data-structures/AboutInfo/) defines these server fields. These checks establish the requested API scope; they do not prove live compatibility. The current public `latest` reference describes 9.1.1.0. No live vSAN environment was used to validate this collector.

## Authentication and query boundary

The collector discovers the SessionManager reference from `ServiceInstance.content`, then sends `userName` and `password` to the documented JSON [Login operation](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/sdk/vim25/release/SessionManager/moId/Login/post/). It uses the `vmware-api-session-id` response header for subsequent requests and logs out only a session it created. The [JSON authentication instructions](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/) show this header exchange.

Alternatively, replace both credential environment fields with `token_env` naming an existing JSON API session header value. It must be a session accepted by this JSON API on the configured vCenter, not an arbitrary bearer token. Supplied sessions are never revoked.

The two inventory operations use POST because they are documented query methods. Their bodies are restricted to explicit `ClusterComputeResource` references and fixed query options. Health always sets `fetchFromCache: true` and `includeObjUuids: false`. The collector does not start health tasks, VM creation tests, network performance tests, repairs, disk changes, or rebalancing. Both query contracts require `System.Read` on the cluster. [Health query options and privileges](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/sdk/vim25/release/vsan/VsanVcClusterHealthSystem/moId/VsanQueryVcClusterHealthSummary/post/), [space query options and privileges](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/sdk/vim25/release/vsan/VsanSpaceReportSystem/moId/VsanQuerySpaceUsage/post/).

Raw exports retain the native response fields and add `cluster_id`, `api_version`, and `server_api_version`. Health also adds `fetch_from_cache: true`. Optional missing fields remain missing. UI-oriented `groups` are not requested or parsed; Broadcom recommends programmatic fields for consumers of the [health summary schema](https://developer.broadcom.com/xapis/vsan-management-api/latest/vim.cluster.VsanClusterHealthSummary.html).

## Build the saved-run report

```console
python report_vsan_health.py --run inventory/run-20261025 --output reports/vsan-health.json --max-used-percent 80 --csv
```

This report reads completed saved inventories without making network requests. It combines records only by the same target and `cluster_id`. When a document saves its requested `cluster_ids`, missing clusters receive explicit unavailable records and rows outside that scope are excluded. Duplicate summaries are ambiguous. Failed or unavailable resources are excluded. Missing fields become explicit unknown values, and the report status becomes `partial` when required reporting sections are unavailable. Report status describes data coverage; a report with complete data can still contain a red or yellow native health status.

The report preserves the native health state, description, score, server check timestamp, and collection timestamps. Cached check time may precede collection substantially. Object counts remain grouped by the server's health-state labels. Detailed per-object UUID enumeration is not requested. Physical-disk records contain returned host and disk health fields; host collection errors remain visible. The [physical-disk summary contract](https://developer.broadcom.com/xapis/vsan-management-api/latest/vim.host.VsanPhysicalDiskHealthSummary.html) identifies a host error as a collection failure.

Capacity calculations use documented `totalCapacityB` and `freeCapacityB` byte values: used bytes equal total minus free, and usage percentage equals used divided by total. `threshold_exceeded` is true only when the unrounded percentage is greater than `max_used_percent`. This is an operator-selected reporting threshold, separate from the server's optional `capacityHealthThreshold`. A zero total or absent/invalid free capacity leaves the percentage and threshold result unknown. These values describe physical capacity including data, metadata, and overhead; they do not estimate free usable capacity under a storage policy. The [space usage response](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/sdk/vim25/release/vsan/VsanSpaceReportSystem/moId/VsanQuerySpaceUsage/post/) defines these fields and the separate effective-capacity data.

Health and capacity are separate observations and do not form an atomic snapshot. The report does not infer healthy disks, inaccessible-object absence, or policy compliance from a successful capacity response.
