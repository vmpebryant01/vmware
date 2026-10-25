"""Tests for source, history and distribution attribution checks.

Author: Paul Bryant
"""

import contextlib
import base64
import gzip
import importlib.util
import io
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import tarfile


SCRIPT = Path(__file__).parents[1] / "tools" / "check_attribution.py"
SPEC = importlib.util.spec_from_file_location("attribution_check", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BAD = "".join(map(chr, (79, 112, 101, 110, 65, 73)))
BAD_MODEL = "".join(map(chr, (71, 80, 84, 45, 54)))
METADATA = b"Metadata-Version: 2.4\nName: vcf-api-collectors\nVersion: 1.0\nAuthor: Paul Bryant\n\n"


def zipped(members=None, comment=b"", extra=b"", member_comment=b""):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.comment = comment
        for name, value in (members or {"sample.txt": b"Author: Paul Bryant\n"}).items():
            info = zipfile.ZipInfo(name)
            info.extra = extra
            info.comment = member_comment
            archive.writestr(info, value)
    return stream.getvalue()


def tarred(members=None, owner="Paul Bryant", link=None, pax=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, value in (members or {"sample.txt": b"Author: Paul Bryant\n"}).items():
            info = tarfile.TarInfo(name)
            info.size = len(value)
            info.uname = owner
            info.pax_headers = pax or {}
            archive.addfile(info, io.BytesIO(value))
        if link:
            info = tarfile.TarInfo("shortcut")
            info.type = tarfile.SYMTYPE
            info.linkname = link
            archive.addfile(info)
    return stream.getvalue()


class AttributionTextTests(unittest.TestCase):
    def test_case_insensitive_text_and_model_names(self):
        for value in (BAD.swapcase(), BAD_MODEL, BAD_MODEL.replace("-", "_"),
                      "\uff2f\uff50\uff45\uff4e\uff21\uff29"):
            scanner = MODULE.Scanner()
            scanner.inspect(value.encode(), "script.py")
            self.assertEqual(scanner.result.exit_code, 1)

    def test_generic_attribution_phrases_are_rejected(self):
        fixtures = (
            (97, 105, 45, 103, 101, 110, 101, 114, 97, 116, 101, 100),
            (97, 105, 32, 103, 101, 110, 101, 114, 97, 116, 101, 100),
            (103, 101, 110, 101, 114, 97, 116, 101, 100, 32, 98, 121, 32, 97, 105),
            (103, 101, 110, 101, 114, 97, 116, 101, 100, 32, 117, 115, 105, 110, 103, 32, 97, 105),
            (97, 114, 116, 105, 102, 105, 99, 105, 97, 108, 32, 105, 110, 116, 101, 108, 108, 105, 103, 101, 110, 99, 101),
        )
        for fixture in fixtures:
            value = "".join(map(chr, fixture)).swapcase()
            scanner = MODULE.Scanner()
            scanner.inspect(value.encode(), "script.py")
            self.assertEqual(scanner.result.exit_code, 1)
            scanner = MODULE.Scanner()
            encoded = b"=?UTF-8?B?" + base64.b64encode(value.encode()) + b"?="
            scanner.inspect(METADATA.replace(b"\n\n", b"\nX-Generator: " + encoded + b"\n\n"), "METADATA")
            self.assertEqual(scanner.result.exit_code, 1)

    def test_utf_boms_and_legacy_text(self):
        for encoding in ("utf-8-sig", "utf-16", "utf-32"):
            scanner = MODULE.Scanner()
            scanner.inspect(BAD.encode(encoding), "notes.txt")
            self.assertEqual(scanner.result.exit_code, 1)
        scanner = MODULE.Scanner()
        scanner.inspect("Author: Paul Bryant\nPrice \u00a310\n".encode("cp1252"), "legacy.txt")
        self.assertEqual(scanner.result.exit_code, 0)

    def test_unknown_binary_and_limits_are_unverified(self):
        scanner = MODULE.Scanner()
        scanner.inspect(b"\x00\x01binary", "asset.bin")
        with patch.object(MODULE, "MAX_FILE", 3):
            scanner.inspect(b"four", "notes.txt")
        self.assertEqual(scanner.result.exit_code, 2)
        self.assertEqual(len(scanner.result.unverified), 2)

    def test_filename_and_diagnostic_are_sanitized(self):
        scanner = MODULE.Scanner()
        scanner.inspect(b"clean", BAD + "\n.txt")
        message = "\n".join(scanner.result.findings)
        self.assertNotIn(BAD.casefold(), message.casefold())
        self.assertNotIn("\n.txt", message)
        self.assertIn("[restricted]", message)

    def test_package_author_is_required_and_exact(self):
        for value in (METADATA.replace(b"Author: Paul Bryant\n", b""),
                      METADATA.replace(b"Paul Bryant", b"Other Person"),
                      METADATA.replace(b"\n\n", b"\nAuthor: Other Person\n\n")):
            scanner = MODULE.Scanner()
            scanner.inspect(value, "sample.dist-info/METADATA")
            self.assertEqual(scanner.result.exit_code, 1)
        scanner = MODULE.Scanner()
        scanner.inspect(METADATA, "sample.dist-info/METADATA")
        self.assertEqual(scanner.result.exit_code, 0)

    def test_other_package_authors_are_preserved(self):
        scanner = MODULE.Scanner()
        scanner.inspect(METADATA.replace(b"vcf-api-collectors", b"another-package")
                        .replace(b"Paul Bryant", b"Other Person"), "PKG-INFO")
        self.assertEqual(scanner.result.exit_code, 0)

    def test_second_authorship_field_cannot_change_display_name(self):
        scanner = MODULE.Scanner()
        scanner.inspect(METADATA.replace(b"\n\n", b"\nAuthor-email: Other Person <person@example.com>\n\n"), "METADATA")
        self.assertEqual(scanner.result.exit_code, 1)

    def test_every_encoded_metadata_header_is_checked(self):
        encodings = (b"=?UTF-8?B?" + base64.b64encode(BAD.encode()) + b"?=",
                     ("=?UTF-8?Q?" + "".join("=" + format(byte, "02X") for byte in BAD.encode()) + "?=").encode())
        for encoded in encodings:
            for name in (b"X-Generator", b"Summary", b"Maintainer", b"Project-URL"):
                for metadata_name in ("METADATA", "PKG-INFO"):
                    scanner = MODULE.Scanner()
                    value = METADATA.replace(b"\n\n", b"\n" + name + b": " + encoded + b"\n\n")
                    self.assertNotIn(BAD.encode(), value)
                    scanner.inspect(value, metadata_name)
                    self.assertEqual(scanner.result.exit_code, 1)
        scanner = MODULE.Scanner()
        value = METADATA.replace(b"vcf-api-collectors", b"another-package")
        value = value.replace(b"\n\n", b"\nX-Generator: " + encoded + b"\n\n")
        scanner.inspect(value, "METADATA")
        self.assertEqual(scanner.result.exit_code, 1)


class AttributionArchiveTests(unittest.TestCase):
    def test_wheel_metadata_and_contents_pass(self):
        scanner = MODULE.Scanner()
        scanner.inspect(zipped({"vcf_api_collectors.dist-info/METADATA": METADATA,
                                "vcf_inventory/__init__.py": b"# Author: Paul Bryant\n"}), "tool.whl")
        self.assertEqual(scanner.result.exit_code, 0)
        self.assertEqual(scanner.result.members, 2)

    def test_wheel_missing_metadata_or_wrong_author_fails(self):
        for members in ({"script.py": b"clean"},
                        {"sample.dist-info/METADATA": METADATA.replace(b"Paul Bryant", b"Other Person")}):
            scanner = MODULE.Scanner()
            scanner.inspect(zipped(members), "tool.whl")
            self.assertEqual(scanner.result.exit_code, 1)

    def test_archive_and_member_comments_are_checked(self):
        for archive in (zipped(comment=BAD.encode()), zipped(member_comment=BAD.encode())):
            scanner = MODULE.Scanner()
            scanner.inspect(archive, "download.zip")
            self.assertEqual(scanner.result.exit_code, 1)

    def test_zip_unicode_metadata_and_unknown_metadata(self):
        value = b"\x01" + b"\x00" * 4 + BAD.encode()
        scanner = MODULE.Scanner()
        scanner.inspect(zipped(extra=struct.pack("<HH", 0x7075, len(value)) + value), "download.zip")
        self.assertEqual(scanner.result.exit_code, 1)
        scanner = MODULE.Scanner()
        scanner.inspect(zipped(extra=struct.pack("<HH", 0xBEEF, 3) + b"abc"), "download.zip")
        self.assertEqual(scanner.result.exit_code, 2)

    def test_nested_archives_are_checked_and_depth_is_bounded(self):
        scanner = MODULE.Scanner()
        scanner.inspect(zipped({"inside.zip": zipped({"notes.txt": BAD.encode()})}), "outer.zip")
        self.assertEqual(scanner.result.exit_code, 1)
        scanner = MODULE.Scanner()
        with patch.object(MODULE, "MAX_DEPTH", 1):
            scanner.inspect(zipped({"inside.zip": zipped()}), "outer.zip")
        self.assertEqual(scanner.result.exit_code, 2)

    def test_archive_size_and_member_count_are_bounded(self):
        for option, limit in (("MAX_TOTAL", 4), ("MAX_MEMBERS", 1), ("MAX_FILE", 2)):
            scanner = MODULE.Scanner()
            with patch.object(MODULE, option, limit):
                scanner.inspect(zipped({"first.txt": b"hello", "second.txt": b"world"}), "download.zip")
            self.assertEqual(scanner.result.exit_code, 2)

    def test_directory_members_count_toward_zip_and_tar_limits(self):
        archive = zipped({"first/": b"", "second/": b""})
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as bundle:
            for name in ("first", "second"):
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                bundle.addfile(info)
        for data, name in ((archive, "download.zip"), (stream.getvalue(), "download.tar")):
            scanner = MODULE.Scanner()
            with patch.object(MODULE, "MAX_MEMBERS", 1):
                scanner.inspect(data, name)
            self.assertEqual(scanner.result.exit_code, 2)
            self.assertEqual(scanner.result.members, 2)

    def test_link_and_unsafe_members_also_count_toward_limits(self):
        scanner = MODULE.Scanner()
        with patch.object(MODULE, "MAX_MEMBERS", 1):
            scanner.inspect(tarred(link="sample.txt"), "download.tar")
        self.assertEqual(scanner.result.exit_code, 2)
        self.assertEqual(scanner.result.members, 2)
        scanner = MODULE.Scanner()
        with patch.object(MODULE, "MAX_MEMBERS", 1):
            scanner.inspect(zipped({"../first.txt": b"", "../second.txt": b""}), "download.zip")
        self.assertEqual(scanner.result.exit_code, 2)
        self.assertEqual(scanner.result.members, 2)

    def test_unsafe_zip_paths_and_unsupported_binary_fail_closed(self):
        for members in ({"../outside.txt": b"text"}, {"C:\\outside.txt": b"text"},
                        {"asset.bin": b"\x00\x01"}):
            scanner = MODULE.Scanner()
            scanner.inspect(zipped(members), "download.zip")
            self.assertEqual(scanner.result.exit_code, 2)

    def test_unsafe_archive_paths_are_not_repeated_in_diagnostics(self):
        for name in ("C:/private-fixture/sample.txt",
                     "/private-fixture/sample.txt",
                     "../private-fixture/sample.txt"):
            for data, archive_name in ((zipped({name: b"clean"}), "download.zip"),
                                       (tarred({name: b"clean"}), "download.tar")):
                scanner = MODULE.Scanner()
                scanner.inspect(data, archive_name)
                self.assertEqual(scanner.result.exit_code, 2)
                diagnostics = "\n".join(scanner.result.findings + scanner.result.unverified)
                self.assertNotIn("private-fixture", diagnostics)
                self.assertIn("[unsafe member 1]", diagnostics)
        scanner = MODULE.Scanner()
        scanner.inspect(zipped({"C:/" + BAD + "/sample.txt": b"clean"}), "download.zip")
        self.assertTrue(scanner.result.findings)

    def test_duplicate_members_and_unknown_compression_fail_closed(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("notes.txt", b"first")
            with self.assertWarns(UserWarning):
                archive.writestr("notes.txt", b"second")
        scanner = MODULE.Scanner()
        scanner.inspect(stream.getvalue(), "download.zip")
        self.assertEqual(scanner.result.exit_code, 2)
        unknown = bytearray(zipped())
        central = unknown.index(b"PK\x01\x02")
        struct.pack_into("<H", unknown, 8, 99)
        struct.pack_into("<H", unknown, central + 10, 99)
        scanner = MODULE.Scanner()
        scanner.inspect(bytes(unknown), "download.zip")
        self.assertEqual(scanner.result.exit_code, 2)

    def test_zip_symlink_target_is_checked_without_following(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            info = zipfile.ZipInfo("shortcut")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, BAD + ".txt")
        scanner = MODULE.Scanner()
        scanner.inspect(stream.getvalue(), "download.zip")
        self.assertEqual(scanner.result.exit_code, 1)

    def test_tar_metadata_owner_link_and_extended_headers_are_checked(self):
        for archive in (tarred(owner=BAD), tarred(link=BAD + ".txt"),
                        tarred(pax={"comment": BAD})):
            scanner = MODULE.Scanner()
            scanner.inspect(archive, "download.tar")
            self.assertEqual(scanner.result.exit_code, 1)

    def test_source_distribution_author_is_checked(self):
        scanner = MODULE.Scanner()
        scanner.inspect(gzip.compress(tarred({"sample/PKG-INFO": METADATA})), "sample.tar.gz")
        self.assertEqual(scanner.result.exit_code, 0)
        scanner = MODULE.Scanner()
        scanner.inspect(gzip.compress(tarred()), "sample.tar.gz")
        self.assertEqual(scanner.result.exit_code, 1)

    def test_gzip_filename_and_comment_are_checked(self):
        archive = gzip.compress(tarred({"sample/PKG-INFO": METADATA}))
        for flag in (8, 16):
            value = archive[:3] + bytes([archive[3] | flag]) + archive[4:10] + BAD.encode() + b"\x00" + archive[10:]
            scanner = MODULE.Scanner()
            scanner.inspect(value, "sample.tar.gz")
            self.assertEqual(scanner.result.exit_code, 1)

    def test_trailing_payloads_and_unsafe_tar_links_are_unverified(self):
        for data, name in ((zipped() + b"suffix", "download.zip"),
                           (tarred() + b"suffix", "download.tar"),
                           (gzip.compress(tarred()) + gzip.compress(b"hidden"), "download.tar.gz"),
                           (tarred(link="../outside.txt"), "download.tar")):
            scanner = MODULE.Scanner()
            scanner.inspect(data, name)
            self.assertEqual(scanner.result.exit_code, 2)


class ToolkitOwnershipTests(unittest.TestCase):
    def inspect(self, name, text):
        scanner = MODULE.Scanner()
        scanner.current_toolkit_author(text.encode(), "vcf9/api_collectors/" + name)
        return scanner.result

    def test_owned_supported_files_have_an_explicit_author(self):
        for name, text in (("script.py", '# Author: Paul Bryant\nprint("ready")\n'),
                           ("inline.py", '"""Inventory module. Author: Paul Bryant."""\n'),
                           ("module.py", '__author__ = "Paul Bryant"\n'),
                           ("docs/guide.md", "# Guide\n\nAuthor: Paul Bryant\n"),
                           ("config.json", '{"author": "Paul Bryant", "targets": []}'),
                           (".gitignore", "# Author: Paul Bryant\n__pycache__/\n")):
            self.assertEqual(self.inspect(name, text).exit_code, 0)

    def test_missing_or_conflicting_author_fails(self):
        for name, text in (("script.py", 'name = "Paul Bryant"\n'),
                           ("module.py", '# Author: Paul Bryant\n__author__ = "Other Person"\n'),
                           ("notes.md", "# Notes\n"),
                           ("config.json", '{"targets": []}'),
                           ("config.json", '{"author": "Other Person"}')):
            self.assertEqual(self.inspect(name, text).exit_code, 1)

    def test_duplicate_json_authors_are_unverified(self):
        result = self.inspect("config.json", '{"author":"Other Person","author":"Paul Bryant"}')
        self.assertEqual(result.exit_code, 2)

    def test_pyproject_authors_are_checked_structurally(self):
        prefix = '# Author: Paul Bryant\n[project]\nname = "vcf-api-collectors"\n'
        self.assertEqual(self.inspect("pyproject.toml", prefix + 'authors = [{name = "Paul Bryant"}]\n').exit_code, 0)
        for suffix in ('authors = [{name = "Other Person"}]\n',
                       'authors = [{name = "Paul Bryant"}, {name = "Other Person"}]\n',
                       'authors = [{email = "person@example.com"}]\n',
                       'description = "Paul Bryant"\n'):
            self.assertEqual(self.inspect("pyproject.toml", prefix + suffix).exit_code, 1)

    def test_python_310_canonical_project_authors_fallback(self):
        original_import = __import__
        def without_tomllib(name, *args, **kwargs):
            if name == "tomllib":
                raise ImportError("Unavailable")
            return original_import(name, *args, **kwargs)
        prefix = '# Author: Paul Bryant\n[project]\nname = "vcf-api-collectors"\n'
        with patch("builtins.__import__", side_effect=without_tomllib):
            self.assertEqual(self.inspect("pyproject.toml", prefix + 'authors = [{name = "Paul Bryant"}]\n').exit_code, 0)
            self.assertEqual(self.inspect("pyproject.toml", prefix + 'authors = [{name = "Other Person"}]\n').exit_code, 1)

    def test_csv_data_and_other_project_collaborators_are_preserved(self):
        self.assertEqual(self.inspect("examples/data.csv", "name,value\nexample,1\n").exit_code, 0)
        scanner = MODULE.Scanner()
        scanner.current_toolkit_author(b"# Author: Other Person\n", "legacy/script.py")
        self.assertEqual(scanner.result.exit_code, 0)


class AttributionRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.git = shutil.which("git")
        if not self.git:
            self.skipTest("Git executable is required")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.command("init", "-q")
        self.command("config", "user.name", "Paul Bryant")
        self.command("config", "user.email", "person@example.com")
        self.command("config", "commit.gpgsign", "false")

    def command(self, *arguments):
        return subprocess.run([self.git, "-C", str(self.repo), *arguments], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def commit(self, value, message="Add sample"):
        (self.repo / "sample.txt").write_text(value, encoding="utf-8")
        self.command("add", "sample.txt")
        self.command("commit", "-q", "-m", message)

    def test_clean_repository_and_head_metadata_pass(self):
        self.commit("Author: Paul Bryant\n")
        scanner = MODULE.Scanner()
        MODULE.scan_repository(scanner, self.repo, self.git)
        self.assertEqual(scanner.result.exit_code, 0)
        self.assertEqual(scanner.result.commits, 1)

    def test_current_text_and_commit_message_are_checked(self):
        self.commit(BAD, "Add " + BAD)
        scanner = MODULE.Scanner()
        MODULE.scan_repository(scanner, self.repo, self.git)
        self.assertEqual(scanner.result.exit_code, 1)
        self.assertGreaterEqual(len(scanner.result.findings), 2)

    def test_new_tracked_toolkit_file_needs_an_author(self):
        self.commit("clean")
        module = self.repo / "vcf9" / "api_collectors" / "module.py"
        module.parent.mkdir(parents=True)
        module.write_text("value = 1\n", encoding="utf-8")
        self.command("add", "vcf9/api_collectors/module.py")
        scanner = MODULE.Scanner()
        MODULE.scan_repository(scanner, self.repo, self.git)
        self.assertEqual(scanner.result.exit_code, 1)
        self.assertTrue(any("must declare Paul Bryant" in value for value in scanner.result.findings))

    def test_historical_toolkit_ownership_is_not_rewritten(self):
        module = self.repo / "vcf9" / "api_collectors" / "module.py"
        module.parent.mkdir(parents=True)
        module.write_text("value = 1\n", encoding="utf-8")
        self.command("add", "vcf9/api_collectors/module.py")
        self.command("commit", "-q", "-m", "Add earlier module")
        module.write_text("# Author: Paul Bryant\nvalue = 2\n", encoding="utf-8")
        self.command("add", "vcf9/api_collectors/module.py")
        self.command("commit", "-q", "-m", "Update current module")
        scanner = MODULE.Scanner()
        MODULE.scan_repository(scanner, self.repo, self.git, all_history=True)
        self.assertEqual(scanner.result.exit_code, 0)
        self.assertEqual(scanner.result.commits, 2)

    def test_commit_author_and_committer_are_checked(self):
        self.command("config", "user.name", BAD)
        self.commit("clean")
        scanner = MODULE.Scanner()
        MODULE.scan_repository(scanner, self.repo, self.git)
        self.assertEqual(scanner.result.exit_code, 1)

    def test_all_history_finds_removed_content_and_old_filename(self):
        self.commit(BAD)
        self.command("mv", "sample.txt", BAD + ".txt")
        self.command("commit", "-q", "-m", "Rename sample")
        self.command("mv", BAD + ".txt", "sample.txt")
        self.commit("clean", "Update sample")
        current = MODULE.Scanner()
        MODULE.scan_repository(current, self.repo, self.git)
        self.assertEqual(current.result.exit_code, 0)
        historical = MODULE.Scanner()
        MODULE.scan_repository(historical, self.repo, self.git, all_history=True)
        self.assertEqual(historical.result.exit_code, 1)
        self.assertEqual(historical.result.commits, 3)

    def test_commit_range_limits_metadata_selection(self):
        self.commit("clean", "Initial " + BAD)
        self.commit("clean again", "Update sample")
        scanner = MODULE.Scanner()
        MODULE.scan_repository(scanner, self.repo, self.git, commit_range="HEAD~1..HEAD")
        self.assertEqual(scanner.result.exit_code, 0)
        self.assertEqual(scanner.result.commits, 1)

    def test_missing_file_and_invalid_revision_are_unverified(self):
        self.commit("clean")
        (self.repo / "sample.txt").unlink()
        scanner = MODULE.Scanner()
        MODULE.scan_repository(scanner, self.repo, self.git)
        self.assertEqual(scanner.result.exit_code, 2)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = MODULE.main(["--repo", str(self.repo), "--git", self.git,
                                  "--commit-range", "missing..HEAD"])
        self.assertEqual(result, 2)
        self.assertNotIn(str(self.repo), output.getvalue())

    def test_artifact_cli_does_not_print_contents(self):
        self.commit("clean")
        artifact = self.repo / "download.zip"
        artifact.write_bytes(zipped({"notes.txt": ("secret value " + BAD).encode()}))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = MODULE.main(["--repo", str(self.repo), "--git", self.git,
                                  "--artifact", str(artifact)])
        self.assertEqual(result, 1)
        self.assertNotIn("secret value", output.getvalue())
        self.assertNotIn(BAD, output.getvalue())


if __name__ == "__main__":
    unittest.main()
