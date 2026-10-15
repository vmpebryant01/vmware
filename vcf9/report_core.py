"""Shared read-only report transport and pagination. Author: Paul Bryant."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import ssl
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from vcf9.sddc_inventory import HOST_PATTERN, SddcClient, ensure_vcf91, write_csv

PAGE_SIZE = 100
MAX_PAGES = 1000
ID_PATTERN = re.compile(r"[A-Za-z0-9_.:-]+\Z")


def safe_path_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value) or value in (".", ".."):
        raise ValueError(f"--{label} must be a simple identifier")
    return quote(value, safe="")


def select_scalar(item: dict, field: str, args) -> object:
    """Select one explicitly approved CSV field without dumping nested payloads."""
    if field.startswith("$"):
        return getattr(args, field[1:])
    if field.startswith("#"):
        value = item.get(field[1:])
        return len(value) if isinstance(value, list) else None
    value: object = item
    for key in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, (str, int, float, bool)) or value is None else None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class ReadClient:
    """GET-only HTTPS client that does not forward credentials through redirects."""

    def __init__(self, host: str, authorization: str, ca_bundle: str | None = None, opener=None):
        if not HOST_PATTERN.fullmatch(host) or ".." in host:
            raise ValueError("--host must be a DNS name or IPv4 address")
        self.base_url = f"https://{host}"
        self.authorization = authorization
        self.opener = opener or build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=ca_bundle)), NoRedirect())

    def get(self, path: str, query: dict | None = None) -> object:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("API path must be relative to the target host")
        suffix = "?" + urlencode(query) if query else ""
        request = Request(self.base_url + path + suffix, headers={"Accept": "application/json", "Authorization": self.authorization}, method="GET")
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"GET {path} returned HTTP {exc.code}") from None
        except URLError as exc:
            raise RuntimeError(f"Cannot reach {self.base_url}: {exc.reason}") from None


def require_dict(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise RuntimeError(f"Unexpected response from {path}")
    return value


def require_items(value: object, key: str, path: str) -> list[dict]:
    result = require_dict(value, path).get(key)
    if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
        raise RuntimeError(f"Unexpected {key} list from {path}")
    return result


def page_items(client: ReadClient, path: str, key: str, style: str, query: dict | None = None) -> list[dict]:
    """Read paged VCF Operations or VCF Automation results, with a hard limit."""
    rows: list[dict] = []
    for page in range(MAX_PAGES):
        params = {**(query or {}), "page": page}
        params["pageSize" if style == "ops" else "size"] = PAGE_SIZE
        response = require_dict(client.get(path, params), path)
        batch = require_items(response, key, path)
        rows.extend(batch)
        metadata = response.get("pageInfo") if style == "ops" else response
        if not isinstance(metadata, dict):
            raise RuntimeError(f"Missing pagination metadata from {path}")
        if style == "ops":
            total = metadata.get("totalCount")
            if not isinstance(total, int) or total < 0:
                raise RuntimeError(f"Invalid totalCount from {path}")
            if len(rows) >= total:
                return rows
        else:
            total_pages = metadata.get("totalPages")
            if not isinstance(total_pages, int) or total_pages < 0 or total_pages > MAX_PAGES:
                raise RuntimeError(f"Invalid totalPages from {path}")
            if page + 1 >= total_pages:
                return rows
        if not batch:
            raise RuntimeError(f"Empty page before expected total from {path}")
    raise RuntimeError(f"Page limit reached for {path}")


def cursor_items(client: ReadClient, path: str, query: dict | None = None) -> list[dict]:
    """Read NSX policy pages while rejecting repeated cursors."""
    rows: list[dict] = []
    cursor = None
    seen: set[str] = set()
    for _ in range(MAX_PAGES):
        params = {**(query or {}), "page_size": PAGE_SIZE}
        if cursor is not None:
            params["cursor"] = cursor
        response = require_dict(client.get(path, params), path)
        rows.extend(require_items(response, "results", path))
        next_cursor = response.get("cursor")
        if not next_cursor:
            return rows
        if not isinstance(next_cursor, str) or next_cursor in seen:
            raise RuntimeError(f"Invalid or repeated cursor from {path}")
        seen.add(next_cursor)
        cursor = next_cursor
    raise RuntimeError(f"Page limit reached for {path}")


def parser_for(description: str, target: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--host", required=True, help=f"{target} DNS name or IPv4 address")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ca-bundle", help="PEM file for the issuing CA")
    if target == "SDDC Manager":
        parser.add_argument("--username", required=True)
    if target == "VCF Operations":
        parser.add_argument("--token-scheme", choices=("OpsToken", "Bearer"), default="OpsToken",
                            help="Use Bearer for a VCF SSO access token")
    if target == "NSX Manager":
        parser.add_argument("--username", required=True)
    return parser


def client_for(args: argparse.Namespace, target: str):
    if target == "SDDC Manager":
        client = SddcClient(args.host, args.ca_bundle)
        password = getpass.getpass("SDDC Manager password: ")
        try:
            client.authenticate(args.username, password)
        finally:
            del password
        appliance = ensure_vcf91(client)
        if not re.match(r"^9\.1\.1(?:\.|$)", str(appliance.get("version", ""))):
            raise RuntimeError("This report expects SDDC Manager 9.1.1.x")
        return client
    if target == "NSX Manager":
        password = getpass.getpass("NSX Manager password: ")
        try:
            encoded = base64.b64encode(f"{args.username}:{password}".encode("utf-8")).decode("ascii")
        finally:
            del password
        return ReadClient(args.host, f"Basic {encoded}", args.ca_bundle)
    if target not in ("VCF Operations", "VCF Automation"):
        raise ValueError(f"Unknown target type: {target}")
    token_name = "VCF_OPS_TOKEN" if target == "VCF Operations" else "VCF_AUTOMATION_TOKEN"
    token = os.environ.get(token_name, "").strip()
    if not token or "\r" in token or "\n" in token:
        raise ValueError(f"Set {token_name} to a valid access token")
    scheme = args.token_scheme if target == "VCF Operations" else "Bearer"
    return ReadClient(args.host, f"{scheme} {token}", args.ca_bundle)


def execute(parser: argparse.ArgumentParser, target: str, filename: str, columns: tuple[str, ...], collect, argv=None) -> int:
    args = parser.parse_args(argv)
    client = None
    try:
        client = client_for(args, target)
        rows = collect(client, args)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise RuntimeError("Report collector did not return rows")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv(args.output_dir / filename, columns, rows)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if isinstance(client, SddcClient):
            client.access_token = None
    print(f"Saved {len(rows)} rows to {args.output_dir / filename}")
    return 0
