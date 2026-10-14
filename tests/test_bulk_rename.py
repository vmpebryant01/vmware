"""Tests for VM rename scope and collision checks.

Author: Paul Bryant
"""

import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "vsphere" / "python" / "bulk_rename_vms.py"
SPEC = importlib.util.spec_from_file_location("bulk_rename_vms", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BulkRenameTests(unittest.TestCase):
    def test_duplicate_target_is_rejected(self):
        sample = "old_name,new_name\nvm-a,new\nvm-b,new\n"
        with patch("builtins.open", return_value=StringIO(sample)):
            with self.assertRaises(ValueError):
                MODULE.read_renames("unused.csv")

    def test_existing_target_and_ambiguous_source_are_rejected(self):
        vms = [SimpleNamespace(name="vm-a"), SimpleNamespace(name="vm-b")]
        with self.assertRaises(ValueError):
            MODULE.resolve_renames(vms, [("vm-a", "vm-b")])
        with self.assertRaises(ValueError):
            MODULE.resolve_renames(vms + [SimpleNamespace(name="vm-a")], [("vm-a", "new")])


if __name__ == "__main__":
    unittest.main()
