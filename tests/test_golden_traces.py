# ABOUTME: Golden-trace replay test: regenerates every recorded game from
# ABOUTME: its seed and demands the exact name-neutral trace back.
"""Safety net for the rules cleanup (docs/rules-cleanup-plan.md, Phase 0).

The fixture in tests/fixtures/golden/ records how 200 seeded games play
out today. This test replays the same seeds and compares the neutral
traces. If a later phase changes game behavior, the comparison fails.

Set GOLDEN_FAST=1 to check every fourth game only. The default run plays
all 200 games.
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (ROOT, os.path.join(ROOT, "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import make_golden_traces as golden  # noqa: E402

GOLDEN_DIR = os.path.join(ROOT, "tests", "fixtures", "golden")

TURN_KEYS = {"turn", "round", "phase", "player", "kind", "to", "target",
             "dice", "points", "positions", "items", "support", "claim"}
PHASES = {"palace", "succession"}
VERBS = set(golden.KIND_MAP.values())


def _load_meta():
    with open(os.path.join(GOLDEN_DIR, "meta.json"), "r",
              encoding="utf-8") as fh:
        return json.load(fh)


def _load_fixture():
    lines = []
    with open(os.path.join(GOLDEN_DIR, "traces.jsonl"), "r",
              encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                lines.append(json.loads(line))
    return lines


class GoldenTracesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = _load_meta()
        cls.fixture = _load_fixture()

    def test_fixture_shape(self):
        """The fixture holds every game, in order, in neutral words."""
        self.assertEqual(self.meta["games"], 200)
        self.assertEqual(len(self.fixture), 200)
        self.assertEqual([line["game"] for line in self.fixture],
                         list(range(self.meta["games"])))
        self.assertEqual([line["seed"] for line in self.fixture],
                         self.meta["seeds"])
        bots = {name for line in self.fixture for name in line["bots"]}
        self.assertGreaterEqual(len(bots), 3, "the fixture must mix bots")
        self.assertTrue(bots <= set(golden.BOT_POOL))
        for line in self.fixture:
            self.assertEqual(len(line["bots"]), 4)
            records = line["trace"]
            self.assertGreater(len(records), 1)
            self.assertEqual(records[-1]["kind"], "result")
            for record in records[:-1]:
                self.assertEqual(set(record), TURN_KEYS)
                self.assertIn(record["phase"], PHASES)
                self.assertIn(record["kind"], VERBS)
                self.assertEqual(len(record["points"]), 4)
                self.assertEqual(len(record["positions"]), 4)
                self.assertEqual(len(record["items"]), 4)

    def test_replay_matches_fixture(self):
        """Same seeds and bots must rebuild the same traces."""
        rules, _rules_name = golden.load_default_rules(ROOT)
        step = 4 if os.environ.get("GOLDEN_FAST") == "1" else 1
        by_index = {line["game"]: line for line in self.fixture}
        for index in range(0, self.meta["games"], step):
            expected = by_index[index]
            replayed = golden.build_game_line(rules, index,
                                              expected["seed"])
            if replayed != expected:
                self._fail_on_first_difference(expected, replayed)

    def _fail_on_first_difference(self, expected, replayed):
        """Fail with the first record that differs."""
        if replayed["bots"] != expected["bots"]:
            self.fail(f"game {expected['game']} seed {expected['seed']}: "
                      f"bots differ: {replayed['bots']} != "
                      f"{expected['bots']}")
        for pos, (want, got) in enumerate(zip(expected["trace"],
                                              replayed["trace"])):
            if want != got:
                self.fail(f"game {expected['game']} seed "
                          f"{expected['seed']}: trace record {pos} "
                          f"differs.\nfixture:  {want}\nreplayed: {got}")
        self.fail(f"game {expected['game']} seed {expected['seed']}: trace "
                  f"lengths differ: fixture {len(expected['trace'])}, "
                  f"replayed {len(replayed['trace'])}")


class WebParityBaselineTest(unittest.TestCase):
    def test_baseline_exists_with_summary(self):
        """The saved parity run reports matching Python and JavaScript."""
        path = os.path.join(GOLDEN_DIR, "web-parity-baseline.txt")
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        self.assertRegex(
            text,
            r"\d+ full action sequences and \d+ turns match between "
            r"Python and JavaScript\.")


if __name__ == "__main__":
    unittest.main()
