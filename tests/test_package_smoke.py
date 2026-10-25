"""Offline tests for installed-package validation. Author: Paul Bryant."""

from email.message import Message
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_installed_package.py"
SPEC = importlib.util.spec_from_file_location("check_installed_package", MODULE_PATH)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def fake_distribution(directory):
    metadata = Message()
    for name, value in (("Name", smoke.EXPECTED_NAME), ("Version", "2.3.0"),
                        ("Author", "Paul Bryant"), ("Requires-Python", ">=3.10"),
                        ("License-File", "COPYRIGHT.md")):
        metadata[name] = value
    entries = [SimpleNamespace(name=name, value=value, group="console_scripts")
               for name, value in smoke.EXPECTED_ENTRY_POINTS.items()]
    files = [value.split(":", 1)[0].replace(".", "/") + ".py"
             for value in smoke.EXPECTED_ENTRY_POINTS.values()]
    files.append("vcf_api_collectors-2.3.0.dist-info/licenses/COPYRIGHT.md")
    return SimpleNamespace(metadata=metadata, version="2.3.0", requires=[], entry_points=entries,
                           files=files, locate_file=lambda name: Path(directory) / name)


class PackageSmokeTests(unittest.TestCase):
    def test_metadata_accepts_declared_contract(self):
        distribution = fake_distribution("environment")
        self.assertEqual(len(smoke.check_metadata(distribution, "2.3.0")), 5)

    def test_metadata_rejects_version_author_python_and_dependency_changes(self):
        for field, value in (("Name", "another-package"), ("Version", "2.4.0"),
                             ("Author", "Other Author"), ("Requires-Python", ">=3.11")):
            with self.subTest(field=field):
                distribution = fake_distribution("environment")
                distribution.metadata.replace_header(field, value)
                with self.assertRaises(smoke.ValidationError):
                    smoke.check_metadata(distribution, "2.3.0")
        distribution = fake_distribution("environment")
        distribution.requires = ["example>=1"]
        with self.assertRaises(smoke.ValidationError):
            smoke.check_metadata(distribution, "2.3.0")

    def test_metadata_rejects_an_additional_author_field(self):
        for field, value in (("Author", "Other Author"), ("Author-email", "Paul Bryant <author@example.invalid>")):
            with self.subTest(field=field):
                distribution = fake_distribution("environment")
                distribution.metadata[field] = value
                with self.assertRaises(smoke.ValidationError):
                    smoke.check_metadata(distribution, "2.3.0")

    def test_license_file_metadata_must_name_the_packaged_notice(self):
        for value in (None, "LICENSE.txt", "COPYRIGHT.md\nLicense-File: extra.txt"):
            with self.subTest(value=value):
                distribution = fake_distribution("environment")
                del distribution.metadata["License-File"]
                if value is not None:
                    for item in value.split("\nLicense-File: "):
                        distribution.metadata["License-File"] = item
                with self.assertRaises(smoke.ValidationError):
                    smoke.check_metadata(distribution, "2.3.0")

    def test_notice_must_be_manifest_owned_and_preserve_the_existing_copyright(self):
        with tempfile.TemporaryDirectory() as directory:
            distribution = fake_distribution(directory)
            notice = Path(directory) / distribution.files[-1]
            notice.parent.mkdir(parents=True)
            notice.write_text("Author: Paul Bryant\nCopyright (c) 2025-2026 Paul Bryant. All rights reserved.\n", encoding="utf-8")
            smoke.check_notice(distribution, directory)
            notice.write_text("Author: Paul Bryant\nRights changed\n", encoding="utf-8")
            with self.assertRaises(smoke.ValidationError):
                smoke.check_notice(distribution, directory)
            distribution.files.pop()
            with self.assertRaises(smoke.ValidationError):
                smoke.check_notice(distribution, directory)

    def test_metadata_rejects_missing_duplicate_and_wrong_entry_points(self):
        for mode in ("missing", "duplicate", "wrong"):
            with self.subTest(mode=mode):
                distribution = fake_distribution("environment")
                if mode == "missing":
                    distribution.entry_points.pop()
                elif mode == "duplicate":
                    distribution.entry_points.append(distribution.entry_points[0])
                else:
                    distribution.entry_points[0].value = "another.module:main"
                with self.assertRaises(smoke.ValidationError):
                    smoke.check_metadata(distribution, "2.3.0")

    def test_environment_requires_venv_and_outside_working_directory(self):
        with self.assertRaises(smoke.ValidationError):
            smoke.check_environment("same", "same", "outside", "checkout")
        with self.assertRaises(smoke.ValidationError):
            smoke.check_environment("venv", "base", Path("checkout") / "child", "checkout")
        smoke.check_environment("venv", "base", "outside", "checkout")

    def test_installed_modules_are_manifest_owned_and_callable(self):
        with tempfile.TemporaryDirectory() as directory:
            distribution = fake_distribution(directory)
            notice = Path(directory) / distribution.files[-1]
            notice.parent.mkdir(parents=True)
            notice.write_text("Author: Paul Bryant\nCopyright (c) 2025-2026 Paul Bryant. All rights reserved.\n", encoding="utf-8")
            modules = {
                value.split(":", 1)[0]: SimpleNamespace(
                    __file__=str(Path(directory) / filename), main=lambda: 0)
                for value, filename in zip(smoke.EXPECTED_ENTRY_POINTS.values(), distribution.files)
            }
            with patch.object(smoke.importlib, "import_module", side_effect=modules.__getitem__):
                smoke.check_modules(distribution, distribution.entry_points, directory)
                module = modules["vcf_inventory.cli"]
                module.__file__ = str(Path(directory).parent / "source.py")
                with self.assertRaises(smoke.ValidationError):
                    smoke.check_modules(distribution, distribution.entry_points, directory)

    def test_module_file_manifest_is_required(self):
        distribution = fake_distribution("environment")
        distribution.files = None
        with self.assertRaises(smoke.ValidationError):
            smoke.check_modules(distribution, distribution.entry_points, "environment")

    def test_metadata_outside_venv_is_rejected(self):
        distribution = fake_distribution("outside")
        with self.assertRaises(smoke.ValidationError):
            smoke.check_modules(distribution, distribution.entry_points, "environment")

    def test_command_wrapper_resolution_is_portable(self):
        with tempfile.TemporaryDirectory() as directory:
            for filename in ("vcf-collect", "vcf-collect.exe"):
                (Path(directory) / filename).write_text("wrapper", encoding="utf-8")
            self.assertEqual(smoke.command_path("vcf-collect", directory, windows=False).name, "vcf-collect")
            self.assertEqual(smoke.command_path("vcf-collect", directory, windows=True).name, "vcf-collect.exe")
            with self.assertRaises(smoke.ValidationError):
                smoke.command_path("missing", directory, windows=False)

    def test_subprocess_environment_excludes_import_path_overrides(self):
        with patch.dict(smoke.os.environ, {"PYTHONPATH": "source", "PYTHONHOME": "other"}), \
                patch.object(smoke.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="usage: command")) as run:
            self.assertEqual(smoke.run_command(Path("vcf-collect"), ["--help"]), "usage: command")
        arguments = run.call_args.kwargs
        self.assertNotIn("PYTHONPATH", arguments["env"])
        self.assertNotIn("PYTHONHOME", arguments["env"])
        self.assertEqual(arguments["timeout"], 30)
        self.assertFalse(arguments["check"])

    def test_wrapper_failures_are_failures(self):
        for result in (SimpleNamespace(returncode=2, stdout=""), OSError("not executable"),
                       subprocess.TimeoutExpired("command", 30)):
            with self.subTest(result=type(result).__name__):
                options = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
                with patch.object(smoke.subprocess, "run", **options), self.assertRaises(smoke.ValidationError):
                    smoke.run_command(Path("vcf-collect"), ["--help"])

    def test_all_generated_commands_and_resource_registry_are_checked(self):
        distribution = fake_distribution("environment")
        registry = '{"sddc_manager":{"hosts":"/v1/hosts"},"vcenter":{"hosts":"/api/vcenter/host"},"nsx":{"segments":"/policy/api/v1/infra/segments"}}'
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(smoke, "command_path", side_effect=lambda name, _directory: Path(directory) / name), \
                    patch.object(smoke, "run_command", side_effect=["usage: command"] * 5 + [registry]) as run:
                count = smoke.check_commands(distribution.entry_points, directory, directory)
        self.assertEqual(count, 3)
        self.assertEqual(run.call_count, 6)
        self.assertEqual(run.call_args.args[1], ["--list-resources"])

    def test_bad_resource_output_and_help_are_rejected(self):
        distribution = fake_distribution("environment")
        for output in ("not json", "[]", '{"vcenter":{}}',
                       '{"sddc_manager":{"a":"bad"},"vcenter":{"a":"/a"},"nsx":{"a":"/a"}}'):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                with patch.object(smoke, "command_path", side_effect=lambda name, _directory: Path(directory) / name), \
                        patch.object(smoke, "run_command", side_effect=["usage: command"] * 5 + [output]), \
                        self.assertRaises(smoke.ValidationError):
                    smoke.check_commands(distribution.entry_points, directory, directory)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(smoke, "command_path", side_effect=lambda name, _directory: Path(directory) / name), \
                    patch.object(smoke, "run_command", return_value="missing usage"), self.assertRaises(smoke.ValidationError):
                smoke.check_commands(distribution.entry_points, directory, directory)

    def test_main_reports_a_failed_install_without_traceback(self):
        with patch.object(smoke, "check_environment", side_effect=smoke.ValidationError("fresh environment required")), \
                patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(smoke.main(["--expected-version", "2.3.0"]), 1)
        self.assertIn("fresh environment required", output.getvalue())


if __name__ == "__main__":
    unittest.main()
