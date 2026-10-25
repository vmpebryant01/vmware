# Live collector validation

Author: Paul Bryant

`validate_live_api.py` exercises the selected collectors against explicitly configured appliances. It validates response structures and pagination using the same collector code as normal inventory collection. It writes observed release/build evidence, per-resource contract outcomes, and a CSV version matrix. It does not declare a product or release universally compatible.

Specify `resources` for every selected target. Keep the selection small and supply the same environment credentials and verified TLS settings used for collection. All addresses come from configuration; the tool does not connect to discovered managers.

```powershell
python .\validate_live_api.py --config .\examples\operations-maintenance.example.json --validate-config
python .\validate_live_api.py --config .\config.json --target management-vcenter --max-requests 25 --max-pages 10 --capture-fixtures --output .\validation
```

The first command only validates configuration and selection. The second contacts the selected target. Environment credentials are required for that run. Use a copy of the example with real endpoints and identifiers before live use.

Each invocation creates a new output directory containing `validation.json` and `tested_versions.csv`. Optional `structural_fixtures.json` contains up to three successful response shapes per selected resource. These files use aliases such as `target_001`, in selected configuration order, rather than manager names or addresses. No mapping to actual managers is exported. Keep your configuration locally to identify the selected targets.

## Request and coverage limits

The default request budget is 25 calls per target, including authentication and version queries. HTTP retries are disabled. `--max-pages` limits collector pagination or logical query batches to three by default; individual collectors can make additional helper requests, all constrained by the request budget. Both limits are explicit and bounded. Session cleanup has a separate allowance of four calls so an exhausted read budget does not prevent closing owned sessions. Session calls follow each product's existing authentication protocol, and read-query POSTs retain the same exact route, action and body restrictions as normal collection.

`contract_validated` means the collector completed its configured account-visible resource under those limits. Empty successful responses validate their envelope only. A page limit, repeated cursor, HTTP error, malformed response or exhausted request budget produces a partial result, never a claim of complete coverage. The validator does not trigger scans, remediate infrastructure, change configuration or perform recovery operations.

## Build evidence

Numeric release/build fields are obtained through the existing documented probes for SDDC Manager, vCenter, NSX and Operations. A configured `version` label is not evidence that the installed build was tested. Missing version permissions, unrecognized version formats, and components without a verified version probe remain unknown in the matrix. Successful selected reads are retained even when the version probe fails, but the overall result remains partial.

Use the matrix as evidence of one account, configured scope and observation time. A passing result does not prove all permissions, all API variants, empty-resource item schemas, unvisited pagination paths or interoperability between connected products. The toolkit has offline tests; no live appliance validation results are distributed with it.

## Structural fixtures

Fixtures retain only allowlisted literal schema field names, observed JSON types and bounded array lengths/samples. All scalar response values are removed, including identifiers, names, addresses, counters, timestamps, tokens and free text. Unknown object keys are never written, because map keys can contain sensitive identifiers. Authentication responses, request paths, query parameters, request bodies and response headers are excluded.

These are partial structural test fixtures, not replayable inventory responses. `vcf_inventory.live_validation.shape_matches(response, fixture["shape"])` can check the observed field types against another response in a local test. Omitted branches, unknown keys and original array sizes are not assertions; use the collector's existing tests for semantic rules and pagination behavior. Captures from an ultimately failed resource remain observations, not proof that its contract passed. The per-resource outcome in `validation.json` determines that result.

## Public API references

- [SDDC Manager appliance information](https://developer.broadcom.com/xapis/sddc-manager-api/latest/v1/system/appliance-info/get/)
- [vCenter appliance version](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/appliance/appliance-system-version/)
- [NSX node information](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/latest/method_ReadNodeProperties.html)
- [Operations current version](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/versions/current/get/)
- Each resource uses the product-specific public API references in the collection and report guides linked from the [toolkit README](../README.md).

Validate methods and permissions against the exact installed component build. The shared transport's TLS checks, redirect refusal, environment credentials and read-query restrictions apply to this tool as well.
