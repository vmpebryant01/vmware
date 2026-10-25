# Lifecycle compliance

Author: Paul Bryant

Collect the desired image and existing vLCM compliance result for explicitly selected image-managed clusters. The collector reads both resources through the vCenter session. The documented operations require `VcIntegrity.lifecycleSoftwareSpecification.Read` on the selected cluster. See [desired software specification](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/esx/settings/clusters/cluster/software/get/) and [cluster compliance](https://developer.broadcom.com/xapis/vsphere-automation-api/latest/api/esx/settings/clusters/cluster/software/compliance/get/).

Add these optional resources to a vCenter target:

```json
{
  "author": "Paul Bryant",
  "targets": [
    {
      "name": "vcenter",
      "component": "vcenter",
      "url": "https://vcenter.example.com",
      "username_env": "VCENTER_USERNAME",
      "password_env": "VCENTER_PASSWORD",
      "verify_tls": true,
      "lifecycle_cluster_ids": ["domain-c101", "domain-c102"],
      "resources": ["lifecycle_desired_image", "lifecycle_compliance"]
    }
  ]
}
```

The IDs must be 1-1000 unique `domain-c` identifiers from your vCenter inventory. The resources accept no filters and are excluded from default collection. Each cluster receives one GET per selected resource. A failed request or invalid response leaves that resource incomplete, without exporting the successful subset as complete coverage.

```powershell
python collect.py --config lifecycle.json --output inventory
python report_lifecycle_compliance.py --run inventory\RUN --output reports\lifecycle.json --max-scan-age-hours 24 --csv
```

The report includes cluster and host rows, native status, the existing scan completion time and commit, current and scan-target base-image versions, desired versions, component compliance, and notification counts. It preserves software identifiers and versions while omitting native message text, remediation instructions, and hardware details.

`review` identifies a known noncompliant or incompatible cached result, or an old scan. `unknown` identifies unavailable, missing, inconsistent, ambiguous, or invalid evidence. The report's overall `partial` status concerns evidence coverage; known noncompliance alone does not make coverage partial. Exit code 0 means the report has complete recognized evidence, 2 means partial evidence, and 1 means invalid input or file access failure.

Scan age is measured against the saved compliance resource's collection time. `source_age_hours` shows the age of that saved observation when the report runs. Reopening an old snapshot does not turn the old scan into a newly observed failure. Invalid, future, numeric, and timezone-free scan times remain unknown.

Desired image collection and compliance collection are separate observations. The scan commit is retained, but the desired-image response does not provide the same commit. Equality of base-image versions is only a version comparison. It does not establish that the complete current desired image, component set, or alternative image matched the scan. Host coverage describes the cached scan rather than the current cluster membership.

No new scan, precheck, stage, or remediation operation runs. The report does not establish hardware compatibility or upgrade readiness. A missing endpoint, insufficient privilege, unsupported cluster management mode, or absent cached result remains unavailable. The public schemas support these read operations, but installed-build and live appliance validation remain necessary before claiming support for a particular VCF 9.x deployment.
