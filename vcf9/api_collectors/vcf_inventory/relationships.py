"""Build conservative relationships from saved inventories. Author: Paul Bryant."""

import argparse
import hashlib
import ipaddress
import itertools
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .exports import sanitize, write_json, write_resource
from .runs import RunError, identity_for, load_run


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}")
_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_DISPLAY_FIELDS = {"name", "displayname", "display_name", "resourcename"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Identity map contains a duplicate object key.")
        result[key] = value
    return result


def validate_identity_map(document):
    """Accept only explicit field namespaces; display names never establish identity."""
    if (not isinstance(document, dict) or "rules" not in document or set(document) - {"rules", "author"}
            or not isinstance(document["rules"], list)):
        raise ValueError("Identity map must contain a rules array and optional author.")
    if "author" in document and (not isinstance(document["author"], str) or not document["author"] or len(document["author"]) > 200):
        raise ValueError("Identity map author must be a nonempty bounded string.")
    rules = document["rules"]
    if len(rules) > 1000:
        raise ValueError("Identity map supports at most 1000 rules.")
    seen, normalizations = set(), {}
    for rule in rules:
        required = {"component", "resource", "field", "namespace", "normalization"}
        if not isinstance(rule, dict) or not required <= set(rule) or set(rule) - (required | {"target"}):
            raise ValueError("An identity rule has missing or unsupported fields.")
        for field in ("component", "resource", "namespace", "target"):
            if field in rule and (not isinstance(rule[field], str) or not _NAME.fullmatch(rule[field])):
                raise ValueError("Identity rule names must be bounded identifiers.")
        if (not isinstance(rule["field"], str) or len(rule["field"]) > 500
                or not _FIELD.fullmatch(rule["field"]) or rule["field"].split(".")[-1].lower() in _DISPLAY_FIELDS):
            raise ValueError("Identity rules require a dotted identifier field; display names cannot be matched.")
        if rule["normalization"] not in ("exact", "uuid", "hostname"):
            raise ValueError("Identity normalization must be exact, uuid, or hostname.")
        previous = normalizations.setdefault(rule["namespace"], rule["normalization"])
        if previous != rule["normalization"]:
            raise ValueError("Each identity namespace must use one normalization.")
        marker = json.dumps(rule, sort_keys=True)
        if marker in seen:
            raise ValueError("Identity map contains a repeated rule.")
        seen.add(marker)
    return [dict(rule) for rule in rules]


def load_identity_map(path):
    """Read a small JSON identity map without retaining its local filename."""
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
        if len(content) > 1024 * 1024:
            raise ValueError("Identity map exceeds its size limit.")
        document = json.loads(content, object_pairs_hook=_unique_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid JSON number.")))
    except (OSError, UnicodeError, ValueError):
        raise ValueError("Cannot read the identity map as a valid bounded UTF-8 JSON object.") from None
    return validate_identity_map(document)


def _hostname(value):
    if not isinstance(value, str) or not value or value != value.strip() or any(char.isspace() for char in value):
        return None
    value = value[:-1] if value.endswith(".") else value
    try:
        return ipaddress.ip_address(value).compressed.lower()
    except ValueError:
        pass
    try:
        value = value.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    if len(value) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in value.split(".")):
        return None
    return value


def endpoint_hostname(endpoint):
    """Normalize a configured HTTPS endpoint's hostname without DNS or network calls."""
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme.lower() != "https" or parsed.username or parsed.password or not parsed.hostname:
            return None
        return _hostname(parsed.hostname)
    except (AttributeError, TypeError, ValueError):
        return None


def _value(row, field):
    for key in field.split("."):
        if not isinstance(row, dict) or key not in row:
            return None
        row = row[key]
    return row


def _normalized(value, normalization):
    if type(value) not in (str, int) or value == "":
        return None
    text = str(value)
    if len(text) > 2000 or any(ord(char) < 32 or ord(char) == 127 for char in text):
        return None
    if normalization == "exact":
        return value
    if normalization == "hostname":
        return _hostname(text)
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError):
        return None


def _id(kind, *parts):
    payload = json.dumps([kind, *parts], ensure_ascii=True, separators=(",", ":"))
    return kind + ":" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_relationships(run, identity_rules=None):
    """Join only explicit API references and caller-declared identity namespaces."""
    rules = validate_identity_map({"rules": identity_rules or []})
    graph = {"author": "Paul Bryant", "schema_version": 1,
             "created_at": datetime.now(timezone.utc).isoformat(),
             "source_run_status": run["summary"].get("status"),
             "source_completed_at": run["summary"].get("completed_at"),
             "nodes": [], "edges": [], "ambiguous": [], "unresolved": [],
             "unavailable_resources": [dict(target=key[0], component=key[1], resource=key[2], reason=reason)
                                       for key, reason in sorted(run.get("unavailable", {}).items())]}
    nodes, entries, buckets, targets, edge_ids = {}, [], {}, {}, set()

    def unresolved(reason, **fields):
        graph["unresolved"].append(dict(reason=reason, **fields))

    def ambiguous(reason, **fields):
        graph["ambiguous"].append(dict(reason=reason, **fields))

    def edge(source, destination, relation, evidence):
        marker = _id("edge", source, destination, relation, evidence)
        if marker not in edge_ids:
            edge_ids.add(marker)
            graph["edges"].append({"id": marker, "source": source, "destination": destination,
                                   "relationship": relation, "evidence": evidence})

    for target in run["summary"]["targets"]:
        key = (target["name"], target["component"])
        hostname = endpoint_hostname(target["endpoint"])
        if key in targets:
            if targets[key]["hostname"] != hostname:
                raise ValueError("Run contains conflicting endpoint hostnames for a target.")
            continue
        identifier = _id("target", *key)
        targets[key] = {"id": identifier, "hostname": hostname}
        nodes[identifier] = {"id": identifier, "kind": "target", "target": key[0], "component": key[1],
                             "endpoint_hostname": hostname}
        if hostname is None:
            unresolved("invalid_target_endpoint", target=key[0], component=key[1])

    for key, document in sorted(run["resources"].items()):
        for ordinal, row in enumerate(document["records"]):
            identity = identity_for(key[1], key[2], row)
            if identity is None:
                unresolved("record_has_no_supported_identifier", target=key[0], component=key[1], resource=key[2], row=ordinal)
                continue
            identifier = _id("record", *key, list(identity))
            entry = {"id": identifier, "key": key, "identity": identity, "row": row}
            entries.append(entry)
            buckets.setdefault(identifier, []).append(entry)
    valid = []
    for identifier, candidates in buckets.items():
        first = candidates[0]
        key = first["key"]
        if len(candidates) != 1:
            ambiguous("duplicate_record_identifier", target=key[0], component=key[1], resource=key[2],
                      identity=list(first["identity"]), record_count=len(candidates))
            continue
        valid.append(first)
        nodes[identifier] = {"id": identifier, "kind": "record", "target": key[0], "component": key[1],
                             "resource": key[2], "identity": list(first["identity"]), "inventory_available": True}
    indexes = {}
    for entry in valid:
        indexes.setdefault(entry["key"], []).append(entry)

    for resource, field, component, relationship in (("vcenters", "fqdn", "vcenter", "managed_vcenter"),
                                                     ("nsx_clusters", "vipFqdn", "nsx", "managed_nsx")):
        source_groups = {}
        for entry in valid:
            if entry["key"][1:] == ("sddc_manager", resource):
                hostname = _hostname(_value(entry["row"], field))
                if hostname is None:
                    unresolved("missing_or_invalid_server_hostname", node=entry["id"], field=field)
                else:
                    source_groups.setdefault((entry["key"][0], hostname), []).append(entry)
        for (target_name, hostname), sources in source_groups.items():
            destinations = [value["id"] for key, value in targets.items() if key[1] == component and value["hostname"] == hostname]
            if len(sources) > 1 or len(destinations) > 1:
                ambiguous("server_hostname_is_not_unique", target=target_name, resource=resource, hostname=hostname,
                          sources=[entry["id"] for entry in sources], destinations=destinations)
            elif not destinations:
                unresolved("configured_target_hostname_not_found", node=sources[0]["id"], component=component, hostname=hostname)
            else:
                edge(sources[0]["id"], destinations[0], relationship, {"field": field, "match": "configured_endpoint_hostname"})

    for entry in valid:
        target, component, resource = entry["key"]
        if (component, resource) == ("sddc_manager", "clusters"):
            domain_id = _value(entry["row"], "domain.id")
            candidates = [other for other in indexes.get((target, component, "domains"), []) if other["row"].get("id") == domain_id]
            evidence = {"field": "domain.id", "match": "same_target_domain_id"}
            if not isinstance(domain_id, str) or not domain_id or not candidates:
                unresolved("domain_reference_not_found", node=entry["id"], field="domain.id")
            elif len(candidates) > 1:
                ambiguous("domain_reference_is_not_unique", node=entry["id"], candidates=[other["id"] for other in candidates])
            else:
                edge(entry["id"], candidates[0]["id"], "belongs_to_domain", evidence)

    # Server-returned Operations IDs establish references even when a resource
    # was outside the saved resources query. Such nodes are explicitly marked.
    def operations_node(target, identity):
        identifier = _id("record", target, "vcf_operations", "resources", [identity])
        if identifier in buckets and len(buckets[identifier]) > 1:
            return None
        if identifier not in nodes:
            nodes[identifier] = {"id": identifier, "kind": "record_reference", "target": target,
                                 "component": "vcf_operations", "resource": "resources", "identity": [identity],
                                 "inventory_available": False}
            unresolved("operations_resource_reference_not_collected", node=identifier)
        return identifier

    for entry in valid:
        target, component, resource = entry["key"]
        if (component, resource) != ("vcf_operations", "relationships"):
            continue
        row = entry["row"]
        source_id, related_id, relation = row.get("resource_id"), row.get("related_resource_id"), row.get("relationship_type")
        if not all(isinstance(value, str) and value for value in (source_id, related_id)) or relation not in ("PARENT", "CHILD"):
            unresolved("invalid_operations_relationship", node=entry["id"])
            continue
        source, destination = operations_node(target, source_id), operations_node(target, related_id)
        if source is None or destination is None:
            ambiguous("operations_reference_is_not_unique", node=entry["id"])
            continue
        edge(source, destination, "has_" + relation.lower(), {"relationship_node": entry["id"], "relationship_type": relation})

    mapped = {}
    for rule in rules:
        matched = False
        for entry in valid:
            target, component, resource = entry["key"]
            if (component, resource) != (rule["component"], rule["resource"]) or rule.get("target", target) != target:
                continue
            matched = True
            value = _normalized(_value(entry["row"], rule["field"]), rule["normalization"])
            if value is None:
                unresolved("identity_rule_field_missing_or_invalid", node=entry["id"], field=rule["field"], namespace=rule["namespace"])
                continue
            mapped.setdefault((rule["namespace"], value), {})[entry["id"]] = entry
        if not matched:
            unresolved("identity_rule_has_no_collected_records", component=rule["component"], resource=rule["resource"],
                       namespace=rule["namespace"], **({"target": rule["target"]} if "target" in rule else {}))
    for (namespace, value), matches in mapped.items():
        candidates = list(matches.values())
        by_target = {}
        for entry in candidates:
            by_target.setdefault(entry["key"][:2], []).append(entry)
        if any(len(group) > 1 for group in by_target.values()):
            ambiguous("identity_namespace_is_not_unique_within_target", namespace=namespace, identity=value,
                      candidates=sorted(matches))
            continue
        cross_product = [(left, right) for left, right in itertools.combinations(candidates, 2) if left["key"][1] != right["key"][1]]
        if not cross_product:
            for entry in candidates:
                unresolved("identity_namespace_has_no_cross_component_match", node=entry["id"], namespace=namespace, identity=value)
        for left, right in cross_product:
            source, destination = sorted((left["id"], right["id"]))
            edge(source, destination, "same_identity", {"namespace": namespace, "identity": value, "match": "explicit_identity_map"})
    graph["nodes"] = sorted(nodes.values(), key=lambda item: item["id"])
    graph["edges"].sort(key=lambda item: item["id"])
    return sanitize(graph)


def main(argv=None):
    """Command-line entry point using completed files only."""
    parser = argparse.ArgumentParser(description="Build explicit relationships from a completed inventory run without network access.")
    parser.add_argument("--run", required=True, type=Path, help="Completed inventory run directory")
    parser.add_argument("--output", required=True, type=Path, help="Relationship graph JSON file outside the run directory")
    parser.add_argument("--identity-map", type=Path, help="Optional explicit identity-namespace JSON rules")
    parser.add_argument("--csv", action="store_true", help="Also export graph collections as JSON and CSV tables")
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        if output.is_relative_to(args.run.resolve()):
            raise ValueError("Choose an output file outside the source run directory.")
        rules = load_identity_map(args.identity_map) if args.identity_map else None
        graph = build_relationships(load_run(args.run), rules)
        collections = ("nodes", "edges", "ambiguous", "unresolved", "unavailable_resources")
        if args.identity_map:
            outputs = {output}
            if args.csv:
                outputs.update(output.parent / (output.stem + "_" + collection + suffix)
                               for collection in collections for suffix in (".json", ".csv"))
            if args.identity_map.resolve() in outputs:
                raise ValueError("Output files must differ from the identity map.")
        if args.csv:
            metadata = {key: value for key, value in graph.items() if key not in collections}
            for collection in collections:
                write_resource(output.parent, output.stem + "_" + collection, graph[collection],
                               dict(metadata, resource="relationships_" + collection), write_csv=True)
        write_json(output, graph)
    except (RunError, OSError, ValueError):
        print("Cannot build the relationship graph. Check the completed run, identity rules, and output location.", file=sys.stderr)
        return 2
    print(f"Wrote relationship graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
          f"{len(graph['ambiguous'])} ambiguous groups, {len(graph['unresolved'])} unresolved references.")
    return 0
