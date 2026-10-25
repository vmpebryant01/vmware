"""Build tracked sources and verify isolated distributions. Author: Paul Bryant."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


SOURCE_PREFIX = "vcf9/api_collectors/"


def copy_tracked_source(repo, destination, git):
    """Copy only tracked source files, excluding local credentials and build output."""
    listing = subprocess.check_output([git, "ls-files", "-z", "--", SOURCE_PREFIX], cwd=repo)
    paths = [value for value in listing.decode("utf-8").split("\0") if value]
    if SOURCE_PREFIX + "pyproject.toml" not in paths:
        raise ValueError("The tracked toolkit build configuration is missing.")
    for name in paths:
        relative = PurePosixPath(name)
        if (not name.startswith(SOURCE_PREFIX) or relative.is_absolute() or ".." in relative.parts
                or "\\" in name or any(":" in part for part in relative.parts)):
            raise ValueError("A tracked source path is outside the toolkit.")
        source = repo.joinpath(*relative.parts)
        toolkit = repo / SOURCE_PREFIX
        if (source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(repo.resolve())
                or not source.resolve().is_relative_to(toolkit.resolve())):
            raise ValueError("A tracked source file is missing or has an unsupported link target.")
        target = destination.joinpath(*PurePosixPath(name[len(SOURCE_PREFIX):]).parts)
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError("A package snapshot destination escapes its directory.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return len(paths)


def build_environment(original):
    """Disable ambient package redirection and user configuration for local checks."""
    environment = {key: value for key, value in original.items()
                   if not key.upper().startswith("PIP_") and key.upper() not in ("PYTHONPATH", "PYTHONHOME")}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return environment


def build_and_check(repo, work, artifact_dir, expected_version, git):
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}", expected_version):
        raise ValueError("The expected version must contain three numeric release components.")
    if work.resolve().is_relative_to(repo.resolve()) or artifact_dir.resolve().is_relative_to(repo.resolve()):
        raise ValueError("Build work and distributions must remain outside the checkout.")
    if artifact_dir.exists():
        raise ValueError("Use a new distribution directory so previous artifacts cannot satisfy this check.")
    work.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    environment = build_environment(os.environ)
    with tempfile.TemporaryDirectory(prefix="package-validation-", dir=work) as temporary:
        root = Path(temporary)
        source = root / "source"
        source.mkdir()
        copied = copy_tracked_source(repo, source, git)
        subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--outdir", str(artifact_dir), str(source)],
                       check=True, env=environment, cwd=root)
        wheels = list(artifact_dir.glob("*.whl"))
        archives = list(artifact_dir.glob("*.tar.gz"))
        if len(wheels) != 1 or len(archives) != 1 or len(list(artifact_dir.iterdir())) != 2:
            raise ValueError("The build must produce exactly one wheel and one source archive.")
        subprocess.run([sys.executable, str(repo / "tools/check_attribution.py"), "--repo", str(repo), "--git", git,
                        "--artifact", str(wheels[0]), "--artifact", str(archives[0])], check=True, env=environment, cwd=root)
        installed = root / "environment"
        subprocess.run([sys.executable, "-m", "venv", str(installed)], check=True, env=environment, cwd=root)
        interpreter = installed / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([str(interpreter), "-m", "pip", "install", "--no-input", "--no-index", "--no-deps", "--no-compile",
                        "--find-links", str(artifact_dir), "vcf-api-collectors==" + expected_version],
                       check=True, env=environment, cwd=root)
        command_directory = root / "commands"
        command_directory.mkdir()
        subprocess.run([str(interpreter), str(repo / "tools/check_installed_package.py"),
                        "--expected-version", expected_version], check=True, env=environment, cwd=command_directory)
    return {"author": "Paul Bryant", "status": "success", "tracked_sources_built": copied,
            "distribution_files": 2, "version": expected_version, "python": ".".join(map(str, sys.version_info[:3]))}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a tracked toolkit snapshot and test its isolated installation.")
    parser.add_argument("--work-dir", type=Path, required=True, help="Temporary build parent outside the checkout")
    parser.add_argument("--artifact-dir", type=Path, required=True, help="New directory for inspected wheel and source archive")
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--git", default="git", help="Git executable")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    try:
        result = build_and_check(repo, args.work_dir.resolve(), args.artifact_dir.resolve(), args.expected_version, args.git)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Package validation failed; inspect the preceding build or check results.", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
