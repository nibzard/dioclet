"""V0.6.2 print-pack regression tests."""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPrintPack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pack-")
        cls.out = os.path.join(cls.tmp, "pack.html")
        res = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools/make_print_pack.py"),
             "--out", cls.out],
            capture_output=True, text=True, check=True)
        cls.html = open(cls.out, encoding="utf-8").read()
        assert res.returncode == 0

    def test_no_doubled_braces(self):
        # The V0.6.1 pack shipped CSS with literal {{ }} (review
        # finding 1); the generator must unescape them.
        self.assertNotIn("{{", self.html)
        self.assertNotIn("}}", self.html)

    def test_style_braces_balance(self):
        style = self.html.split("<style>")[1].split("</style>")[0]
        self.assertEqual(style.count("{"), style.count("}"))

    def test_four_tracker_sheets(self):
        # Review finding 3: equipment ownership must be trackable.
        self.assertEqual(self.html.count('class="tracker"'), 4)
        for item in ("pugio", "lorica segmentata"):
            self.assertIn(item, self.html)

    def test_pawn_fits_street_circle(self):
        # Review finding 2: board circles are ~8.5mm on an A4
        # landscape page; pawns must not exceed that.
        self.assertIn("width:7mm", self.html)
        self.assertIn("size: A4 landscape", self.html)

    def test_stationary_rule_stated(self):
        # Review finding 4: duels and guard posts require movement.
        flat = " ".join(self.html.split())
        self.assertIn("need a move of at least one space", flat)


class TestMirrorBatchDispatch(unittest.TestCase):
    def test_runs_non_tactical_policy(self):
        res = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools/mirror_batch.py"),
             "--rules", os.path.join(ROOT, "rules_v06_realboard_p3.json"),
             "--policy", "greedy", "--games", "3", "--seed-base", "9900",
             "--out", tempfile.mkdtemp(prefix="mb-")],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr[-500:])


if __name__ == "__main__":
    unittest.main()
