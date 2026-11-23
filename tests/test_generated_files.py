# ABOUTME: Guards the files that generators derive from the rules JSON: the
# ABOUTME: committed playtest pack and web bundle must equal a fresh build.
"""The committed generated files equal a fresh build.

`playtest/playtest-pack.html`, `web/board-data.js`, and `web/rules.js`
are written by generators from the rules JSON. A rules change that skips
a generator leaves a stale file that no other test sees, so this module
compares each committed file with a fresh build.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import engine  # noqa: E402
from tools import make_web_board  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "playtest" / "playtest-pack.html"


class GeneratedFilesAreCurrent(unittest.TestCase):
    def test_playtest_pack_matches_the_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "playtest-pack.html"
            run = subprocess.run(
                [sys.executable, "tools/make_print_pack.py", "--out", str(out)],
                cwd=REPO, check=True, capture_output=True, text=True)
            self.assertEqual(run.stderr, "")
            self.assertEqual(out.read_bytes(), PACK.read_bytes(),
                             "playtest/playtest-pack.html is stale; run "
                             "python3 tools/make_print_pack.py")

    def test_web_bundle_matches_the_generator(self):
        rules = engine.load_rules(str(REPO / make_web_board.RULES))
        generated, _data = make_web_board.generated(rules)
        self.assertEqual(sorted(generated),
                         ["web/board-data.js", "web/rules.js"])
        for path, text in generated.items():
            with self.subTest(path=path):
                self.assertEqual((REPO / path).read_text(encoding="utf-8"), text,
                                 f"{path} is stale; run python3 tools/make_web_board.py")


if __name__ == "__main__":
    unittest.main()
