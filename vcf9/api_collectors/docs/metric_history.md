# Historical performance and capacity samples

Author: Paul Bryant

Use `metric_history` for selected VCF Operations metrics over one or two explicit windows. The collector uses the documented [historical statistics GET](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/stats/get/), which accepts millisecond UTC `begin` and `end`, metric keys, rollups and intervals. These reads use the same supported Operations authentication as [Operations inventory](operations.md). Existing `latest_metrics` collection remains available for a single recent sample.

## Configuration

```json
{
  "author": "Paul Bryant",
  "targets": [
    {
      "name": "operations-history",
      "component": "vcf_operations",
      "url": "https://operations.example.test",
      "token_env": "VCF_OPERATIONS_TOKEN",
      "resources": ["metric_history"],
      "resource_ids": ["replace-with-operations-resource-id"],
      "stat_keys": ["cpu|usage_average"],
      "metric_history": {
        "windows": [
          {"label": "earlier", "begin": "2026-10-23T00:00:00Z", "end": "2026-10-24T00:00:00Z"},
          {"label": "later", "begin": "2026-10-24T00:00:00Z", "end": "2026-10-25T00:00:00Z"}
        ],
        "rollup_type": "AVG",
        "interval_type": "MINUTES",
        "interval_quantifier": 5
      }
    }
  ]
}
```

Replace the resource identifier, metric keys and dates with values appropriate to your installation. Resource identifiers come from Operations inventory; CPU, memory and storage metric keys depend on the adapter and resource kind. A metric name alone does not establish its unit or whether it represents physical, allocated or usable capacity.

Windows require explicit time zones, positive millisecond timestamps and durations greater than zero and no longer than 366 days. Labels must be unique and contain 1-40 letters, digits, underscores or hyphens. The collector supports `AVG`, `MIN`, `MAX`, `SUM` and `COUNT`, and fixed `SECONDS`, `MINUTES`, `HOURS`, `DAYS` and `WEEKS` intervals. It requires an integer interval quantifier of 1-1,000,000. Calendar months and years, latest-sample queries, raw unbounded streams and dynamic thresholds are outside this collector's scope.

Each resource/key/window combination is a separate GET. The limits are 1,000 combinations, 10,000 nominal intervals per window, and 1,000,000 nominal samples across the target. A returned series is limited to 10,001 samples to allow an endpoint sample; the target is also limited to 1,000,000 returned samples. `max_pages` is the total logical request budget for this resource, including resource metadata, measurement-unit metadata and historical queries. There is no undocumented pagination fallback. Unexpected continuation metadata fails collection.

```powershell
python collect.py --config history.json --output inventory --csv
python report_metric_history.py --run inventory/COMPLETED_RUN --output reports/metric-history.json --csv
```

The common command is `vcf-report --report metric_history`. The report reads a completed saved run and makes no API calls. It compares the two windows within a saved target; it does not require `--previous`.

## Units and returned sample semantics

The collector obtains units only from exact matching [attribute metadata](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/adapterkinds/adapterKindKey/resourcekinds/resourceKindKey/statkeys/get/) after reading the selected [resource metadata](https://developer.broadcom.com/xapis/vcf-operations-api/latest/suite-api/api/resources/id/get/). The original metric unit is `metric_unit`. `unit` describes the sampled metric values when applicable and is unknown if metadata is missing. For `COUNT`, `unit` remains unknown because the source metric's unit does not describe a count of observations. A conflicting nonempty series unit fails collection.

Requested rollup and cadence are saved separately from the API's returned [`rollUpType` and `intervalUnit`](https://developer.broadcom.com/xapis/vcf-operations-api/latest/data-structures/stats/). Missing or different returned metadata leaves cadence estimates and period comparisons unknown. Returned arrays are validated for finite numbers, unique timestamps, matching lengths and the requested window. Paired timestamps and values are sorted together. Unrequested resources or metric keys fail collection. Empty results produce explicit empty arrays, never fabricated zeros.

The outer [`values` array](https://developer.broadcom.com/xapis/vcf-operations-api/latest/data-structures/stats-of-resources/) and each resource's [`resourceId` and `stat-list`](https://developer.broadcom.com/xapis/vcf-operations-api/latest/data-structures/stats-of-resource/) are optional in the public schema. Omitted arrays or statistics lists produce no-sample observations. Any returned resource identifier must match the explicitly queried resource. An empty series may omit numeric data; nonempty timestamp arrays still require matching numeric values. Reports recheck saved scope limits and native metadata types before calculating coverage or comparing periods.

The report calculates minimum, maximum, arithmetic mean and nearest-rank P95 across the returned samples. These statistics retain the returned rollup basis. A maximum of five-minute AVG samples is a maximum of averages; it does not establish an instantaneous CPU peak. Percentiles and means are not time-weighted and cannot reconstruct raw measurements from rolled-up values. No forecast or capacity guarantee is calculated.

## Coverage and period comparisons

When returned rollup and fixed interval match the request, `nominal_expected_samples` is the window duration divided by the interval and rounded up. `sample_coverage_percent_estimate` compares the returned count with that nominal count and caps the estimate at 100 percent. The estimate does not establish endpoint inclusion, bucket alignment, retention completeness or successful collection at every expected instant. `boundary_coverage_known` is always false.

Interior timestamps that differ by an approximately whole number of requested intervals produce an estimated missing-interior-sample count. Tolerance is the lesser of one second and one percent of the interval. Irregular cadence leaves that missing-sample count and the coverage percentage unknown. Interior gaps make the report partial. Samples near the window boundaries may remain unavailable even when no interior gap is visible.

Two equal-duration, nonoverlapping windows can be compared for the same resource and key when units are known and equal, returned semantics match the common request, and both windows contain samples. The later window shows absolute mean change and percentage change from the earlier window. A zero earlier mean has no defined percentage change. Comparisons describe available samples only; differing missing-sample patterns can affect their meaning. Overlap, unequal durations or missing metadata leave comparisons unknown.

## Validation scope

The automated tests use offline responses. Installed-build schema behavior, retention, permissions and live metric availability still require validation against the target appliance. Successful HTTP collection means the selected queries completed; it does not certify that every requested historical measurement exists or that the selected metric is suitable for a sizing decision.
