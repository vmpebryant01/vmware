# Inventory relationships

Author: Paul Bryant

Build a graph from a completed saved inventory run. This command reads files only. It does not authenticate, resolve DNS, contact endpoints, or change infrastructure.

```console
python build_relationships.py --run inventory/run-20261024 --output reports/relationships.json --csv
```

The output must be outside the input run directory. The loader accepts completed successful or incomplete runs and reads only resources that finished successfully with complete reported coverage. Failed resources appear in `unavailable_resources`; their records do not participate in matching.

The default relationships use these documented API references:

| Source | Destination | Match |
| --- | --- | --- |
| SDDC Manager `vcenters.fqdn` | A configured vCenter target | Unique normalized endpoint hostname |
| SDDC Manager `nsx_clusters.vipFqdn` | A configured NSX target | Unique normalized endpoint hostname |
| SDDC Manager `clusters.domain.id` | Same-target `domains.id` | Exact domain ID |
| Operations collected resource relationships | Same-target Operations resource IDs | Server-returned `PARENT` or `CHILD` direction |

SDDC Manager documents the server FQDN and domain ID fields in its [vCenter inventory](https://developer.broadcom.com/xapis/vmware-cloud-foundation-api/latest/v1/vcenters/get/), [NSX cluster inventory](https://developer.broadcom.com/xapis/vmware-cloud-foundation-api/latest/v1/nsxt-clusters/get/), and [cluster inventory](https://developer.broadcom.com/xapis/vmware-cloud-foundation-api/latest/v1/clusters/get/) APIs. Operations provides explicit directions and related resource objects through its [resource relationship API](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/id/relationships/get/).

Hostname matching folds letter case, removes one trailing DNS dot, and normalizes internationalized hostnames and IP address notation. Endpoint ports do not distinguish hostname matches. Multiple matching configured targets, or duplicate source hostnames within the same SDDC Manager target, produce an ambiguity without an edge. A hostname match establishes a reference to the configured endpoint; it does not verify the remote server's identity, DNS aliases, or current availability.

The graph contains `nodes`, `edges`, `ambiguous`, `unresolved`, and `unavailable_resources`. Node IDs qualify each record by target, component, resource, and supported native identity. The hash in a node ID provides a stable graph key. It does not conceal the native identity stored alongside it. Display names never establish identity.

Operations edges preserve the requested direction as `has_parent` or `has_child`, from the queried resource to its related resource. If a server-returned resource ID was outside the successful saved resource inventory, the graph creates a `record_reference` node with `inventory_available: false` and reports an unresolved inventory reference. This preserves the explicit relationship while disclosing that a full resource record was not collected. Duplicate collected resource IDs prevent an edge.

With `--csv`, each graph collection also has a JSON and CSV sidecar, such as `relationships_nodes.json` and `relationships_nodes.csv`. All exports identify Paul Bryant as author. Output documents contain inventory identifiers and endpoint hostnames, but do not include the local input run path or identity-map filename.

## Explicit identity namespaces

Cross-component matches beyond the default references require an identity map. Every rule names a component, resource, dotted record field, namespace, and normalization. `target` optionally limits a rule to one configured target. The document accepts an optional author and at most 1000 rules. Unknown fields, duplicate rules, and display-name fields are rejected.

```console
python build_relationships.py --run inventory/run-20261024 --output reports/relationships.json --identity-map identity-map.json
```

An empty map is valid:

```json
{
  "author": "Paul Bryant",
  "rules": []
}
```

Rules share a namespace only when the operator has established that the selected fields identify the same kind of object in both products. Every rule in one namespace must use the same normalization. Supported normalization values are `exact`, `uuid`, and `hostname`. Exact matching preserves the string or integer type and value without trimming or changing its case. UUID matching accepts UUID spelling variations and produces the standard lowercase form. Hostname normalization uses the rules described above. Fields resolve through objects only; array indexes and automatic searches of identifier lists are unsupported.

For example, the following rule pair applies only to richer saved inventories that actually contain a verified `instance_uuid` field in both resources. These fields are illustrative. The standard vCenter VM summary collector does not supply them. The [vCenter VM list API](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/vcenter/vm/get/) supplies a vCenter-local `vm` identifier; it cannot by itself establish a cross-product VM UUID match. Operations [resource details](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/id/get/) describe identifiers according to the resource and adapter kind, so the operator must select fields whose meaning is verified for that adapter.

```json
{
  "author": "Paul Bryant",
  "rules": [
    {
      "component": "vcenter",
      "resource": "vms",
      "field": "instance_uuid",
      "namespace": "vm_instance_uuid",
      "normalization": "uuid",
      "target": "workload-vcenter"
    },
    {
      "component": "vcf_operations",
      "resource": "resources",
      "field": "instance_uuid",
      "namespace": "vm_instance_uuid",
      "normalization": "uuid",
      "target": "operations"
    }
  ]
}
```

A namespace identity may match at most one record per target. Multiple records from one target make the entire identity group ambiguous and prevent all its identity edges. Missing or invalid fields, missing opposite-component matches, and uncollected references appear in `unresolved`. The graph does not infer relationships from similar names, coincident local IDs, or shared UUID-looking values without configured rules.

Exit code `0` means the graph was written successfully. Ambiguity and unresolved references remain in that graph for inspection; they do not change the exit code. Exit code `2` means the input run, mapping, or output location could not be processed. A saved run and its graph describe observations collected over time and are not an atomic infrastructure snapshot.
