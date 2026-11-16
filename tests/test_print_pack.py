# ABOUTME: Regression test for mirror_batch.py: a non-tactical --policy
# ABOUTME: must run to completion on the current succession rules.
"""Tool-dispatch regression tests.

The classic V0.6.1 print-pack class is gone: its rules files cannot load
under the succession validator, so the classic branch of
make_print_pack.py is unreachable. The succession print kit is covered
by test_print_kit.py.
"""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestMirrorBatchDispatch(unittest.TestCase):
    def test_runs_non_tactical_policy(self):
        res = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools/mirror_batch.py"),
             "--rules", os.path.join(ROOT, "experiments/rules/rules_v08_succession.json"),
             "--policy", "greedy", "--games", "3", "--seed-base", "9900",
             "--out", tempfile.mkdtemp(prefix="mb-")],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr[-500:])


if __name__ == "__main__":
    unittest.main()
