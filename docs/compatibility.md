# Historical version scope

Author: Paul Bryant

The original repository commits were posted on July 23, 2025. VMware Cloud Foundation (VCF) 9.0 became generally available on June 17, 2025, and VCF PowerCLI 9.0 was announced on June 24, 2025. The posting date therefore does not establish that the scripts predate VCF 9. The code uses the earlier, component-specific vSphere, NSX, and SRM interfaces, so this repository preserves that product generation.

| Component | Reference available by July 23, 2025 | Scope of these examples |
| --- | --- | --- |
| vSphere | vCenter Server 8.0 Update 3e | vSphere 8.x APIs and cmdlets, with vCenter 8.0 Update 3 as the reference generation. Python examples use the pyVmomi 8.0 Update 3 SDK line or the vCenter REST interface present in this generation. |
| NSX | NSX 4.2.2.1 | NSX 4.2.x Policy and Manager APIs. Names containing `NSX-T` reflect the older naming used in the original scripts. |
| PowerShell modules | VMware.PowerCLI 13.3 | VMware.PowerCLI 13.x module family. This is distinct from VCF.PowerCLI 9.x. |
| Site recovery | VMware Live Site Recovery 9.0.2.2 was available before VCF 9; 9.0.3 was available by the posting date | SRM 8.x and pre-VCF-9 Live Site Recovery 9.0.2.x concepts. The number 9.0 in Live Site Recovery is a separate product version, not a claim of VCF 9 support. SRM integrations in this repository remain incomplete. |

These are historical reference versions, not a record of the products used when each script was written. The repository does not contain a deployment manifest or live test results that establish an exact supported patch level. Validate each script against the installed product and module builds in a nonproduction environment. VCF 9.x, vSphere 9.x, NSX 9.x, and VCF.PowerCLI 9.x have not been validated here.

## API inventory collectors

The separate [API inventory collection](../vcf9/api_collectors/README.md) uses documented product APIs for VCF management, HCX, NSX, VCF Operations, VCF Automation, and Protection and Recovery. Its guide and product notes link the public API references and describe authentication, inventory scope, and pagination limits. It requires Python 3.11 or later in this repository and uses only the standard library.

Offline tests exercise request handling, authentication, pagination, failure reporting, and exports. They do not establish live compatibility with a particular VCF 9.x release or a combination of component builds. Confirm endpoint availability, permissions, and returned fields against the installed products before operational use. The historical examples retain the version scope above.

## Check your environment

For PowerShell, inspect the installed module and the connected vCenter version before running a script:

```powershell
Get-Module VMware.PowerCLI -ListAvailable | Select-Object Name, Version
Connect-VIServer -Server <vcenter-hostname>
$global:DefaultVIServer | Select-Object Name, Version, Build
```

For Python, `nsx/python/get_nsxt_api_version.py` queries the NSX Manager build. Review the script before use and supply a trusted certificate chain. SRM scripts need an implemented adapter for the installed Live Site Recovery API before they can produce operational results.

## Product sources

- [VCF 9.0 general availability, June 17, 2025](https://blogs.vmware.com/cloud-foundation/2025/06/17/whats-new-in-vmware-cloud-foundation-9-0/)
- [VCF PowerCLI 9.0 announcement, June 24, 2025](https://blogs.vmware.com/cloud-foundation/2025/06/24/introducing-vcf-powercli-9-0/)
- [vCenter Server build and release dates](https://knowledge.broadcom.com/external/article?legacyId=2143838)
- [NSX build and release dates](https://knowledge.broadcom.com/external/article/317797/build-numbers-and-versions-of-vmware-nsx.html)
- [Live Site Recovery and SRM build and release dates](https://knowledge.broadcom.com/external/article/313905/build-numbers-and-versions-of-vmware-liv.html)
- [VMware.PowerCLI 13.3 package](https://www.powershellgallery.com/packages/VMware.PowerCLI/13.3.0.24145083)
- [vSphere 8.0.3 API reference](https://developer.broadcom.com/xapis/vsphere-automation-api/8.0.3/)
- [pyVmomi 8.0 Update 3 SDK package](https://pypi.org/project/pyvmomi/8.0.3.0.1/)
- [NSX 4.2.2 API reference](https://developer.broadcom.com/xapis/nsx-t-data-center-rest-api/4.2.2/)
