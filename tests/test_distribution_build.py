"""Tracked package snapshots and build isolation. Author: Paul Bryant."""

import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from tools.build_and_check_package import build_and_check, build_environment, copy_tracked_source


class DistributionBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repository"
        self.source = self.repo / "vcf9/api_collectors"
        self.source.mkdir(parents=True)
        (self.source / "pyproject.toml").write_text("# Author: Paul Bryant\n", encoding="utf-8")

    def test_copy_includes_tracked_changes_and_excludes_local_configuration(self):
        (self.source / "module.py").write_text("# Author: Paul Bryant\nvalue = 2\n", encoding="utf-8")
        (self.source / "config.json").write_text('{"local": true}', encoding="utf-8")
        destination = self.root / "snapshot"
        with patch("tools.build_and_check_package.subprocess.check_output", return_value=
                   b"vcf9/api_collectors/pyproject.toml\0vcf9/api_collectors/module.py\0"):
            count = copy_tracked_source(self.repo, destination, "git")
        self.assertEqual(count, 2)
        self.assertIn("value = 2", (destination / "module.py").read_text(encoding="utf-8"))
        self.assertFalse((destination / "config.json").exists())

    def test_copy_rejects_escaping_tracked_paths(self):
        listing = b"vcf9/api_collectors/pyproject.toml\0vcf9/api_collectors/../../outside.txt\0"
        with patch("tools.build_and_check_package.subprocess.check_output", return_value=listing):
            with self.assertRaises(ValueError):
                copy_tracked_source(self.repo, self.root / "snapshot", "git")

    def test_copy_rejects_paths_with_cross_platform_drive_or_separator_semantics(self):
        for path in (b"vcf9/api_collectors/C:/outside.py", b"vcf9/api_collectors/parent\\outside.py"):
            listing = b"vcf9/api_collectors/pyproject.toml\0" + path + b"\0"
            with self.subTest(path=path), patch("tools.build_and_check_package.subprocess.check_output", return_value=listing):
                with self.assertRaises(ValueError):
                    copy_tracked_source(self.repo, self.root / "snapshot", "git")

    def test_build_environment_removes_installer_redirection_and_configuration(self):
        environment = build_environment({"PIP_TARGET": "outside", "PIP_PREFIX": "outside", "PIP_FIND_LINKS": "other",
                                         "PIP_CONFIG_FILE": "private", "PYTHONPATH": "source", "PYTHONHOME": "other", "PATH": "tools"})
        self.assertEqual(environment["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(environment["PATH"], "tools")
        self.assertFalse({"PIP_TARGET", "PIP_PREFIX", "PIP_FIND_LINKS", "PYTHONPATH", "PYTHONHOME"} & environment.keys())

    def test_copy_rejects_missing_tracked_source(self):
        listing = b"vcf9/api_collectors/pyproject.toml\0vcf9/api_collectors/missing.py\0"
        with patch("tools.build_and_check_package.subprocess.check_output", return_value=listing):
            with self.assertRaises(ValueError):
                copy_tracked_source(self.repo, self.root / "snapshot", "git")

    def test_build_refuses_checkout_work_or_existing_artifacts_before_building(self):
        work = self.root / "work"
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        with patch("tools.build_and_check_package.subprocess.run") as run:
            with self.assertRaises(ValueError):
                build_and_check(self.repo, self.repo / "work", artifacts, "2.3.0", "git")
            with self.assertRaises(ValueError):
                build_and_check(self.repo, work, artifacts, "2.3.0", "git")
        run.assert_not_called()

    def test_build_refuses_unexpected_version_syntax_before_running_tools(self):
        with patch("tools.build_and_check_package.subprocess.run") as run:
            with self.assertRaises(ValueError):
                build_and_check(self.repo, self.root / "work", self.root / "artifacts", "2.3.0 --extra", "git")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
