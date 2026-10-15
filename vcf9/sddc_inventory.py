"""Read-only SDDC Manager 9.1.x inventory export. Author: Paul Bryant."""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import re
import ssl
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PAGE_SIZE = 100
MAX_PAGES = 1000
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


def safe_cell(value: object) -> str:
    """Keep spreadsheet applications from interpreting inventory text as formulas."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    result = "" if value is None else str(value)
    if result.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + result
    return result


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: safe_cell(row.get(column)) for column in columns})


class SddcClient:
    def __init__(self, host: str, ca_bundle: str | None = None, opener=urlopen):
        if not HOST_PATTERN.fullmatch(host) or ".." in host:
            raise ValueError("--host must be an SDDC Manager DNS name or IPv4 address")
        self.base_url = f"https://{host}"
        self.context = ssl.create_default_context(cafile=ca_bundle)
        self.opener = opener
        self.access_token: str | None = None

    def request_json(self, method: str, path: str, body: dict | None = None) -> object:
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener(request, timeout=30, context=self.context) as response:
                return json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"SDDC Manager {method} {path.split('?')[0]} returned HTTP {exc.code}") from None
        except URLError as exc:
            raise RuntimeError(f"Cannot reach SDDC Manager: {exc.reason}") from None

    def authenticate(self, username: str, password: str) -> None:
        result = self.request_json("POST", "/v1/tokens", {"username": username, "password": password})
        if not isinstance(result, dict) or not isinstance(result.get("accessToken"), str):
            raise RuntimeError("SDDC Manager did not return an access token")
        self.access_token = result["accessToken"]

    def get_pages(self, path: str, *, filters: dict[str, int | str] | None = None) -> list[dict]:
        rows: list[dict] = []
        for page_number in range(MAX_PAGES):
            query = urlencode({**(filters or {}), "pageNumber": page_number, "pageSize": PAGE_SIZE})
            result = self.request_json("GET", f"{path}?{query}")
            if not isinstance(result, dict) or not isinstance(result.get("elements"), list):
                raise RuntimeError(f"Unexpected response from {path}")
            if not all(isinstance(item, dict) for item in result["elements"]):
                raise RuntimeError(f"Unexpected list item from {path}")
            rows.extend(result["elements"])
            metadata = result.get("pageMetadata")
            if not isinstance(metadata, dict) or not isinstance(metadata.get("totalPages"), int):
                raise RuntimeError(f"Missing pagination metadata from {path}")
            total_pages = metadata["totalPages"]
            if total_pages < 0 or total_pages > MAX_PAGES:
                raise RuntimeError(f"Invalid page count from {path}")
            if page_number + 1 >= total_pages:
                return rows
        raise RuntimeError(f"Page limit reached for {path}")


def ensure_vcf91(client: SddcClient) -> dict:
    appliance = client.request_json("GET", "/v1/system/appliance-info")
    if not isinstance(appliance, dict):
        raise RuntimeError("Unexpected appliance information response")
    version = appliance.get("version", "")
    if not isinstance(version, str) or not version.startswith("9.1."):
        raise RuntimeError(f"Expected SDDC Manager 9.1.x; reported version: {version or 'unknown'}")
    if appliance.get("role") != "SddcManager":
        raise RuntimeError("The target is not an SDDC Manager appliance")
    return appliance


def collect(client: SddcClient) -> dict[str, object]:
    appliance = ensure_vcf91(client)
    return {
        "appliance": appliance,
        "domains": client.get_pages("/v1/domains"),
        "clusters": client.get_pages("/v1/clusters"),
        "hosts": client.get_pages("/v1/hosts"),
    }


def export_inventory(inventory: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    appliance = inventory["appliance"]
    write_csv(output_dir / "appliance.csv", ("role", "version", "dnsDomain"), [appliance])
    write_csv(output_dir / "domains.csv", ("id", "name", "type", "status", "lifecycleManagementMode"), inventory["domains"])
    clusters = [
        {"id": item.get("id"), "name": item.get("name"), "domain": (item.get("domain") or {}).get("name"),
         "status": item.get("status"), "primaryDatastoreType": item.get("primaryDatastoreType"),
         "isImageBased": item.get("isImageBased")}
        for item in inventory["clusters"]
    ]
    write_csv(output_dir / "clusters.csv", ("id", "name", "domain", "status", "primaryDatastoreType", "isImageBased"), clusters)
    write_csv(output_dir / "hosts.csv", ("id", "fqdn", "status", "esxiVersion", "hardwareVendor", "hardwareModel"), inventory["hosts"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="SDDC Manager DNS name or IPv4 address")
    parser.add_argument("--username", required=True, help="SDDC Manager user name")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ca-bundle", help="PEM file containing the trusted issuing CA")
    args = parser.parse_args(argv)
    try:
        client = SddcClient(args.host, args.ca_bundle)
        password = getpass.getpass("SDDC Manager password: ")
        client.authenticate(args.username, password)
        del password
        try:
            inventory = collect(client)
        finally:
            client.access_token = None
        export_inventory(inventory, args.output_dir)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Saved four CSV reports in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
