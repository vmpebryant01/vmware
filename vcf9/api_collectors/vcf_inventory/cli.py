"""Command-line inventory collection. Author: Paul Bryant."""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .collectors import RESOURCE_PATHS, collect_resource, resources_for
from .config import ConfigError, load_config
from .exports import write_json, write_resource
from .http_client import ApiError, HttpClient


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def collection_details(client, resource):
    metadata = getattr(client, "collection_metadata", {})
    return metadata.get(resource) if isinstance(metadata, dict) else None


def parser():
    result = argparse.ArgumentParser(description="Collect read-only VMware Cloud Foundation component inventory.")
    result.add_argument("--config", type=Path, help="JSON configuration file")
    result.add_argument("--output", type=Path, default=Path("inventory"), help="Parent directory for a new run")
    result.add_argument("--component", choices=sorted(RESOURCE_PATHS), help="Collect only this component")
    result.add_argument("--target", action="append", default=[], help="Collect only this named target; repeatable")
    result.add_argument("--csv", action="store_true", help="Write flattened CSV files alongside JSON")
    result.add_argument("--list-resources", action="store_true", help="Print resource names and API paths; no network")
    result.add_argument("--validate-config", action="store_true", help="Validate configuration structure; no network or secrets")
    result.add_argument("--preflight", action="store_true", help="Probe selected APIs and permissions without collecting full inventories")
    return result


def main(argv=None, component_scope=None):
    args = parser().parse_args(argv)
    if args.list_resources:
        selected_paths = {component: paths for component, paths in RESOURCE_PATHS.items()
                          if (not component_scope or component in component_scope)
                          and (not args.component or component == args.component)}
        print(json.dumps(selected_paths, indent=2))
        return 0
    active_client = None
    try:
        if not args.config:
            raise ConfigError("Provide --config, or use --list-resources.")
        if component_scope and args.component and args.component not in component_scope:
            raise ConfigError("The selected component is outside this script's product scope.")
        config = load_config(args.config)
        known_names = {target["name"] for target in config["targets"]}
        if set(args.target) - known_names:
            raise ConfigError("A selected target is not present in the configuration.")
        targets = [target for target in config["targets"]
                   if (not args.component or target["component"] == args.component)
                   and (not component_scope or target["component"] in component_scope)
                   and (not args.target or target["name"] in args.target)]
        if not targets:
            raise ConfigError("The selected component/target combination matches no targets.")
        if args.validate_config:
            print(f"Configuration valid: {len(targets)} selected target(s). No network requests made.")
            return 0
        run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        run_directory = args.output.resolve() / run_name
        run_directory.mkdir(parents=True, exist_ok=False)
        if args.preflight:
            from .preflight import run_preflight
            report = run_preflight(targets, config)
            write_json(run_directory / "preflight.json", report)
            print(f"Preflight: {run_directory / 'preflight.json'}")
            return 0 if report["status"] == "success" else 2
        summary = {"author": "Paul Bryant", "schema_version": "2.0", "started_at": utc_now(),
                   "scope": "Resources visible to each configured account and within configured API scopes.",
                   "targets": [], "status": "running"}
        failed = False
        write_json(run_directory / "summary.json", summary)
        for target in targets:
            target_summary = {"name": target["name"], "component": target["component"],
                              "endpoint": target["url"], "resources": [], "status": "running"}
            if target.get("version"):
                target_summary["configured_version"] = target["version"]
            summary["targets"].append(target_summary)
            client = None
            authenticated = False
            try:
                client = HttpClient(target, timeout=config["timeout_seconds"], retries=config["retries"])
                active_client = client
                client.authenticate()
                authenticated = True
            except ApiError as exc:
                target_summary["error"] = str(exc)
                failed = True
            resources = resources_for(target)
            for resource in resources:
                result = {"resource": resource, "started_at": utc_now()}
                target_summary["resources"].append(result)
                if not authenticated:
                    result.update(status="error", error="Collection unavailable because authentication or TLS setup failed.")
                    print(f"{target['name']}/{resource}: error", file=sys.stderr)
                else:
                    try:
                        records = collect_resource(client, resource, page_size=config["page_size"], max_pages=config["max_pages"])
                        metadata = {"schema_version": "2.0", "collected_at": utc_now(),
                                    "target": target["name"], "component": target["component"],
                                    "resource": resource, "endpoint": target["url"],
                                    "scope_filters": target.get("filters", {}).get(resource, {})}
                        if target["component"] == "nsx":
                            metadata["site_id"] = target.get("site_id", "default")
                            metadata["enforcement_point_id"] = target.get("enforcement_point_id", "default")
                            metadata["domain_id"] = target.get("domain_id", "default")
                        for option in ("api_family", "api_version", "org_id", "pairing_id", "source_vc_guid", "version",
                                       "domain_ids", "task_days", "certificate_attention_days", "policy_ids", "srm_ids", "resource_ids", "stat_keys",
                                       "group_ids", "rule_ids", "deployment_ids", "cluster_ids", "lifecycle_cluster_ids",
                                       "supervisor_ids", "namespace_ids", "metric_history"):
                            if option in target:
                                metadata[option] = target[option]
                        if resource == "failed_tasks":
                            metadata.setdefault("task_days", 30)
                        if resource == "certificates":
                            metadata.setdefault("certificate_attention_days", 60)
                        collection = collection_details(client, resource)
                        if collection is not None:
                            metadata["collection"] = collection
                        write_resource(run_directory / target["name"], resource, records, metadata, write_csv=args.csv)
                        result.update(status="success", record_count=len(records), file=f"{target['name']}/{resource}.json")
                        print(f"{target['name']}/{resource}: {len(records)} records")
                    except ApiError as exc:
                        result.update(status="error", error=str(exc))
                        failed = True
                        print(f"{target['name']}/{resource}: {exc}", file=sys.stderr)
                result["completed_at"] = utc_now()
                collection = collection_details(client, resource) if client else None
                if collection is not None:
                    result["collection"] = collection
                write_json(run_directory / "summary.json", summary)
            if client is not None:
                try:
                    client.close()
                except ApiError as exc:
                    target_summary["session_cleanup_error"] = str(exc)
                    failed = True
                finally:
                    active_client = None
            target_summary["status"] = "error" if ("error" in target_summary or "session_cleanup_error" in target_summary or any(
                r["status"] == "error" for r in target_summary["resources"])) else "success"
            write_json(run_directory / "summary.json", summary)
        summary["completed_at"] = utc_now()
        summary["status"] = "incomplete" if failed else "success"
        write_json(run_directory / "summary.json", summary)
        print(f"Results: {run_directory}")
        return 2 if failed else 0
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("File access failed. Check output permissions and available disk space.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Collection interrupted. Any running summary is incomplete.", file=sys.stderr)
        return 130
    finally:
        # Also close a vCenter session after a local write failure or interruption.
        if active_client is not None:
            try:
                active_client.close()
            except ApiError:
                print("Session cleanup failed after collection stopped.", file=sys.stderr)
