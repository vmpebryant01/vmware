# Onboarding

Clone this repository and review the root README for dependencies and current limits. Install the packages in `requirements.txt` for Python workflows, or the relevant VMware PowerCLI modules for PowerShell workflows. Copy the appropriate component's `.env.example` to `.env`, then provide credentials and a trusted certificate chain for your environment.

Check [historical version scope](compatibility.md) before selecting modules or endpoints. The PowerShell examples use the VMware.PowerCLI 13.x family; their VCF.PowerCLI 9.x behavior has not been validated.

To install the July 2025 reference module version from PowerShell Gallery, run `Install-Module VMware.PowerCLI -RequiredVersion 13.3.0.24145083`. The Python requirements keep pyVmomi in the vSphere 8.0 Update 3 SDK line.

Run read-only reports on a nonproduction system first. For scripts that support preview, inspect the output before using `--apply`. For scripts without preview, inspect the API calls and scope in the source before running them.
