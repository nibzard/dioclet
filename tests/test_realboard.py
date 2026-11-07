"""Tests for the V0.6 real-board graph (blocked cells, street topology)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import board  # noqa: E402
import engine  # noqa: E402


def load_v06():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return engine.load_rules(os.path.join(root, "rules_v06_realboard.json"))


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
        self.assertEqual(b.distance(b.emperor, b.retreat), 1)

    def test_walkable_count(self):
        b = board.Board(load_v06())
        dist = b.distances(b.gates["P0"])
        self.assertEqual(len(dist), b.width * b.height - len(b.blocked))

    def test_blocked_gate_rejected(self):
        rules = engine.load_rules("rules_baseline.json")
        rules["board"]["blocked"] = [list(rules["board"]["gates"]["P0"])]
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(rules)

    def test_unreachable_site_rejected(self):
        rules = engine.load_rules("rules_baseline.json")
        # Wall district A at (1,1) off completely.
        rules["board"]["blocked"] = [[0, 1], [1, 0], [2, 1], [1, 2]]
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(rules)

    def test_v06_rules_pass_validation(self):
        engine.validate_rules(load_v06())


if __name__ == "__main__":
    unittest.main()
