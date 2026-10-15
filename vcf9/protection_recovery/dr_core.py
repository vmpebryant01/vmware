"""Session transport for VCF Protection and Recovery v2. Author: Paul Bryant."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import ssl
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from vcf9.report_core import MAX_PAGES, PAGE_SIZE, require_dict, require_items, safe_path_id as path_id
from vcf9.sddc_inventory import HOST_PATTERN, write_csv

BASE_PATH = "/api/rest/srm/v2"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class DrClient:
    """Verified-HTTPS client scoped to the SRM v2 API on one host."""

    def __init__(self, host: str, ca_bundle: str | None = None, opener=None):
        if not HOST_PATTERN.fullmatch(host) or ".." in host:
            raise ValueError("--host must be a DNS name or IPv4 address")
        self.base_url = f"https://{host}{BASE_PATH}"
        self.opener = opener or build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=ca_bundle)), NoRedirect())
        self.session_id: str | None = None

    def request(self, method: str, path: str, *, query: dict | None = None,
                basic: tuple[str, str] | None = None) -> object:
        if method not in ("GET", "POST", "DELETE") or not path.startswith("/") or path.startswith("//"):
            raise ValueError("Invalid recovery API request")
        headers = {"Accept": "application/json"}
        if self.session_id:
            headers["x-dr-session"] = self.session_id
        if basic is not None:
            encoded = base64.b64encode(f"{basic[0]}:{basic[1]}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"
        suffix = "?" + urlencode(query) if query else ""
        request = Request(self.base_url + path + suffix, data=b"" if method == "POST" else None,
                          headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                if response.status == 204:
                    return None
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"Recovery API {method} {path} returned HTTP {exc.code}") from None
        except URLError as exc:
            raise RuntimeError(f"Cannot reach recovery API: {exc.reason}") from None

    def login(self, username: str, password: str) -> None:
        response = require_dict(self.request("POST", "/session", basic=(username, password)), "/session")
        session_id = response.get("session_id")
        if not isinstance(session_id, str) or not session_id or "\r" in session_id or "\n" in session_id:
            raise RuntimeError("Recovery API did not return a valid session ID")
        self.session_id = session_id

    def remote_login(self, pairing_id: str, username: str, password: str) -> None:
        path = f"/pairings/{path_id(pairing_id, 'pairing-id')}/remote-session"
        self.request("POST", path, basic=(username, password))

    def get(self, path: str, query: dict | None = None) -> object:
        if not self.session_id:
            raise RuntimeError("Recovery API session is not authenticated")
        return self.request("GET", path, query=query)

    def logout(self) -> None:
        if self.session_id:
            try:
                self.request("DELETE", "/session")
            finally:
                self.session_id = None


def dr_items(client: DrClient, path: str) -> list[dict]:
    """Follow the API's offset/limit and total metadata without silent truncation."""
    rows: list[dict] = []
    for _ in range(MAX_PAGES):
        response = require_dict(client.get(path, {"limit": PAGE_SIZE, "offset": len(rows)}), path)
        batch = require_items(response, "list", path)
        meta = require_dict(response.get("_meta"), path)
        total = meta.get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise RuntimeError(f"Invalid total from {path}")
        errors = meta.get("errors")
        if errors:
            raise RuntimeError(f"Recovery API reported list errors for {path}")
        rows.extend(batch)
        if len(rows) > total:
            raise RuntimeError(f"Inconsistent list total from {path}")
        if len(rows) >= total:
            return rows
        if not batch:
            raise RuntimeError(f"Empty page before expected total from {path}")
    raise RuntimeError(f"Page limit reached for {path}")


def parser_for_dr(description: str, required_ids: tuple[str, ...]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--host", required=True, help="Protection and Recovery API host")
    parser.add_argument("--username", required=True, help="Local site account")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ca-bundle", help="PEM file for the issuing CA")
    for item in required_ids:
        parser.add_argument(f"--{item}", required=True)
    if "pairing-id" in required_ids:
        parser.add_argument("--remote-username", help="Remote site account; defaults to --username")
    return parser


def execute_dr(description: str, filename: str, required_ids: tuple[str, ...],
               columns: tuple[str, ...], collect, argv=None) -> int:
    args = parser_for_dr(description, required_ids).parse_args(argv)
    client = None
    try:
        for item in required_ids:
            path_id(getattr(args, item.replace("-", "_")), item)
        client = DrClient(args.host, args.ca_bundle)
        password = getpass.getpass("Local site password: ")
        try:
            client.login(args.username, password)
        finally:
            del password
        if "pairing-id" in required_ids:
            password = getpass.getpass("Remote site password: ")
            try:
                client.remote_login(args.pairing_id, args.remote_username or args.username, password)
            finally:
                del password
        rows = collect(client, args)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise RuntimeError("Report collector did not return rows")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv(args.output_dir / filename, columns, rows)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            try:
                client.logout()
            except (OSError, RuntimeError, ValueError) as exc:
                print(f"Warning: recovery API logout failed: {exc}", file=sys.stderr)
    print(f"Saved {len(rows)} rows to {args.output_dir / filename}")
    return 0
