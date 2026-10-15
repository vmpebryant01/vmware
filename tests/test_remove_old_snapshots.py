"""Tests for snapshot selection and the default preview guard.

Author: Paul Bryant
"""

from datetime import datetime, timedelta, timezone
import importlib.util
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest


SCRIPT = Path(__file__).parents[1] / "vsphere" / "python" / "remove_old_snapshots.py"
SPEC = importlib.util.spec_from_file_location("remove_old_snapshots", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SnapshotSelectionTests(unittest.TestCase):
    def test_nested_snapshots_are_selected_by_age(self):
        now = datetime.now(timezone.utc)
        old = SimpleNamespace(
            name="old",
            createTime=now - timedelta(days=40),
            childSnapshotList=[],
        )
        recent = SimpleNamespace(
            name="recent",
            createTime=now - timedelta(days=2),
            childSnapshotList=[old],
        )
        vm = SimpleNamespace(
            name="example-vm",
            snapshot=SimpleNamespace(rootSnapshotList=[recent]),
        )
        selected = MODULE.older_snapshots([vm], now - timedelta(days=30))
        self.assertEqual([(v.name, node.name) for v, node in selected], [("example-vm", "old")])

    def test_apply_requires_explicit_scope(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                MODULE.parse_args(["--days", "30", "--apply"])
        self.assertFalse(MODULE.parse_args(["--days", "30"]).apply)


if __name__ == "__main__":
    unittest.main()
