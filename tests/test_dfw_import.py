"""Tests for NSX firewall import validation.

Author: Paul Bryant
"""

import importlib.util
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = (
    Path(__file__).parents[1]
    / "nsx"
    / "python_complex"
    / "dfw_rules_production"
    / "create_nsxt_dfw_rules_from_csv.py"
)
SPEC = importlib.util.spec_from_file_location("create_nsxt_dfw_rules_from_csv", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FirewallImportTests(unittest.TestCase):
    def test_sample_uses_security_policy_paths_and_unique_order(self):
        plan = MODULE.read_plan(SCRIPT.with_name("dfw_rules_production.csv"))
        self.assertGreater(len(plan), 1)
        first = plan[0]["rules"][0]
        self.assertEqual(first["services"], ["/infra/services/HTTP", "/infra/services/HTTPS"])
        self.assertEqual(first["scope"], ["/infra/domains/default/groups/SG-Prod-WebApp"])
        self.assertEqual(
            [rule["sequence_number"] for rule in plan[0]["rules"]],
            list(range(10, 10 * (len(plan[0]["rules"]) + 1), 10)),
        )

    def test_invalid_action_rejected_before_api_use(self):
        bad_csv = (
            "Section,RuleName,Source,Destination,Service,Action,Direction,AppliedTo,Notes,Logging\n"
            "Prod,Rule A,ANY,ANY,ANY,PASS,IN_OUT,ANY,,TRUE\n"
        )
        with patch("builtins.open", return_value=StringIO(bad_csv)):
            with self.assertRaises(ValueError):
                MODULE.read_plan("unused.csv")


if __name__ == "__main__":
    unittest.main()
