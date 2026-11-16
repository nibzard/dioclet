# ABOUTME: Real-board graph tests: blocked cells, street topology, and
# ABOUTME: the walkable-cell count of the V0.6 palace map.
"""Tests for the V0.6 real-board graph (blocked cells, street topology)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import board  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_v06():
    """The raw V0.6 map JSON, re-keyed into the current map shape.

    This file predates the rules schema, so its seat-id gate keys are
    translated to the compass names the board module reads.
    """
    with open(os.path.join(ROOT, "experiments/rules/rules_v06_realboard.json"),
              encoding="utf-8") as fh:
        raw = json.load(fh)["board"]
    raw["gates"] = dict(zip(("north", "east", "south", "west"),
                            (raw["gates"][pid] for pid in ("P0", "P1", "P2", "P3"))))
    return {"palace": {"map": raw}}


class TestBlockedCells(unittest.TestCase):
    def test_blocked_cells_are_never_reachable(self):
        rules = load_v06()
        b = board.Board(rules)
        dist = b.distances(b.gates["P0"])
        for cell in b.blocked:
            self.assertNotIn(cell, dist)

    def test_street_topology_distances(self):
        b = board.Board(load_v06())
        self.assertEqual(b.distance((0, 6), (18, 6)), 18)   # west to east gate
        self.assertEqual(b.distance((9, 0), (9, 12)), 12)   # north to south gate
        self.assertEqual(b.distance((0, 6), (9, 6)), 9)     # west gate to checkpoint
        self.assertEqual(b.distance((9, 0), (9, 6)), 6)     # north gate to checkpoint

    def test_walkable_count(self):
        b = board.Board(load_v06())
        dist = b.distances(b.gates["P0"])
        self.assertEqual(len(dist), b.width * b.height - len(b.blocked))


if __name__ == "__main__":
    unittest.main()
