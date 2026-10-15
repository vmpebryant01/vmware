# Usage

- PowerShell and Python scripts live under the `vsphere`, `nsx`, and `srm` component directories. See the [script status guide](script_status.md) for the complete inventory.
- Run scripts from the repository root when following the [workflow notes](workflows.md). Other examples may assume a working directory within their component; inspect the source before running them.
- Scripts produce the files described in their own source. Incomplete integrations stop with an error before creating an operational report.

Credential handling is via prompt (PowerCLI) or `.env` (Python). Never check credentials into source control.
