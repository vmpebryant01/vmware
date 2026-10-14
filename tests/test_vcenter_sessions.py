"""Check that vCenter tokens are attached only during authentication.

Author: Paul Bryant
"""

import ast
from pathlib import Path
import unittest


PYTHON_DIR = Path(__file__).parents[1] / "vsphere" / "python"


def sets_session_header(node):
    if not isinstance(node, ast.Assign):
        return False
    for target in node.targets:
        if not isinstance(target, ast.Subscript):
            continue
        if not isinstance(target.value, ast.Attribute):
            continue
        if target.value.attr != "headers":
            continue
        if not isinstance(target.value.value, ast.Name) or target.value.value.id != "session":
            continue
        if isinstance(target.slice, ast.Constant) and target.slice.value == "vmware-api-session-id":
            return True
    return False


class VcenterSessionTests(unittest.TestCase):
    def test_only_authentication_sets_session_header(self):
        checked = 0
        for path in PYTHON_DIR.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
                assignments = [node for node in ast.walk(function) if sets_session_header(node)]
                if function.name == "get_session":
                    self.assertEqual(len(assignments), 1, f"{path.name} authentication")
                    checked += 1
                else:
                    self.assertEqual(assignments, [], f"{path.name}:{function.name}")
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
