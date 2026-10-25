# Attribution checks

Author: Paul Bryant

Run the repository check before committing or sharing a distribution:

```console
python tools/check_attribution.py --repo . --all-history
python tools/check_attribution.py --repo . --all-history --artifact path/to/package.whl --artifact path/to/package.tar.gz
```

The default checks every tracked working-tree filename and file, plus the author,
committer, other headers and message of the current commit. `--all-history` also
checks all locally reachable commits, every historical tracked filename and every
unique historical file version. Fetch the required branches and full history
before using that option. It cannot inspect remote history that is absent locally.

Use `--commit-range BASE..HEAD` to limit commit metadata inspection to a particular
range. This option still checks all current tracked files. It does not check older
file contents; use `--all-history` for that purpose. An empty or unavailable commit
selection fails as unverified. Git defines the index listing and revision traversal
used here. [Tracked file listing](https://git-scm.com/docs/git-ls-files),
[revision traversal](https://git-scm.com/docs/git-rev-list)

The prohibited provider, assistant and model names are stored as numeric character
sequences, together with generic generated-content attribution phrases. Matching
is case insensitive and normalizes Unicode compatibility
characters. Diagnostics identify the relative file or archive member and the kind
of problem, without printing file contents, commit messages or matched phrases.
An affected filename is sanitized before printing. Unsafe archive paths are
identified by member number without repeating the supplied path. This is an attribution check,
not a credential scanner or a general detector of how text was written.

`--artifact` can be repeated. ZIP, wheel, tar and gzip-compressed tar archives are
inspected in memory without extracting files. Inspection includes nested members,
ZIP comments and supported extra metadata, gzip filenames and comments, tar owner
and group names, extended headers and link targets. Absolute paths, parent-path
escapes, duplicate names, encrypted ZIP members, unsupported member types,
unrecognized metadata fields and trailing payloads fail as unverified. Linked
targets are inspected as text; the check does not follow them. Archive behavior
uses the standard library's [ZIP reader](https://docs.python.org/3/library/zipfile.html)
and [tar reader](https://docs.python.org/3/library/tarfile.html).

Wheel and compressed source distribution artifacts must contain metadata for
`vcf-api-collectors`. Every matching `METADATA` or `PKG-INFO` record must contain
exactly one `Author: Paul Bryant` field. A second author display name in
`Author-email` also fails. All package metadata header names and decoded values,
including encoded extension headers, are checked for prohibited attribution.
Other packages' author fields are preserved and still
scanned for prohibited attribution. This follows the package format's
[core metadata fields](https://packaging.python.org/en/latest/specifications/core-metadata/).

Supported source encodings are UTF-8, UTF-16 or UTF-32 with a byte-order mark, and
legacy Windows-1252 text without binary control characters. Unsupported binary
formats fail as unverified, including opaque image or document metadata. Add an
appropriate format reader before including such files; the check has no silent
binary skip or content exclusion list. Existing collaborators' names and legitimate
third-party credits are not replaced. Resolve an actual conflict deliberately;
the tool never edits source, archives or history.

Current tracked toolkit files also require an explicit Paul Bryant author
declaration. JSON examples require the top-level `author` field, source and
documentation files require an author header or Python `__author__` declaration,
and `pyproject.toml` must declare exactly one project author named Paul Bryant.
CSV and TSV data do not require invented author rows. This ownership requirement
applies to the current toolkit tree, not earlier commits or other projects'
collaborator history. Python 3.10 accepts the canonical single-line project
authors declaration; newer Python versions parse that field with the standard
TOML reader.

Inspection limits are 16 MiB per file or artifact, 128 MiB of expanded archive
contents, 10,000 archive members and four archive levels. Limits also bound
historical blob inspection. Directory, link and rejected members count toward
the member limit. Exceeding a limit fails as unverified rather than
producing a passing result. These limits prevent an oversized or deeply nested
archive from being treated as fully inspected.

Exit codes are `0` for a completed clean check, `1` for attribution or package
author findings, and `2` when any requested part could not be fully inspected.
Continuous integration must treat both nonzero exit codes as failures. Newly
created files must be staged before a local run because untracked files are not
part of the tracked repository scope. The workflow builds and checks package
artifacts explicitly; ignored local build outputs are not implicitly included.
