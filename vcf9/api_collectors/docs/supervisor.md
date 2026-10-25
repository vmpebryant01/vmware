# Supervisor state and namespace quotas

Author: Paul Bryant

Collect the current summary and conditions for explicitly identified Supervisors, plus configuration status, runtime usage and quotas for explicitly identified namespaces. All collection calls are GET requests against the configured vCenter origin. The collector does not access a Kubernetes API endpoint, discover additional objects, run checks, upgrade a Supervisor or change quotas.

```powershell
python collect_vcf.py --component vcenter --config examples/supervisor-inventory.example.json --output ./inventory
python report_supervisor_health.py --run ./inventory/<completed-run> --max-used-percent 80 --output ./reports/supervisor-health.json --csv
```

Use the completed run directory printed by the collector. Supply the named credential environment variables and configure a trusted CA bundle through `verify_tls` when necessary.

Optional resources:

| Resource | Required target selector | Information |
| --- | --- | --- |
| `supervisor_summaries` | `supervisor_ids` | Name, native configuration and Kubernetes status, runtime usage and capacity, message identifiers and severity |
| `supervisor_conditions` | `supervisor_ids` | Native condition type and status, transition time, reason, severity and message identifiers |
| `namespaces` | `namespace_ids` | Hosting cluster, native configuration status, usage, dynamic resource quotas and per-policy storage limits |

Each selector accepts 1-1000 unique simple identifiers. A Supervisor identifier is distinct from a vSphere cluster identifier. Supply the identifiers for the API objects you intend to inspect; the scripts do not match display names or infer a namespace's Supervisor from a cluster name. `namespace_ids` is unnecessary when collecting only Supervisor resources, and `supervisor_ids` is unnecessary for namespace-only collection. These resources reject arbitrary filters.

The collector stores its explicit identifier scope with every resource. A failure during collection leaves that resource incomplete, so a partial fan-out cannot establish coverage. The offline report excludes duplicated or out-of-scope records and emits unknown evidence when a selected scope cannot be assessed. A missing or empty conditions response is not interpreted as a healthy Supervisor.

The report preserves native statuses and condition polarity instead of assigning a universal healthy label to a true or false condition. It shows Supervisor CPU, memory and storage usage percentages where both native values are valid and capacity is positive. CPU usage and capacity are in MHz; memory and storage usage and capacity are in MiB. The threshold is an operator review threshold, not a vendor alarm definition. A zero or missing capacity yields an unknown percentage.

Namespace `resource_spec` is a dynamic vendor schema. Quota keys and scalar values are preserved with their native units and are not converted into percentages. Unexpected nested quota structures are rejected rather than interpreted. Missing resource constraints remain null. Each `storage_specs.limit` is a limit in mebibytes for its associated storage policy; a missing limit is null and means no limit for that policy. Total namespace storage usage is not attributed to individual policies and is never divided by each policy limit.

Summary, conditions and namespace reads occur separately. Their collection times are retained; they do not form an atomic snapshot. Report `success` describes evidence completeness, including unhealthy native states or exceeded review thresholds. It does not certify workload availability. This report covers management API observations, not guest Kubernetes clusters, pod events or application health.

The Supervisor Summary and Conditions APIs were added in vSphere API 8.0.0.1. They are used instead of the cluster summary fields deprecated in API 9.1.0.0. Namespace information is read through the namespace Instances API. Native status fields and permissions may vary by installed build; test them with an account authorized to read the selected objects. An inaccessible object remains unknown, including a not-found response that can also indicate missing read privilege.

Public API references:

- [Supervisor Summary GET](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/namespace-management/supervisors/supervisor/summary/get/)
- [Supervisor SDK statistics and metric units](https://dp-downloads-pstg.broadcom.com/api-content/apis/API_VAA_003/Python%208.0/html/8.0.0.1/com.vmware.vcenter.namespace_management.html)
- [Supervisor Conditions GET](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/namespace-management/supervisors/supervisor/conditions/get/)
- [Namespace information GET](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/namespaces/instances/namespace/get/)
- [Namespace storage specification and limit units](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/data-structures/Vcenter%20Namespaces%20Instances%20StorageSpec/)
- [Deprecated cluster fields and their replacements](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/data-structures/Vcenter%20NamespaceManagement%20Clusters%20Info/)
