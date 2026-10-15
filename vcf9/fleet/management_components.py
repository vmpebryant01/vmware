"""Export VCF management component deployment status. Author: Paul Bryant."""

from vcf9.report_core import execute, parser_for, require_dict


def collect(client, _args):
    path = "/v1/vcf-management-components"
    response = require_dict(client.request_json("GET", path), path)
    rows = []
    for component, details in response.items():
        if not isinstance(details, dict):
            continue
        base = {"component": component, "deploymentStatus": details.get("deploymentStatus"),
                "deploymentType": details.get("deploymentType")}
        component_rows = []
        if details.get("fqdn"):
            component_rows.append({**base, "endpoint": "appliance", "fqdn": details["fqdn"]})
        if details.get("loadBalancerFqdn"):
            component_rows.append({**base, "endpoint": "loadBalancer", "fqdn": details["loadBalancerFqdn"]})
        for node in details.get("nodes") or []:
            if isinstance(node, dict):
                component_rows.append({**base, "endpoint": node.get("type") or "node", "fqdn": node.get("fqdn")})
        if not component_rows:
            component_rows.append({**base, "endpoint": "", "fqdn": ""})
        rows.extend(component_rows)
    return rows


def main(argv=None):
    parser = parser_for(__doc__, "SDDC Manager")
    return execute(parser, "SDDC Manager", "management_components.csv",
                   ("component", "endpoint", "fqdn", "deploymentStatus", "deploymentType"), collect, argv)


if __name__ == "__main__":
    raise SystemExit(main())
