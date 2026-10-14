# Usage

- All PowerCLI scripts are in `/scripts`, Python scripts in `/python`.
- Run scripts from within their folder; see README in each submodule for details.
- Scripts produce the files described in their own source. Incomplete integrations stop with an error before creating an operational report.

Credential handling is via prompt (PowerCLI) or `.env` (Python). Never check credentials into source control.
