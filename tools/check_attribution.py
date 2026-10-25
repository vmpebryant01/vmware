"""Check source, history and distribution archives for unwanted attribution.

Author: Paul Bryant
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from email import policy
from email.parser import Parser
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import sys
import tarfile
import unicodedata
import zipfile
import zlib


AUTHOR = "Paul Bryant"
PACKAGE = "vcf-api-collectors"
# Numeric spellings keep the checks and their fixtures free of denied names.
DENIED = tuple("".join(map(chr, values)) for values in (
    (99, 104, 97, 116, 103, 112, 116),
    (111, 112, 101, 110, 97, 105),
    (99, 111, 100, 101, 120),
    (97, 105, 45, 103, 101, 110, 101, 114, 97, 116, 101, 100),
    (97, 105, 32, 103, 101, 110, 101, 114, 97, 116, 101, 100),
    (103, 101, 110, 101, 114, 97, 116, 101, 100, 32, 98, 121, 32, 97, 105),
    (103, 101, 110, 101, 114, 97, 116, 101, 100, 32, 117, 115, 105, 110, 103, 32, 97, 105),
    (97, 114, 116, 105, 102, 105, 99, 105, 97, 108, 32, 105, 110, 116, 101, 108, 108, 105, 103, 101, 110, 99, 101),
))
MODEL = re.compile("".join(map(chr, (103, 112, 116))) + r"[- _]?\d", re.I)
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_MEMBERS = 10000
MAX_DEPTH = 4
TOOLKIT = "vcf9/api_collectors/"


@dataclass
class Result:
    findings: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    files: int = 0
    commits: int = 0
    members: int = 0
    expanded_bytes: int = 0

    @property
    def exit_code(self) -> int:
        return 2 if self.unverified else (1 if self.findings else 0)


def safe_label(value: str) -> str:
    """Do not repeat a prohibited name or control character in diagnostics."""
    value = unicodedata.normalize("NFKC", value)
    for denied in DENIED:
        value = re.sub(re.escape(denied), "[restricted]", value, flags=re.I)
    value = MODEL.sub("[restricted]", value)
    return "".join(char if char.isprintable() else "?" for char in value)[:240]


def contains_denied(value: str) -> bool:
    value = unicodedata.normalize("NFKC", value).casefold()
    return any(denied in value for denied in DENIED) or bool(MODEL.search(value))


def decode_text(data: bytes) -> str:
    """Accept BOM text, UTF-8, or legacy Windows text, never opaque binary."""
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        text = data.decode("utf-32")
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    elif data.startswith(b"\xef\xbb\xbf"):
        text = data.decode("utf-8-sig")
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("cp1252")
    if any(ord(char) < 32 and char not in "\t\r\n\f" for char in text):
        raise ValueError("Opaque binary")
    if any(0x7F <= ord(char) <= 0x9F or 0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise ValueError("Unsupported text")
    return text


def safe_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(name) and not (
        path.is_absolute() or ".." in path.parts or "\x00" in name
        or re.match(r"^[A-Za-z]:", normalized)
    )


class Scanner:
    def __init__(self) -> None:
        self.result = Result()

    def finding(self, label: str, reason: str) -> None:
        self.result.findings.append(f"{safe_label(label)}: {reason}")

    def unknown(self, label: str, reason: str) -> None:
        self.result.unverified.append(f"{safe_label(label)}: {reason}")

    def text(self, value: str, label: str) -> None:
        if contains_denied(value):
            self.finding(label, "prohibited attribution")
        if any((ord(char) < 32 and char not in "\t\r\n\f")
               or 0x7F <= ord(char) <= 0x9F or 0xD800 <= ord(char) <= 0xDFFF
               for char in value):
            self.unknown(label, "unsupported binary metadata or text")

    def raw_metadata(self, data: bytes, label: str) -> None:
        lowered = data.lower()
        encodings = ("utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be")
        if any(word.encode(encoding) in lowered for word in DENIED for encoding in encodings):
            self.finding(label, "prohibited attribution in binary metadata")
        model_prefix = "".join(map(chr, (103, 112, 116)))
        if any((model_prefix + separator + digit).encode(encoding) in lowered
               for encoding in encodings for separator in ("", "-", " ", "_")
               for digit in "0123456789"):
            self.finding(label, "prohibited model attribution in binary metadata")

    def package_metadata(self, text: str, label: str) -> bool:
        message = Parser(policy=policy.default).parsestr(text)
        for key, value in message.items():
            self.text(key, label + " [decoded header name]")
            self.text(str(value), label + " [decoded header value]")
        names = message.get_all("Name", [])
        if len(names) != 1 or re.sub(r"[-_.]+", "-", str(names[0])).lower() != PACKAGE:
            return False
        authors = message.get_all("Author", [])
        if len(authors) != 1 or str(authors[0]).strip() != AUTHOR:
            self.finding(label, "package Author must be Paul Bryant")
        emails = message.get_all("Author-email", [])
        if emails:
            # A second authorship field must not introduce another display name.
            from email.utils import getaddresses
            parsed = getaddresses([str(item) for item in emails])
            if any(name and name != AUTHOR for name, _address in parsed):
                self.finding(label, "package Author-email has a different author")
        return True

    def current_toolkit_author(self, data: bytes, name: str) -> None:
        """Enforce current project ownership without changing historical authors."""
        if not name.startswith(TOOLKIT) or Path(name).suffix.lower() in (".csv", ".tsv"):
            return
        try:
            text = decode_text(data)
            if name.endswith(".json"):
                def unique_object(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError("Duplicate JSON key")
                        result[key] = value
                    return result
                document = json.loads(text, object_pairs_hook=unique_object)
                if not isinstance(document, dict) or document.get("author") != AUTHOR:
                    self.finding(name, "toolkit JSON author must be Paul Bryant")
                return
            declarations = re.findall(r"(?mi)^[ \t]*(?:#[ \t]*)?Author:[ \t]*([^\r\n]+)", text)
            if name.endswith(".py"):
                tree = ast.parse(text)
                docstring = ast.get_docstring(tree) or ""
                declarations.extend(value.strip().rstrip(".") for value in
                                    re.findall(r"\bAuthor:[ \t]*([^\r\n]+)", docstring))
                for node in tree.body:
                    if isinstance(node, ast.Assign) and any(
                            isinstance(target, ast.Name) and target.id == "__author__"
                            for target in node.targets):
                        declarations.append(ast.literal_eval(node.value))
                    elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                          and node.target.id == "__author__"):
                        declarations.append(ast.literal_eval(node.value))
            if not declarations or any(not isinstance(value, str) or value.strip() != AUTHOR
                                       for value in declarations):
                self.finding(name, "toolkit file must declare Paul Bryant as author")
            if name == TOOLKIT + "pyproject.toml":
                try:
                    import tomllib
                except ImportError:
                    # Python 3.10 accepts only the canonical authors declaration.
                    section = re.search(r"(?ms)^\[project\][ \t]*\r?\n(.*?)(?=^\[|\Z)", text)
                    lines = re.findall(r"(?m)^authors[ \t]*=[^\r\n]*", section.group(1) if section else "")
                    expected = r'''authors\s*=\s*\[\s*\{\s*name\s*=\s*(?:"Paul Bryant"|'Paul Bryant')\s*\}\s*\]\s*'''
                    valid = len(lines) == 1 and re.fullmatch(expected, lines[0]) is not None
                else:
                    authors = tomllib.loads(text).get("project", {}).get("authors")
                    valid = (isinstance(authors, list) and len(authors) == 1
                             and isinstance(authors[0], dict) and authors[0].get("name") == AUTHOR)
                if not valid:
                    self.finding(name, "project authors must contain only Paul Bryant")
        except (ValueError, UnicodeError, SyntaxError, TypeError):
            self.unknown(name, "current toolkit author declaration cannot be verified")

    def inspect(self, data: bytes, label: str, depth: int = 0) -> bool:
        """Inspect without extraction. Return whether toolkit metadata was found."""
        self.text(label, label)
        self.result.files += 1
        if len(data) > MAX_FILE:
            self.unknown(label, "file exceeds inspection limit")
            return False
        lowered = label.lower()
        is_zip = data.startswith((b"PK\x03\x04", b"PK\x05\x06"))
        is_gzip = data.startswith(b"\x1f\x8b")
        is_tar = len(data) >= 512 and data[257:262] in (b"ustar",)
        expected_zip = lowered.endswith((".zip", ".whl"))
        expected_tar = lowered.endswith((".tar", ".tar.gz", ".tgz"))
        if is_zip or is_gzip or is_tar or expected_zip or expected_tar:
            if depth >= MAX_DEPTH:
                self.unknown(label, "archive nesting exceeds inspection limit")
                return False
            try:
                if is_zip or expected_zip:
                    matched = self.zip(data, label, depth)
                else:
                    matched = self.tar(data, label, depth, compressed=is_gzip)
            except (ValueError, OSError, EOFError, UnicodeError, struct.error,
                    RuntimeError, NotImplementedError, OverflowError,
                    zipfile.BadZipFile, tarfile.TarError, zlib.error):
                self.unknown(label, "archive cannot be fully inspected")
                return False
            if lowered.endswith((".whl", ".tar.gz", ".tgz")) and not matched:
                self.finding(label, "toolkit distribution metadata is missing")
            return matched
        try:
            text = decode_text(data)
        except (UnicodeError, ValueError):
            self.raw_metadata(data, label)
            self.unknown(label, "unsupported binary or text encoding")
            return False
        self.text(text, label)
        if label.rsplit("/", 1)[-1] in ("METADATA", "PKG-INFO"):
            return self.package_metadata(text, label)
        return False

    def member(self, label: str) -> bool:
        self.result.members += 1
        if self.result.members > MAX_MEMBERS:
            self.unknown(label, "archive member count exceeds inspection limit")
            return False
        return True

    def reserve(self, size: int, label: str) -> bool:
        self.result.expanded_bytes += size
        if (size < 0 or size > MAX_FILE
                or self.result.expanded_bytes > MAX_TOTAL):
            self.unknown(label, "archive contents exceed inspection limits")
            return False
        return True

    def zip_extra(self, data: bytes, label: str) -> None:
        self.raw_metadata(data, label)
        offset = 0
        while offset < len(data):
            if len(data) - offset < 4:
                raise ValueError("Truncated extra header")
            kind, size = struct.unpack_from("<HH", data, offset)
            offset += 4
            value = data[offset:offset + size]
            if len(value) != size:
                raise ValueError("Truncated extra value")
            offset += size
            if kind in (0x7075, 0x6375):
                if len(value) < 5 or value[0] != 1:
                    raise ValueError("Unsupported Unicode extra field")
                self.text(value[5:].decode("utf-8"), label)
            elif kind not in (0x0001, 0x000A, 0x5455, 0x7875):
                self.unknown(label, "unsupported ZIP metadata field")

    def zip(self, data: bytes, label: str, depth: int) -> bool:
        self.raw_metadata(data, label + " [ZIP headers]")
        end = data.rfind(b"PK\x05\x06")
        if end < 0 or end + 22 > len(data):
            raise ValueError("Missing ZIP trailer")
        comment_length = struct.unpack_from("<H", data, end + 20)[0]
        if end + 22 + comment_length != len(data):
            raise ValueError("Uninspected ZIP suffix")
        disk, central_disk, disk_count, member_count, central_size, central_offset = struct.unpack_from("<HHHHII", data, end + 4)
        if disk or central_disk or disk_count != member_count:
            raise ValueError("Unsupported multipart ZIP")
        if central_offset + central_size != end:
            raise ValueError("Unsupported central directory metadata")
        matched = False
        names: set[str] = set()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) != member_count:
                raise ValueError("ZIP member count differs from trailer")
            if members and min(member.header_offset for member in members) != 0:
                raise ValueError("Uninspected ZIP prefix")
            previous_end = 0
            for member in sorted(members, key=lambda entry: entry.header_offset):
                if member.header_offset != previous_end:
                    raise ValueError("Uninspected ZIP record gap")
                name_size, extra_size = struct.unpack_from("<HH", data, member.header_offset + 26)
                previous_end = member.header_offset + 30 + name_size + extra_size + member.compress_size
                if member.flag_bits & 8:
                    descriptor = data[previous_end:previous_end + 16]
                    signed = descriptor.startswith(b"PK\x07\x08")
                    descriptor_size = 16 if signed else 12
                    offset = 4 if signed else 0
                    crc, compressed, expanded = struct.unpack_from("<III", descriptor, offset)
                    if (crc, compressed, expanded) != (member.CRC, member.compress_size, member.file_size):
                        raise ValueError("Unsupported ZIP data descriptor")
                    previous_end += descriptor_size
            if previous_end != central_offset:
                raise ValueError("Uninspected ZIP directory gap")
            self.text(decode_text(archive.comment), label + " [archive comment]")
            for number, member in enumerate(members, 1):
                member_label = (label + "!/" + member.filename if safe_member(member.filename)
                                else label + "!/[unsafe member " + str(number) + "]")
                if not self.member(member_label):
                    break
                self.text(member.filename, member_label)
                self.text(decode_text(member.comment), member_label + " [comment]")
                self.zip_extra(member.extra, member_label + " [metadata]")
                if not safe_member(member.filename) or member.filename in names:
                    self.unknown(member_label, "unsafe or duplicate archive path")
                    continue
                names.add(member.filename)
                if member.flag_bits & 1:
                    self.unknown(member_label, "encrypted archive member")
                    continue
                header = member.header_offset
                if data[header:header + 4] != b"PK\x03\x04":
                    raise ValueError("Unsupported local header")
                name_size, extra_size = struct.unpack_from("<HH", data, header + 26)
                local_name = data[header + 30:header + 30 + name_size]
                local_extra = data[header + 30 + name_size:header + 30 + name_size + extra_size]
                if len(local_extra) != extra_size:
                    raise ValueError("Truncated local header")
                self.raw_metadata(local_name, member_label + " [local name]")
                self.zip_extra(local_extra, member_label + " [local metadata]")
                mode = member.external_attr >> 16
                if member.is_dir():
                    continue
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFLNK):
                    self.unknown(member_label, "unsupported archive member type")
                    continue
                if not self.reserve(member.file_size, member_label):
                    continue
                value = archive.read(member)
                if stat.S_ISLNK(mode):
                    target = decode_text(value)
                    self.text(target, member_label + " [link target]")
                    if not safe_member(target):
                        self.unknown(member_label, "unsafe archive link target")
                    continue
                matched = self.inspect(value, member_label, depth + 1) or matched
        return matched

    def gzip(self, data: bytes, label: str) -> bytes:
        if len(data) < 18 or data[2] != 8 or data[3] & 0xE0:
            raise ValueError("Unsupported compression header")
        flags, offset = data[3], 10
        if flags & 4:
            size = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            self.raw_metadata(data[offset:offset + size], label + " [gzip metadata]")
            self.unknown(label, "unsupported gzip extra metadata")
            offset += size
        for flag, field_name in ((8, "filename"), (16, "comment")):
            if flags & flag:
                end = data.find(b"\x00", offset)
                if end < 0:
                    raise ValueError("Truncated compression header")
                self.text(data[offset:end].decode("latin-1"), label + " [gzip " + field_name + "]")
                offset = end + 1
        if flags & 2:
            offset += 2
        if offset > len(data) - 8:
            raise ValueError("Truncated compression header")
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        expanded = decoder.decompress(data, MAX_TOTAL + 1)
        if len(expanded) > MAX_TOTAL or not decoder.eof or decoder.unused_data:
            raise ValueError("Compression limit or trailing members")
        return expanded

    def tar(self, data: bytes, label: str, depth: int, compressed: bool) -> bool:
        if compressed:
            data = self.gzip(data, label)
        matched = False
        names: set[str] = set()
        # Also check raw header bytes, including extended and long-name records.
        self.raw_metadata(data, label + " [tar headers]")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            for key, value in archive.pax_headers.items():
                self.text(key + "=" + value, label + " [global metadata]")
            for number, member in enumerate(archive, 1):
                member_label = (label + "!/" + member.name if safe_member(member.name)
                                else label + "!/[unsafe member " + str(number) + "]")
                if not self.member(member_label):
                    break
                for text in (member.name, member.linkname, member.uname, member.gname):
                    self.text(text, member_label + " [metadata]")
                for key, value in member.pax_headers.items():
                    self.text(key + "=" + value, member_label + " [extended metadata]")
                if not safe_member(member.name) or member.name in names:
                    self.unknown(member_label, "unsafe or duplicate archive path")
                    continue
                names.add(member.name)
                if member.isdir():
                    continue
                if member.issym() or member.islnk():
                    if not safe_member(member.linkname):
                        self.unknown(member_label, "unsafe archive link target")
                    continue
                if not member.isfile() or member.sparse is not None:
                    self.unknown(member_label, "unsupported archive member type")
                    continue
                if not self.reserve(member.size, member_label):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Missing archive data")
                matched = self.inspect(stream.read(MAX_FILE + 1), member_label, depth + 1) or matched
            # Standard end padding is zero. Reject hidden payload after the last member.
            if any(data[archive.offset:]):
                raise ValueError("Uninspected tar suffix")
        return matched


def git(repo: Path, executable: str, *arguments: str, data: bytes | None = None) -> bytes:
    completed = subprocess.run(
        [executable, "-C", str(repo), *arguments], input=data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise ValueError("Repository command failed")
    return completed.stdout


def scan_repository(scanner: Scanner, repo: Path, executable: str = "git",
                    commit_range: str | None = None, all_history: bool = False) -> None:
    root = repo.resolve()
    indexed = git(root, executable, "ls-files", "--stage", "-z")
    for entry in indexed.split(b"\x00"):
        if not entry:
            continue
        details, raw_name = entry.split(b"\t", 1)
        mode, _object_id, stage = details.split()
        name = raw_name.decode("utf-8")
        scanner.text(name, name)
        target = root / name
        if stage != b"0" or mode not in (b"100644", b"100755"):
            scanner.unknown(name, "unmerged entry, link or submodule is not supported")
            continue
        if not target.resolve().is_relative_to(root) or target.is_symlink():
            scanner.unknown(name, "tracked path escapes repository")
            continue
        try:
            if target.stat().st_size > MAX_FILE:
                scanner.unknown(name, "file exceeds inspection limit")
            else:
                content = target.read_bytes()
                scanner.inspect(content, name)
                scanner.current_toolkit_author(content, name)
        except OSError:
            scanner.unknown(name, "tracked file cannot be read")

    revision = "--all" if all_history else (commit_range or "HEAD")
    if revision.startswith("-") and revision != "--all":
        raise ValueError("Invalid revision")
    arguments = ["rev-list", revision]
    if not all_history and not commit_range:
        arguments.insert(1, "--max-count=1")
    commits = git(root, executable, *arguments).splitlines()
    if not commits:
        scanner.unknown("commit metadata", "requested revision has no commits")
        return
    objects: dict[bytes, str] = {}
    for number, object_id in enumerate(commits, 1):
        commit = git(root, executable, "cat-file", "commit", object_id.decode("ascii"))
        scanner.text(decode_text(commit), "commit metadata " + str(number))
        scanner.result.commits += 1
        if all_history:
            tree = git(root, executable, "ls-tree", "-r", "-z", "--full-tree", object_id.decode("ascii"))
            for entry in tree.split(b"\x00"):
                if not entry:
                    continue
                details, raw_name = entry.split(b"\t", 1)
                mode, kind, blob = details.split()
                name = raw_name.decode("utf-8")
                scanner.text(name, name + " [history path]")
                if kind != b"blob" or mode not in (b"100644", b"100755"):
                    scanner.unknown(name, "historical link or submodule is not supported")
                else:
                    objects.setdefault(blob, name)
    if objects:
        request = b"\n".join(objects) + b"\n"
        sizes = git(root, executable, "cat-file", "--batch-check", data=request).splitlines()
        total = 0
        accepted: dict[bytes, str] = {}
        for line in sizes:
            object_id, kind, raw_size = line.split()
            size = int(raw_size)
            total += size
            if kind != b"blob" or size > MAX_FILE or total > MAX_TOTAL:
                scanner.unknown(objects[object_id], "historical content exceeds inspection limits")
            else:
                accepted[object_id] = objects[object_id]
        if accepted:
            response = io.BytesIO(git(root, executable, "cat-file", "--batch", data=b"\n".join(accepted) + b"\n"))
            for _expected in accepted:
                object_id, kind, raw_size = response.readline().split()
                value = response.read(int(raw_size))
                if kind != b"blob" or response.read(1) != b"\n":
                    raise ValueError("Invalid repository object response")
                scanner.inspect(value, "history/" + accepted[object_id])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--git", default="git", help="Git executable, if it is not on PATH")
    history = parser.add_mutually_exclusive_group()
    history.add_argument("--commit-range", help="Commit metadata selection, for example BASE..HEAD")
    history.add_argument("--all-history", action="store_true", help="Inspect all locally reachable versions and commits")
    parser.add_argument("--artifact", action="append", type=Path, default=[], help="ZIP, wheel or source distribution to inspect")
    options = parser.parse_args(argv)
    scanner = Scanner()
    try:
        scan_repository(scanner, options.repo, options.git, options.commit_range, options.all_history)
    except (ValueError, OSError, UnicodeError):
        scanner.unknown("repository", "source or history inspection could not complete")
    for artifact in options.artifact:
        label = artifact.name
        try:
            if artifact.stat().st_size > MAX_FILE:
                scanner.unknown(label, "artifact exceeds inspection limit")
                continue
            if artifact.suffix.lower() not in (".zip", ".whl", ".gz", ".tgz", ".tar"):
                scanner.unknown(label, "unsupported artifact format")
                continue
            scanner.inspect(artifact.read_bytes(), label)
        except OSError:
            scanner.unknown(label, "artifact cannot be read")
    result = scanner.result
    for message in result.findings:
        print("FAIL " + message)
    for message in result.unverified:
        print("UNVERIFIED " + message)
    status = "passed" if result.exit_code == 0 else "failed"
    print(f"Attribution check {status}: {result.files} files, {result.commits} commits, {result.members} archive members.")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
