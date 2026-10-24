# vCenter inventory partitioning

Author: Paul Bryant

vCenter inventory list APIs have result limits rather than cursor pagination. The collector automatically narrows a query when its returned count reaches a documented boundary, then combines complete child scopes by stable object ID. The original resource filters remain constraints on every child request.

| Resource | Documented list limit | Reference |
| --- | --- | --- |
| Datacenters | 1,000 | [Datacenter list](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/datacenter/get/) |
| Clusters | 1,000 | [Cluster list](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/cluster/get/) |
| Hosts | 2,500 | [Host list](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/host/get/) |
| Datastores | 2,500 | [Datastore list](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/datastore/get/) |
| Networks | 1,000 | [Network list](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/network/get/) |
| VMs | 4,000 | [VM list](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/vm/get/) |

The APIs document HTTP 500 with `UnableToAllocateResource` when too many objects match. A transport error that exposes only HTTP 500 does not identify its cause. The collector retains that uncertainty in collection metadata and accepts narrower results only when all child scopes establish coverage. Other HTTP failures and typed backend errors propagate as failures.

## Automatic behavior

The collector first issues the configured query. A successful response below the boundary completes that scope. At the boundary, it first divides any configured array filter into smaller subsets while retaining every other filter. Subsets are divided again when needed. For example, splitting an original `hosts` list preserves its accompanying datacenter, cluster, folder, name, and power-state constraints. Exact names remain exact names; the collector does not invent wildcard or identifier-prefix queries. Supported filter fields are specified in the linked resource APIs.

If the resource supports a datacenter filter and no datacenter restriction is already present, the collector discovers visible datacenters and queries each one. Datacenter discovery must itself complete below its limit. It does not apply a different resource's configured filters to that discovery.

For a VM query that remains capped within a datacenter, the collector can divide the scope into `POWERED_OFF`, `POWERED_ON`, and `SUSPENDED`. These are the power-state values in the [official Automation SDK binding](https://dp-downloads-pstg.broadcom.com/api-content/apis/API_VAA_003/Python%208.0/html/8.0.0.1/com.vmware.vcenter.html#com.vmware.vcenter.vm_client.Power.State); the [current vSphere power-state model](https://developer.broadcom.com/xapis/vsphere-web-services-api/latest/vim.VirtualMachine.PowerState.html) defines the corresponding three states. An unknown state observed in a parent response prevents this split. The [current VM summary](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/data-structures/Vcenter%20VM%20Summary/) requires the VM ID and power state even when CPU and memory configuration details are unavailable.

Automatic datacenter and power-state partitions retain VMs without a usable host association. The collector does not replace an unrestricted VM query with queries for discovered hosts, or replace unrestricted host inventory with cluster-only queries. Such substitutions could omit orphaned VMs or standalone hosts. The [host filter contract](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/host/get/) explicitly includes hosts outside clusters when the cluster filter is absent.

## Coverage and limits

The collector fails the resource when a child remains capped and no exhaustive supported split remains. It also fails for capped datacenter discovery, missing stable IDs, an observed parent object absent from the child union, unexpected overlap between datacenters, conflicting object records, or an exhausted request budget. An incomplete resource does not return partial rows for export.

An irreducible child requires a narrower explicit scope, such as a supplied list of VM IDs, exact names, folders, datacenters, clusters, or hosts. A single datacenter with more than 4,000 VMs in one power state can still require such a scope. The collector does not infer completeness from the number of discovered hosts or guess IDs for missing objects.

Complete partitions are rechecked, together with the discovered datacenter set, before returning the collection. Identical objects from overlapping configured scopes are deduplicated by their stable resource ID. Changes detected during these checks fail the resource. These sequential requests are not an atomic snapshot, so collect during a stable inventory interval when a consistent baseline matters.

For vCenter, `max_pages` is the total API query budget for one resource, including discovery and verification. The metadata's `request_count` counts these queries; configured transport retries can add HTTP attempts. Collection metadata records the strategy, original filters, query and partition counts, deduplicated records, individual query outcomes, coverage status, and any missing coverage. Coverage remains limited to the configured scope and the objects visible to the account.

Offline tests include a 5,001-VM inventory, overlapping folder filters, standalone and disconnected hosts, hostless VMs, changed partitions, capped children, request limits, and error propagation. They do not establish compatibility with a live vCenter build.
