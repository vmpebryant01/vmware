"""Shared evidence and time handling for saved-run reports. Author: Paul Bryant."""

import math
from datetime import datetime, timezone

from .runs import _json


def parse_time(value, epoch_unit=None):
    """Return aware UTC time; numeric timestamps require an explicit documented unit."""
    try:
        if isinstance(value, datetime):
            result = value
        elif isinstance(value, str) and value.strip():
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif type(value) in (int, float) and math.isfinite(value) and value > 0 and epoch_unit in ("seconds", "milliseconds"):
            result = datetime.fromtimestamp(value / (1000 if epoch_unit == "milliseconds" else 1), timezone.utc)
        else:
            return None
        if result.tzinfo is None or result.utcoffset() is None:
            return None
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def positive_number(value, label, maximum=876000):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(f"{label} must be a positive finite number no greater than {maximum}.")
    return value


def documents(run, component, resource):
    return [document for key, document in sorted(run["resources"].items()) if key[1:] == (component, resource)]


def read_policy(path):
    return _json(path)


def record_index(document, field):
    """Return unique records and ambiguous IDs, without resolving duplicates arbitrarily."""
    unique, ambiguous = {}, set()
    for row in document["records"]:
        identity = row.get(field)
        if not isinstance(identity, str) or not identity:
            continue
        if identity in unique or identity in ambiguous:
            unique.pop(identity, None)
            ambiguous.add(identity)
        else:
            unique[identity] = row
    return unique, ambiguous
