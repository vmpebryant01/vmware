# Contributing

Thanks for your interest in improving these examples. Issue reports are welcome. Contact the maintainer through an issue before submitting code so contribution and reuse permission can be agreed in writing. The `vsphere`, `nsx`, and `srm` directories are components of this repository.

- Include the component, exact product and API versions, operating system, module or Python package versions, and a sanitized reproduction when reporting a defect.
- Keep credentials and customer data out of commits, logs, tests, and issue comments. Use environment variables or a local, ignored `.env` file for secrets. Verify TLS certificates.
- For changes that write to infrastructure, provide a safe preview or explicit target scope, explain failure behavior, and add focused tests for validation and safety controls.
- Run the checks in `.github/workflows/lint.yml` locally where possible. State which checks ran and whether a live test was performed. Passing static checks alone does not establish live compatibility.
- Update the README, [version scope](docs/compatibility.md), and [script status](docs/script_status.md) when behavior or support claims change.

The repository is all rights reserved. Opening a pull request does not change the reuse terms. See [copyright and reuse](COPYRIGHT.md) and the [code of conduct](CODE_OF_CONDUCT.md).
