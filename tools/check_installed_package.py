"""Verify the installed inventory package without contacting appliances. Author: Paul Bryant."""

import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import sysconfig


EXPECTED_NAME = "vcf-api-collectors"
EXPECTED_AUTHOR = "Paul Bryant"
EXPECTED_COPYRIGHT = "Copyright (c) 2025-2026 Paul Bryant. All rights reserved."
EXPECTED_ENTRY_POINTS = {
    "vcf-collect": "vcf_inventory.cli:main",
    "vcf-compare": "vcf_inventory.compare:main",
    "vcf-relationships": "vcf_inventory.relationships:main",
    "vcf-report": "vcf_inventory.reporting:main",
    "vcf-validate-live": "vcf_inventory.live_validation:main",
}


class ValidationError(RuntimeError):
    """The installed distribution does not meet its packaging contract."""


def within(path, directory):
    """Compare resolved paths, including symlink targets."""
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
    except ValueError:
        return False
    return True


def check_environment(prefix, base_prefix, cwd, checkout):
    if Path(prefix).resolve() == Path(base_prefix).resolve():
        raise ValidationError("Run this check with the Python interpreter from a fresh virtual environment.")
    if within(cwd, checkout):
        raise ValidationError("Run this check from a directory outside the repository checkout.")


def normalized_name(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def check_metadata(distribution, expected_version):
    metadata = distribution.metadata
    if normalized_name(metadata.get("Name", "")) != EXPECTED_NAME:
        raise ValidationError("Installed distribution name does not match the expected package.")
    if metadata.get("Version") != expected_version or distribution.version != expected_version:
        raise ValidationError("Installed distribution version does not match --expected-version.")
    if metadata.get_all("Author", []) != [EXPECTED_AUTHOR] or metadata.get_all("Author-email", []):
        raise ValidationError("Installed distribution author must be Paul Bryant, with no additional author field.")
    if metadata.get("Requires-Python", "").replace(" ", "") != ">=3.10":
        raise ValidationError("Installed distribution must advertise Python >=3.10.")
    if distribution.requires:
        raise ValidationError("Installed distribution declares runtime dependencies; the toolkit promises none.")
    if metadata.get_all("License-File", []) != ["COPYRIGHT.md"]:
        raise ValidationError("Installed distribution must declare COPYRIGHT.md as its license file.")
    console = [entry for entry in distribution.entry_points if entry.group == "console_scripts"]
    names = [entry.name for entry in console]
    if len(names) != len(set(names)) or {entry.name: entry.value for entry in console} != EXPECTED_ENTRY_POINTS:
        raise ValidationError("Installed console commands differ from the expected five entry points.")
    return console


def check_notice(distribution, prefix):
    notices = [item for item in distribution.files or []
               if len(PurePosixPath(str(item)).parts) == 3
               and PurePosixPath(str(item)).parts[0].endswith(".dist-info")
               and PurePosixPath(str(item)).parts[1:] == ("licenses", "COPYRIGHT.md")]
    if len(notices) != 1:
        raise ValidationError("Installed distribution must own exactly one packaged COPYRIGHT.md notice.")
    notice = Path(distribution.locate_file(notices[0]))
    if not within(notice, prefix):
        raise ValidationError("The installed copyright notice is outside the virtual environment.")
    try:
        lines = notice.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValidationError("The installed copyright notice cannot be read as UTF-8.") from exc
    if "Author: Paul Bryant" not in lines or EXPECTED_COPYRIGHT not in lines:
        raise ValidationError("The installed notice must preserve Paul Bryant's copyright and reserved rights.")


def check_modules(distribution, entries, prefix):
    if not within(distribution.locate_file(""), prefix):
        raise ValidationError("Distribution metadata is outside the active virtual environment.")
    files = distribution.files
    if files is None:
        raise ValidationError("Installed distribution has no file manifest.")
    check_notice(distribution, prefix)
    owned = {Path(distribution.locate_file(item)).resolve() for item in files}
    for entry in entries:
        module_name, attribute = entry.value.split(":", 1)
        module = importlib.import_module(module_name)
        origin = getattr(module, "__file__", None)
        if not origin or not within(origin, prefix) or Path(origin).resolve() not in owned:
            raise ValidationError(f"{entry.name} imports code outside the installed distribution.")
        if not callable(getattr(module, attribute, None)):
            raise ValidationError(f"{entry.name} does not resolve to a callable entry point.")


def command_path(name, scripts_directory, windows=None):
    if windows is None:
        windows = os.name == "nt"
    path = Path(scripts_directory) / (name + ".exe" if windows else name)
    if not path.is_file():
        raise ValidationError(f"The installer did not create the {name} console wrapper.")
    return path


def run_command(path, arguments):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run([str(path), *arguments], capture_output=True, text=True,
                                timeout=30, check=False, env=environment)
    except subprocess.TimeoutExpired as exc:
        raise ValidationError(f"{path.stem} did not finish within 30 seconds.") from exc
    except OSError as exc:
        raise ValidationError(f"The {path.stem} console wrapper could not be started.") from exc
    if result.returncode != 0:
        raise ValidationError(f"{path.stem} {' '.join(arguments)} returned exit code {result.returncode}.")
    return result.stdout


def check_commands(entries, scripts_directory, prefix):
    if not within(scripts_directory, prefix):
        raise ValidationError("The console script directory is outside the active virtual environment.")
    wrappers = {entry.name: command_path(entry.name, scripts_directory) for entry in entries}
    for name, path in wrappers.items():
        if not within(path, prefix):
            raise ValidationError(f"The {name} console wrapper is outside the virtual environment.")
        help_text = run_command(path, ["--help"])
        if "usage:" not in help_text.lower():
            raise ValidationError(f"{name} --help did not return command usage.")
    try:
        resources = json.loads(run_command(wrappers["vcf-collect"], ["--list-resources"]))
    except (TypeError, ValueError) as exc:
        raise ValidationError("vcf-collect --list-resources did not return JSON.") from exc
    if not isinstance(resources, dict) or not {"sddc_manager", "vcenter", "nsx"}.issubset(resources):
        raise ValidationError("The installed resource registry is missing core components.")
    for component, endpoints in resources.items():
        if not isinstance(component, str) or not isinstance(endpoints, dict) or not endpoints:
            raise ValidationError("The installed resource registry has an invalid component.")
        if any(not isinstance(name, str) or not name or not isinstance(path, str) or not path.startswith("/")
               for name, path in endpoints.items()):
            raise ValidationError("The installed resource registry has an invalid resource path.")
    return sum(len(endpoints) for endpoints in resources.values())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a wheel installed into a fresh virtual environment, without appliance calls.")
    parser.add_argument("--expected-version", required=True, help="Version expected from the source release metadata")
    arguments = parser.parse_args(argv)
    try:
        check_environment(sys.prefix, sys.base_prefix, Path.cwd(), Path(__file__).resolve().parents[1])
        distribution = importlib.metadata.distribution(EXPECTED_NAME)
        entries = check_metadata(distribution, arguments.expected_version)
        check_modules(distribution, entries, sys.prefix)
        resource_count = check_commands(entries, sysconfig.get_path("scripts"), sys.prefix)
    except (ValidationError, importlib.metadata.PackageNotFoundError, ImportError, OSError) as exc:
        print(f"Installed package check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"author": EXPECTED_AUTHOR, "status": "success", "package": EXPECTED_NAME,
                      "version": arguments.expected_version, "commands_checked": len(entries),
                      "registered_resources": resource_count}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
