"""JSON and CSV exports. Author: Paul Bryant."""

import csv
import json
import os
import re
import tempfile
from pathlib import Path

SECRET_KEYS = {
    "password", "passwd", "pwd", "credential", "credentials", "secret", "clientsecret",
    "token", "accesstoken", "refreshtoken", "authorization", "privatekey", "sessionid",
    "vmwareapisessionid", "cookie", "setcookie", "xsrf", "xsrftoken", "apikey",
    "sshprivatekey", "certificateprivatekey", "passphrase",
    "xhmauthorization", "xdrsession", "secretkey",
}


def sanitize(data):
    """Redact secret-bearing fields recursively; preserve ordinary inventory fields."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            secret = normalized in SECRET_KEYS or any(
                normalized.endswith(suffix) for suffix in ("password", "passwd", "secret", "privatekey", "token", "passphrase")
            )
            result[key] = "[REDACTED]" if secret else sanitize(value)
        return result
    if isinstance(data, list):
        return [sanitize(value) for value in data]
    return data


def write_json(path, data):
    """Replace a single file atomically; failed writes do not leave half a JSON document."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".inventory-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _flatten(record, prefix=""):
    result = {}
    for key, value in record.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict) and value:
            result.update(_flatten(value, name))
        elif isinstance(value, (dict, list)):
            result[name] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            result[name] = value
    return result


def _csv_value(value):
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return value


def write_resource(directory, resource, records, metadata, write_csv=True):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cleaned = sanitize(records)
    document = sanitize(metadata)
    document.update({"author": "Paul Bryant", "record_count": len(cleaned), "records": cleaned})
    # Write CSV first, then JSON. The caller reports success only after both finish.
    if write_csv:
        rows = [_flatten(row) for row in cleaned]
        columns = sorted({column for row in rows for column in row})
        handle, temporary = tempfile.mkstemp(prefix=".inventory-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(handle, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                if columns:
                    writer.writerow([_csv_value(column) for column in columns])
                    for row in rows:
                        writer.writerow([_csv_value(row.get(column, "")) for column in columns])
            os.replace(temporary, directory / f"{resource}.csv")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    write_json(directory / f"{resource}.json", document)
