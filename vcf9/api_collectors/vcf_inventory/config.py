"""Configuration validation. Author: Paul Bryant."""

import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit
from .products import PRODUCT_MODULES, module_for

COMPONENTS = {"sddc_manager", "vcenter", "nsx"} | set(PRODUCT_MODULES)
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
}


class ConfigError(ValueError):
    """An invalid configuration or selection."""


def _integer(value, key, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ConfigError(f"{key} must be an integer from {minimum} to {maximum}.")


def load_config(path):
    """Validate structure without reading secrets or contacting endpoints."""
    from .collectors import RESOURCE_PATHS

    path = Path(path).resolve()
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("Cannot read configuration as UTF-8 JSON.") from exc
    if not isinstance(config, dict):
        raise ConfigError("Configuration must be a JSON object.")
    allowed = {"author", "timeout_seconds", "retries", "page_size", "max_pages", "targets"}
    if set(config) - allowed:
        raise ConfigError("Unknown top-level configuration field.")
    config.setdefault("timeout_seconds", 30)
    config.setdefault("retries", 2)
    config.setdefault("page_size", 100)
    config.setdefault("max_pages", 1000)
    timeout = config["timeout_seconds"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 600:
        raise ConfigError("timeout_seconds must be a finite number from 1 to 600.")
    _integer(config["retries"], "retries", 0, 5)
    _integer(config["page_size"], "page_size", 1, 1000)
    _integer(config["max_pages"], "max_pages", 1, 100000)
    targets = config.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ConfigError("targets must be a nonempty array.")
    seen = set()
    common_fields = {"name", "component", "url", "username_env", "password_env", "resources", "verify_tls", "version"}
    component_fields = {
        "sddc_manager": {"task_days", "certificate_attention_days", "domain_ids"}, "vcenter": {"filters"},
        "nsx": {"site_id", "enforcement_point_id", "domain_id", "policy_ids", "rule_ids"},
        "vsan": {"cluster_ids", "api_version", "token_env"},
        "vcf_fleet": {"token_env"},
        "hcx": {"auth_source", "token_env"},
        "vcf_operations": {"auth_source", "token_env", "token_scheme", "filters", "resource_ids", "stat_keys"},
        "vcf_automation": {"api_family", "token_env", "api_version", "org_id", "deployment_ids"},
        "live_site_recovery": {"auth_source", "token_env", "api_version", "pairing_id", "remote_username_env", "remote_password_env", "srm_ids", "group_ids"},
        "vsphere_replication": {"auth_source", "token_env", "api_version", "pairing_id", "remote_username_env", "remote_password_env", "source_vc_guid"},
    }
    for target in targets:
        if not isinstance(target, dict):
            raise ConfigError("Each target must be an object.")
        name = target.get("name", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
            raise ConfigError("Target names must contain 1-64 letters, digits, underscores or hyphens.")
        if name.upper() in RESERVED_NAMES or name.casefold() in seen:
            raise ConfigError("Target names must be unique and must not be reserved device names.")
        seen.add(name.casefold())
        component = target.get("component")
        if not isinstance(component, str) or component not in COMPONENTS:
            raise ConfigError(f"Target {name}: invalid component.")
        if set(target) - common_fields - component_fields[component]:
            raise ConfigError(f"Target {name}: unknown field or option for this component.")
        url = target.get("url")
        if not isinstance(url, str) or any(c.isspace() for c in url) or "\\" in url:
            raise ConfigError(f"Target {name}: url must be an HTTPS origin.")
        try:
            parts = urlsplit(url)
            valid_port = parts.port is None or 1 <= parts.port <= 65535
        except ValueError as exc:
            raise ConfigError(f"Target {name}: invalid URL or port.") from exc
        if (parts.scheme != "https" or not parts.hostname or not valid_port
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment):
            raise ConfigError(f"Target {name}: use https://hostname[:port] with no credentials or API path.")
        target["url"] = url.rstrip("/")
        credential_fields = ("username_env", "password_env", "token_env", "remote_username_env", "remote_password_env")
        for field in credential_fields:
            if field not in target:
                continue
            value = target[field]
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                raise ConfigError(f"Target {name}: {field} must name an environment variable.")
        if component in ("sddc_manager", "vcenter", "nsx") and not all(target.get(f) for f in ("username_env", "password_env")):
            raise ConfigError(f"Target {name}: username_env and password_env are required.")
        if component == "vcf_operations":
            has_token = bool(target.get("token_env"))
            has_credentials = any(target.get(f) for f in ("username_env", "password_env"))
            if (has_token and has_credentials) or (not has_token and not all(target.get(f) for f in ("username_env", "password_env"))):
                raise ConfigError(f"Target {name}: supply token_env or both username_env and password_env.")
        if component in ("vcf_automation", "vcf_fleet") and any(f in target for f in ("username_env", "password_env")):
            raise ConfigError(f"Target {name}: this component uses token_env authentication.")
        verify = target.setdefault("verify_tls", True)
        if verify is not True:
            if not isinstance(verify, str) or not verify:
                raise ConfigError(f"Target {name}: verify_tls must be true or a CA bundle file path.")
            ca_path = Path(verify)
            if not ca_path.is_absolute():
                ca_path = path.parent / ca_path
            if not ca_path.is_file():
                raise ConfigError(f"Target {name}: CA bundle file does not exist.")
            target["verify_tls"] = str(ca_path.resolve())
        resources = target.get("resources")
        if resources is not None:
            if (not isinstance(resources, list) or not resources
                    or any(not isinstance(r, str) or r not in RESOURCE_PATHS[component] for r in resources)
                    or len(resources) != len(set(resources))):
                raise ConfigError(f"Target {name}: resources must be a nonempty array of unique known names.")
        for field in ("site_id", "enforcement_point_id", "domain_id"):
            if field in target:
                value = target[field]
                if component != "nsx" or not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                    raise ConfigError(f"Target {name}: invalid NSX {field}.")
        if "version" in target and (not isinstance(target["version"], str) or len(target["version"]) > 100):
            raise ConfigError(f"Target {name}: version must be a string of at most 100 characters.")
        for field in ("auth_source", "api_family", "api_version", "org_id", "token_scheme"):
            if field in target and (not isinstance(target[field], str) or not target[field] or len(target[field]) > 200
                                    or any(ord(c) < 32 or ord(c) == 127 for c in target[field])):
                raise ConfigError(f"Target {name}: invalid {field}.")
        filters = target.get("filters", {})
        if not isinstance(filters, dict) or (filters and component not in ("vcenter", "vcf_operations")):
            raise ConfigError(f"Target {name}: filters are supported only for vCenter and VCF Operations.")
        for resource, params in filters.items():
            if resource not in RESOURCE_PATHS[component] or not isinstance(params, dict):
                raise ConfigError(f"Target {name}: invalid filter resource or query parameters.")
            for key, value in params.items():
                if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", key):
                    raise ConfigError(f"Target {name}: invalid filter parameter name.")
                values = value if isinstance(value, list) else [value]
                if not values or any(type(v) not in (str, int, float, bool) or (type(v) is float and not math.isfinite(v)) for v in values):
                    raise ConfigError(f"Target {name}: filter values must be scalar values or nonempty arrays.")
        from .operational import validate_target as validate_operational
        try:
            validate_operational(target)
            from . import assurance, activity, protection_evidence
            for supplemental in (assurance, activity, protection_evidence):
                supplemental.validate_target(target)
        except ValueError as exc:
            raise ConfigError(f"Target {name}: {exc}") from None
        product = module_for(component)
        if product is not None and hasattr(product, "validate_target"):
            try:
                product.validate_target(target)
            except ValueError as exc:
                raise ConfigError(f"Target {name}: {exc}") from None
    return config
