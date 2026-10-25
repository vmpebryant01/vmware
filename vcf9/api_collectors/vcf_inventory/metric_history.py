"""Explicitly bounded Operations historical metric queries. Author: Paul Bryant."""

import math
import re

from .http_client import ApiError
from .products.operations import _unit_metadata
from .report_support import parse_time


COMPONENT = "vcf_operations"
RESOURCE_PATHS = {COMPONENT: {"metric_history": "/suite-api/api/resources/stats"}}
DEFAULT_RESOURCES = {}
ALLOWED_OPERATIONS = set()
INTERVAL_SECONDS = {"SECONDS": 1, "MINUTES": 60, "HOURS": 3600, "DAYS": 86400, "WEEKS": 604800}
INTERVAL_TYPES = set(INTERVAL_SECONDS) | {"MONTHS", "YEARS"}
ROLLUPS = {"AVG", "MIN", "MAX", "SUM", "COUNT"}
MAX_SERIES = 1000
MAX_SAMPLES = 10000


def finite_number(value):
    """Accept finite machine-range JSON numbers without overflowing on large integers."""
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def supports(component, resource):
    return resource in RESOURCE_PATHS.get(component, {})


def _strings(values, label, identifiers=False):
    if (not isinstance(values, list) or not values or len(values) > 1000
            or any(not isinstance(item, str) or not item or len(item) > 1000
                   or any(ord(char) < 32 or ord(char) == 127 for char in item) for item in values)
            or len(set(values)) != len(values)
            or (identifiers and any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", item) for item in values))):
        raise ValueError(f"Metric history {label} must be a nonempty unique string array within its documented limits.")


def _windows(settings):
    windows = settings.get("windows")
    if not isinstance(windows, list) or not 1 <= len(windows) <= 2:
        raise ValueError("metric_history.windows requires one or two explicit time windows.")
    result, labels = [], set()
    for window in windows:
        if not isinstance(window, dict) or set(window) != {"label", "begin", "end"}:
            raise ValueError("Each metric history window requires exactly label, begin and end.")
        label = window["label"]
        if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", label) or label in labels:
            raise ValueError("Metric history window labels must be unique simple identifiers of 1-40 characters.")
        labels.add(label)
        begin = parse_time(window["begin"]) if isinstance(window["begin"], str) else None
        end = parse_time(window["end"]) if isinstance(window["end"], str) else None
        if begin is None or end is None or not 0 < (end - begin).total_seconds() <= 366 * 86400:
            raise ValueError("Metric history windows require aware ISO timestamps and a positive duration no greater than 366 days.")
        begin_ms, end_ms = int(begin.timestamp() * 1000), int(end.timestamp() * 1000)
        if begin_ms <= 0 or end_ms <= begin_ms:
            raise ValueError("Metric history window timestamps must be positive and distinct at millisecond resolution.")
        result.append({"label": label, "begin_ms": begin_ms, "end_ms": end_ms})
    return result


def validate_target(target):
    """Require selected resources, selected metric keys and fixed bounded windows."""
    selected = target.get("resources", [])
    if not isinstance(selected, list):
        raise ValueError("resources must be an array.")
    if "metric_history" not in target and "metric_history" not in selected:
        return
    if target.get("component") != COMPONENT:
        raise ValueError("metric_history is supported only for VCF Operations.")
    settings = target.get("metric_history")
    if (not isinstance(settings, dict)
            or set(settings) != {"windows", "rollup_type", "interval_type", "interval_quantifier"}):
        raise ValueError("metric_history requires windows, rollup_type, interval_type and interval_quantifier.")
    if (not isinstance(settings["rollup_type"], str) or settings["rollup_type"] not in ROLLUPS
            or not isinstance(settings["interval_type"], str) or settings["interval_type"] not in INTERVAL_SECONDS):
        raise ValueError("Metric history requires an explicit supported rollup and fixed interval.")
    quantifier = settings["interval_quantifier"]
    if type(quantifier) is not int or not 1 <= quantifier <= 1000000:
        raise ValueError("metric_history.interval_quantifier must be an integer from 1 to 1000000.")
    _strings(target.get("resource_ids"), "resource_ids", identifiers=True)
    _strings(target.get("stat_keys"), "stat_keys")
    windows = _windows(settings)
    series_count = len(target["resource_ids"]) * len(target["stat_keys"]) * len(windows)
    if series_count > MAX_SERIES:
        raise ValueError("Metric history is limited to 1000 selected resource, key and window combinations.")
    interval_ms = INTERVAL_SECONDS[settings["interval_type"]] * quantifier * 1000
    expected = [math.ceil((window["end_ms"] - window["begin_ms"]) / interval_ms) for window in windows]
    if any(value > MAX_SAMPLES for value in expected) or sum(expected) * len(target["resource_ids"]) * len(target["stat_keys"]) > 1000000:
        raise ValueError("Metric history exceeds its nominal sample budget; choose shorter windows or coarser intervals.")


def validated_scope(collection):
    """Return complete saved scope only when it satisfies the collector's same limits."""
    if not isinstance(collection, dict) or collection.get("coverage") != "complete":
        return None
    windows = collection.get("windows")
    if not isinstance(windows, list) or not 1 <= len(windows) <= 2:
        return None
    normalized = []
    for window in windows:
        if (not isinstance(window, dict) or set(window) != {"label", "begin_ms", "end_ms"}
                or type(window["begin_ms"]) is not int or type(window["end_ms"]) is not int
                or not 0 < window["begin_ms"] < window["end_ms"]
                or window["end_ms"] - window["begin_ms"] > 366 * 86400 * 1000):
            return None
        begin, end = (parse_time(window[field], "milliseconds") for field in ("begin_ms", "end_ms"))
        if begin is None or end is None:
            return None
        normalized.append({"label": window["label"], "begin": begin.isoformat(), "end": end.isoformat()})
    target = {"component": COMPONENT, "resources": ["metric_history"],
              "resource_ids": collection.get("resource_ids"), "stat_keys": collection.get("stat_keys"),
              "metric_history": {"windows": normalized, "rollup_type": collection.get("requested_rollup_type"),
                                 "interval_type": collection.get("requested_interval_type"),
                                 "interval_quantifier": collection.get("requested_interval_quantifier")}}
    try:
        validate_target(target)
    except ValueError:
        return None
    return collection


class _Budget:
    def __init__(self, client, maximum, details):
        self.client, self.maximum, self.details = client, maximum, details

    def get(self, path, params=None):
        if self.details["request_count"] >= self.maximum:
            raise ApiError("Metric history exceeded max_pages; coverage is incomplete.")
        self.details["request_count"] += 1
        return self.client.get(path, params=params)


def _query(identity, key, window, settings):
    return {"resourceId": [identity], "statKey": [key], "begin": window["begin_ms"], "end": window["end_ms"],
            "rollUpType": settings["rollup_type"], "intervalType": settings["interval_type"],
            "intervalQuantifier": settings["interval_quantifier"], "dt": "false", "currentOnly": "false"}


def _series(payload, identity, key, window):
    if (not isinstance(payload, dict) or payload.get("error") or payload.get("errors")
            or payload.get("cursor") or payload.get("nextPage") or payload.get("pageInfo")):
        raise ApiError("Operations returned an invalid historical statistics envelope.")
    values = payload.get("values", [])
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values) or len(values) > 1:
        raise ApiError("Operations returned an invalid or repeated historical resource scope.")
    series = []
    for value in values:
        if ("resourceId" in value and value["resourceId"] != identity
                or not isinstance(value.get("stat-list", {}), dict)):
            raise ApiError("Operations returned historical statistics outside the selected resource scope.")
        stats = value.get("stat-list", {}).get("stat", [])
        if not isinstance(stats, list) or any(not isinstance(stat, dict) for stat in stats):
            raise ApiError("Operations returned an invalid historical statistics array.")
        series.extend(stats)
    if len(series) > 1:
        raise ApiError("Operations repeated a selected historical metric key.")
    if not series:
        return {"timestamps": [], "data": [], "reported_rollup_type": None, "reported_interval": None,
                "reported_series_unit": None}
    stat = series[0]
    if not isinstance(stat.get("statKey"), dict) or stat["statKey"].get("key") != key:
        raise ApiError("Operations returned an unexpected historical metric key.")
    timestamps, data = stat.get("timestamps"), stat.get("data", [])
    if (not isinstance(timestamps, list) or not isinstance(data, list) or len(timestamps) != len(data)
            or len(timestamps) > MAX_SAMPLES + 1
            or any(type(stamp) is not int or not window["begin_ms"] <= stamp <= window["end_ms"] for stamp in timestamps)
            or len(set(timestamps)) != len(timestamps)
            or any(not finite_number(number) for number in data)):
        raise ApiError("Operations returned malformed, repeated, out-of-window or excessive historical samples.")
    rollup, interval, unit = stat.get("rollUpType"), stat.get("intervalUnit"), stat.get("unit")
    if rollup is not None and (not isinstance(rollup, str) or rollup not in ROLLUPS | {"NONE", "LATEST"}):
        raise ApiError("Operations returned an invalid historical rollup type.")
    if interval is not None and (not isinstance(interval, dict) or not isinstance(interval.get("intervalType"), str)
                                 or interval["intervalType"] not in INTERVAL_TYPES
                                 or type(interval.get("quantifier")) is not int or interval["quantifier"] < 1):
        raise ApiError("Operations returned invalid historical interval metadata.")
    if unit is not None and (not isinstance(unit, str) or not unit.strip()):
        raise ApiError("Operations returned an invalid historical measurement unit.")
    samples = sorted(zip(timestamps, data))
    return {"timestamps": [item[0] for item in samples], "data": [item[1] for item in samples],
            "reported_rollup_type": rollup,
            "reported_interval": None if interval is None else {"intervalType": interval["intervalType"], "quantifier": interval["quantifier"]},
            "reported_series_unit": unit}


def collect_resource(client, resource, page_size=100, max_pages=1000):
    """Query each selected series and window, counting every metadata and metric GET."""
    if not supports(client.target.get("component"), resource):
        raise ValueError("Unsupported metric history resource.")
    validate_target(dict(client.target, resources=[resource]))
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("Metric history max_pages must be positive.")
    target, settings = client.target, client.target["metric_history"]
    windows = _windows(settings)
    if not isinstance(getattr(client, "collection_metadata", None), dict):
        client.collection_metadata = {}
    details = {"coverage": "incomplete", "strategy": "explicit_series_and_windows", "request_count": 0,
               "resource_ids": list(target["resource_ids"]), "stat_keys": list(target["stat_keys"]), "windows": windows,
               "requested_rollup_type": settings["rollup_type"], "requested_interval_type": settings["interval_type"],
               "requested_interval_quantifier": settings["interval_quantifier"]}
    client.collection_metadata[resource] = details
    budget, cache, records, sample_count = _Budget(client, max_pages, details), {}, [], 0
    for identity in target["resource_ids"]:
        resource_key, units = _unit_metadata(budget, identity, target["stat_keys"], cache)
        name = resource_key.get("name")
        if name is not None and not isinstance(name, str):
            raise ApiError("Operations returned an invalid historical resource name.")
        for key in target["stat_keys"]:
            for window in windows:
                payload = budget.get(RESOURCE_PATHS[COMPONENT][resource], params=_query(identity, key, window, settings))
                record = _series(payload, identity, key, window)
                sample_count += len(record["timestamps"])
                if sample_count > 1000000:
                    raise ApiError("Metric history exceeded its returned-sample budget; coverage is incomplete.")
                unit = units.get(key, {}).get("unit")
                if unit is not None and (not isinstance(unit, str) or not unit.strip()):
                    raise ApiError("Operations returned invalid historical measurement-unit metadata.")
                if record["reported_series_unit"] and unit is not None and record["reported_series_unit"] != unit:
                    raise ApiError("Operations returned conflicting historical measurement units.")
                # A COUNT rollup counts observations; its source metric's unit does not describe that count.
                sample_unit = None if settings["rollup_type"] == "COUNT" or record["reported_rollup_type"] == "COUNT" else unit
                record.update(resource_id=identity, resource_name=name, stat_key=key, unit=sample_unit, metric_unit=unit,
                              window_label=window["label"], begin_ms=window["begin_ms"], end_ms=window["end_ms"],
                              requested_rollup_type=settings["rollup_type"], requested_interval_type=settings["interval_type"],
                              requested_interval_quantifier=settings["interval_quantifier"],
                              availability="samples_returned" if record["timestamps"] else "no_samples_returned")
                records.append(record)
    details.update(coverage="complete", record_count=len(records))
    return records


def probe_request(target, resource):
    """Probe the first selected series within the actual explicit window."""
    if not supports(target.get("component"), resource):
        return None
    validate_target(dict(target, resources=[resource]))
    settings = target["metric_history"]
    return ("GET", RESOURCE_PATHS[COMPONENT][resource],
            _query(target["resource_ids"][0], target["stat_keys"][0], _windows(settings)[0], settings), None,
            "First selected resource, metric key and bounded time window only; unit metadata and full coverage are not established.")
