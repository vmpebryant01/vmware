# Onboarding

Clone this repository and review the root README for dependencies and current limits. Install the packages in `requirements.txt` for Python workflows, or the relevant VMware PowerCLI modules for PowerShell workflows. Copy the appropriate component's `.env.example` to `.env`, then provide credentials and a trusted certificate chain for your environment.

Run read-only reports on a nonproduction system first. For scripts that support preview, inspect the output before using `--apply`. For scripts without preview, inspect the API calls and scope in the source before running them.
