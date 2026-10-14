# VMware Automation Scripts

This repository contains vSphere, NSX, and Site Recovery Manager (SRM) scripts. It is a collection of examples with different levels of implementation and verification. Review each script and test it against a nonproduction system before using it in operations.

## Setup

1. Install Python 3.11 or later and run `python -m pip install -r requirements.txt` for Python scripts.
2. Install the relevant VMware PowerCLI modules for PowerShell scripts.
3. Copy the relevant `vsphere/.env.example`, `nsx/.env.example`, or `srm/.env.example` to `.env` in that directory. Supply credentials through your normal secret management process. Never commit `.env` files.
4. Trust the issuing CA for vCenter, NSX, or SRM. For Python scripts that support a custom CA, set the corresponding `VCENTER_CA_BUNDLE` or `NSXT_CA_BUNDLE` environment variable.

The vSphere snapshot removal and NSX firewall CSV importer preview their planned changes by default and require `--apply` to write. Other scripts may change infrastructure immediately. Read their code and documentation before running them.

## Current limits

- The SRM Python workflows stop before generating output because their API integration is incomplete.
- Many SRM and NSX PowerShell examples refer to commands outside the published PowerCLI modules. They now check for those commands before requesting credentials and stop if the commands are unavailable. The SRM module exposes its API through `Connect-SrmServer` and the connection's `ExtensionData` property. See [Broadcom's command reference](https://developer.broadcom.com/powercli/latest/vmware.vimautomation.srm/commands/connect-srmserver).
- Several vSphere inventory reports now read actual vCenter objects through pyVmomi. Reports that need unavailable backup, CMDB, NSX, SRM, or historical data stop before creating an operational report. Remaining placeholder fields must not be treated as measured results.
- The repository has static syntax checks and a small unit test suite. Live API behavior needs validation on the product versions in use.

See `docs/onboarding.md` for the original onboarding notes.
