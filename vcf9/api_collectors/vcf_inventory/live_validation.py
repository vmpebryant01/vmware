"""Bounded live collector contracts and value-free fixtures. Author: Paul Bryant."""

import argparse
import csv
import io
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, load_config
from .exports import write_json
from .http_client import ApiError, HttpClient
from .preflight import _failure
from .version_probes import probe_version


# Only literal schema names are retained. Unknown object keys can be identifiers,
# addresses, metric names, or user text, so their spelling is never exported.
_SCHEMA_FIELDS = frozenset("""
value values elements results result_count cursor pageMetadata pageNumber pageSize
totalElements totalPages pageInfo page totalCount count total records items content
id identifier uuid name version build node_version product_version major minor
minorMinor patch buildNumber resource resourceList resourceId resourceIdentifier
resourceKey adapterKindKey resourceKindKey stat stat-list statList stat-key statKey
timestamps data unit units intervalType intervalQuantifier rollUpType status state
config_status kubernetes_status conditions type severity reason messages message
start_time end_time scan_time scan_commit current target base_image addon components
hosts cluster host vm datacenter datastore network capacity free used cpu memory
power_state connection_state enabled servers mode hostname port protocol health
backup_jobs backup_schedules role_id privileges permissions roles marker iterate
next next_page links link rel href timestamp collectionTime response
""".split())


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def response_shape(value, max_nodes=500, max_depth=8):
    """Describe observed JSON types without retaining scalar values or dynamic keys.

    Arrays are sampled, not replayed. The result is a structural test fixture,
    not a replacement response suitable for inventory or semantic testing.
    """
    remaining = [max_nodes]

    def visit(item, depth):
        if remaining[0] <= 0 or depth > max_depth:
            return {"kind": "omitted"}
        remaining[0] -= 1
        if item is None:
            return {"kind": "null"}
        if type(item) is bool:
            return {"kind": "boolean"}
        if type(item) is int:
            return {"kind": "integer"}
        if type(item) is float:
            return {"kind": "number"}
        if isinstance(item, str):
            return {"kind": "string"}
        if isinstance(item, list):
            return {"kind": "array", "observed_length": len(item),
                    "samples": [visit(child, depth + 1) for child in item[:3]],
                    "sampled": len(item) > 3}
        if isinstance(item, dict):
            fields = {key: visit(child, depth + 1) for key, child in sorted(item.items())
                      if key in _SCHEMA_FIELDS and remaining[0] > 0}
            dynamic = [child for key, child in item.items() if key not in _SCHEMA_FIELDS]
            return {"kind": "object", "fields": fields,
                    "other_field_count": len(dynamic),
                    "other_field_samples": [visit(child, depth + 1) for child in dynamic[:2]],
                    "sampled": len(dynamic) > 2 or remaining[0] <= 0}
        return {"kind": "unrecognized"}

    return visit(value, 0)


def shape_matches(value, fixture):
    """Check captured field types without requiring original values or array sizes.

    Omitted branches and unknown-key samples are not constraints. This is a
    deliberately partial assertion, alongside each collector's semantic checks.
    """
    kind = fixture.get("kind")
    checks = {"null": value is None, "boolean": type(value) is bool,
              "integer": type(value) is int, "number": type(value) in (int, float),
              "string": isinstance(value, str), "array": isinstance(value, list),
              "object": isinstance(value, dict), "omitted": True}
    if not checks.get(kind, False):
        return False
    if kind == "object":
        return all(key in value and shape_matches(value[key], expected)
                   for key, expected in fixture.get("fields", {}).items())
    if kind == "array":
        samples = fixture.get("samples", [])
        # An empty observation cannot establish an item schema.
        return not samples or all(any(shape_matches(item, sample) for sample in samples) for item in value[:3])
    return True


def _is_session_request(component, method, path):
    if (component, method, path) in {
            ("sddc_manager", "POST", "/v1/tokens"),
            ("vcenter", "POST", "/api/session"), ("vcenter", "DELETE", "/api/session")}:
        return True
    from .products import module_for
    product = module_for(component)
    return product is not None and (
        (component, method, path) in product.ALLOWED_OPERATIONS
        or (hasattr(product, "allow_request") and product.allow_request(component, method, path)))


def run_live_validation(targets, config, *, max_requests=25, max_pages=3,
                        capture_fixtures=False, client_factory=HttpClient):
    """Exercise explicit resources using the real collectors within hard budgets.

    Retries are disabled. Session cleanup has a separate four-call allowance so
    an exhausted inventory budget does not prevent closing an owned session.
    No target addresses, configured names, credentials, bodies, or raw errors
    are written to the result. Target aliases follow selected configuration order.
    """
    from .collectors import collect_resource

    if type(max_requests) is not int or not 2 <= max_requests <= 1000:
        raise ValueError("max_requests must be an integer from 2 to 1000.")
    if type(max_pages) is not int or not 1 <= max_pages <= 1000:
        raise ValueError("max_pages must be an integer from 1 to 1000.")
    if not targets or any(not isinstance(t.get("resources"), list) or not t["resources"] for t in targets):
        raise ValueError("Live validation requires explicit nonempty resources for every selected target.")
    report = {"author": "Paul Bryant", "schema_version": "1.0", "started_at": _utc_now(),
              "status": "success", "targets": [], "fixtures": [],
              "limits": {"requests_per_target": max_requests, "max_pages": max_pages,
                         "http_retries": 0, "cleanup_calls_per_target": 4},
              "limitations": [
                  "Results cover the selected account-visible resources at the observed build and time only.",
                  "Collector contract validation is not vendor certification or blanket release compatibility.",
                  "Structural fixtures remove all scalar values and unknown key names; array samples are bounded.",
                  "Shape fixtures cannot reproduce real values, semantic failures, or complete pagination sequences."]}
    for index, target in enumerate(targets, 1):
        alias = f"target_{index:03d}"
        row = {"target_alias": alias, "component": target["component"], "status": "success",
               "authentication": {"status": "not_checked"}, "version": {"status": "unknown"},
               "resources": []}
        report["targets"].append(row)
        client = None
        state = {"calls": 0, "cleanup_calls": 0, "cleanup": False, "resource": None,
                 "fixture_count": 0, "resource_calls": 0}
        try:
            client = client_factory(target, timeout=config.get("timeout_seconds", 30), retries=0)
            original = client.request

            def bounded_request(method, path, *args, **kwargs):
                if state["cleanup"]:
                    if state["cleanup_calls"] >= 4:
                        raise ApiError("Session cleanup request limit reached.", category="request_budget")
                    state["cleanup_calls"] += 1
                else:
                    if state["calls"] >= max_requests:
                        raise ApiError("Live validation request limit reached.", category="request_budget")
                    state["calls"] += 1
                result = original(method, path, *args, **kwargs)
                resource = state["resource"]
                # Session requests can occur while a read reauthenticates. They
                # must never become fixtures, even though their values are removed.
                auth_route = _is_session_request(target["component"], method, path)
                if resource is not None and not auth_route:
                    state["resource_calls"] += 1
                    if capture_fixtures and state["fixture_count"] < 3:
                        payload = result[0] if kwargs.get("include_headers") else result
                        report["fixtures"].append({"author": "Paul Bryant", "target_alias": alias,
                                                   "component": target["component"], "resource": resource,
                                                   "sample_number": state["fixture_count"] + 1,
                                                   "shape": response_shape(payload)})
                        state["fixture_count"] += 1
                return result

            client.request = bounded_request
            client.authenticate()
            row["authentication"] = {"status": "configured"}
            component = target["component"]
            row["version"] = probe_version(client, target, numeric_only=True)
            for resource in target["resources"]:
                state.update(resource=resource, fixture_count=0, resource_calls=0)
                observation = {"resource": resource, "status": "not_checked"}
                row["resources"].append(observation)
                try:
                    records = collect_resource(client, resource, page_size=config.get("page_size", 100), max_pages=max_pages)
                    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
                        raise ApiError("Collector did not return its expected record structure.")
                    metadata = getattr(client, "collection_metadata", {})
                    details = metadata.get(resource) if isinstance(metadata, dict) else None
                    if isinstance(details, dict) and details.get("coverage") not in (None, "complete"):
                        raise ApiError("Collector returned an explicitly incomplete resource.")
                    if state["resource_calls"] == 0:
                        raise ApiError("No protected inventory response was observed.")
                    observation.update(status="contract_validated", observed_record_count=len(records),
                                       scope="configured_account_visible_resource")
                    row["authentication"]["status"] = "verified_for_selected_reads"
                except ApiError as exc:
                    observation.update(_safe_failure(exc))
                observation["observed_response_count"] = state["resource_calls"]
                state["resource"] = None
        except ApiError as exc:
            row["authentication"] = _safe_failure(exc)
        finally:
            if client is not None:
                state.update(cleanup=True, resource=None)
                try:
                    client.close()
                    row["session_cleanup"] = {"status": "success"}
                except ApiError as exc:
                    row["session_cleanup"] = _safe_failure(exc)
            row["request_count"] = state["calls"]
            row["cleanup_request_count"] = state["cleanup_calls"]
        if (row["version"]["status"] != "reported"
                or len(row["resources"]) != len(target["resources"])
                or any(item["status"] != "contract_validated" for item in row["resources"])
                or row.get("session_cleanup", {}).get("status") != "success"):
            row["status"] = report["status"] = "partial"
    report["completed_at"] = _utc_now()
    return report


def _safe_failure(exc):
    if getattr(exc, "category", None) == "request_budget":
        return {"status": "request_budget_exhausted"}
    return _failure(exc)


def matrix_csv(report):
    """Write observed-build evidence, without treating failures as incompatibility."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("author", "observed_at", "target_alias", "component", "version_status",
                     "version_scope", "server_api_version", "numeric_version_fields", "resource", "contract_status"))
    for target in report["targets"]:
        version = target["version"]
        fields = "; ".join(f"{key}={value}" for key, value in sorted(version.get("fields", {}).items()))
        for resource in target["resources"] or [{"resource": "", "status": "not_checked"}]:
            writer.writerow(("Paul Bryant", report["completed_at"], target["target_alias"], target["component"],
                             version["status"], version.get("scope", "unknown"), version.get("server_api_version", ""),
                             fields, resource["resource"], resource["status"]))
    return stream.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate explicit live collector contracts with bounded read requests.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--target", action="append", default=[], help="Select configured target names; repeatable")
    parser.add_argument("--output", type=Path, default=Path("validation"), help="Parent directory for a new result directory")
    parser.add_argument("--max-requests", type=int, default=25, help="Per-target requests, including authentication and version; default 25")
    parser.add_argument("--max-pages", type=int, default=3, help="Collector page or logical-query limit; default 3")
    parser.add_argument("--capture-fixtures", action="store_true", help="Write value-free structural response fixtures")
    parser.add_argument("--validate-config", action="store_true", help="Validate selection and limits without network access")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if set(args.target) - {target["name"] for target in config["targets"]}:
            raise ValueError("A selected target is absent from the configuration.")
        targets = [target for target in config["targets"] if not args.target or target["name"] in args.target]
        if not 2 <= args.max_requests <= 1000 or not 1 <= args.max_pages <= 1000:
            raise ValueError("Use max-requests 2-1000 and max-pages 1-1000.")
        if any(not target.get("resources") for target in targets):
            raise ValueError("Specify resources explicitly for every selected target.")
        if args.validate_config:
            print(f"Live validation configuration valid: {len(targets)} target(s). No network requests made.")
            return 0
        destination = args.output.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
        destination.mkdir(parents=True, exist_ok=False)
        report = run_live_validation(targets, config, max_requests=args.max_requests, max_pages=args.max_pages,
                                     capture_fixtures=args.capture_fixtures)
        fixtures = report.pop("fixtures")
        if args.capture_fixtures:
            write_json(destination / "structural_fixtures.json", {"author": "Paul Bryant", "schema_version": "1.0", "fixtures": fixtures})
        write_json(destination / "validation.json", report)
        (destination / "tested_versions.csv").write_text(matrix_csv(report), encoding="utf-8-sig", newline="")
        print(f"Validation results: {destination}")
        return 0 if report["status"] == "success" else 2
    except (ConfigError, ValueError) as exc:
        print(f"Cannot validate live APIs: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("Cannot read configuration or write validation results.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Live validation interrupted; results may be incomplete.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
