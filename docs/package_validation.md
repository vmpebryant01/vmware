# Installed package validation

Author: Paul Bryant

The inventory toolkit supports Python 3.10 and later. Its installed distribution is
`vcf-api-collectors`, with no runtime dependencies. Packaging checks build both the
wheel and source archive, then install the wheel into a fresh virtual environment.
Running the checks outside the repository prevents source files in the checkout
from satisfying an import that is missing from the wheel.

Use the Python interpreter from that environment to run
`tools/check_installed_package.py` by its absolute path. Supply the release version
from `vcf9/api_collectors/pyproject.toml` as `--expected-version`. The helper uses
only the Python standard library, including on Python 3.10.

For example, after building and installing the wheel, run this command from an
empty directory outside the checkout, substituting your own environment and
checkout paths:

```text
<environment-python> <checkout>/tools/check_installed_package.py --expected-version 2.3.0
```

The check confirms the installed name, version, author, Python requirement and
absence of declared runtime dependencies. It requires `License-File: COPYRIGHT.md`
and an owned notice inside the installed distribution's `licenses` directory that
preserves Paul Bryant's existing copyright and reserved rights. It also verifies that every registered
console command imports a callable from a file owned by the installed distribution
inside the active virtual environment. It runs the installer-generated wrappers
for all five commands with `--help`, then runs `vcf-collect --list-resources` and
checks the returned resource registry. These commands do not require configuration,
credentials or appliance access. The check neither installs packages nor writes
collection results.

CI checks the toolkit on Python 3.10 through 3.15 on Linux, with additional Windows
jobs for 3.10 and 3.15. Python 3.10 jobs check the advertised compatibility minimum;
they do not extend its [upstream support lifecycle](https://devguide.python.org/versions/).
Use an upstream-supported interpreter for new deployments. The repository's other
scripts have a separate minimum Python requirement; the toolkit's Python 3.10
compatibility does not extend that promise to every script in the repository.

`tools/build_and_check_package.py` runs the build and installation checks together.
Install the development build tools `build`, `setuptools>=77` and `wheel` into a
dedicated build environment first. Supply new work and artifact directories outside
the checkout:

```text
python tools/build_and_check_package.py --work-dir ../package-work --artifact-dir ../package-artifacts --expected-version 2.3.0
```

The helper copies tracked working-tree toolkit files into a temporary source tree.
Stage new source files before running it locally. Untracked configuration, credentials
and build output are excluded. It builds a source archive and wheel, inspects both
through the attribution gate, then installs the wheel into a separate fresh virtual
environment using only that local distribution directory. Installation uses the
package name and version, avoiding installer provenance that embeds a local source
path. The saved wheel and source archive remain in the supplied artifact directory.

The existing copyright and reuse notice is included in both distributions through
`project.license-files`; its terms are not changed. Installed metadata identifies
Paul Bryant and retains the original notice. This standard metadata field requires
setuptools 77 or newer, as documented in the
[setuptools configuration guide](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).

The workflow follows [GitHub's Python build and test guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
and the [Python packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/).

Successful package checks establish that a distribution can be installed and that
its offline commands work on the tested interpreter. They do not establish
compatibility with an appliance build or validate live API permissions. Those
require the separate live validation workflow.

The fields inspected here follow the public
[Python package core metadata specification](https://packaging.python.org/en/latest/specifications/core-metadata/).
Console command registration follows the
[entry point specification](https://packaging.python.org/en/latest/specifications/entry-points/).
Installed metadata and file ownership are read through
[`importlib.metadata`](https://docs.python.org/3/library/importlib.metadata.html).
