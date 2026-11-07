"""V0.6.1 regression tests: board facts and the balanced_se variant."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import board  # noqa: E402
import engine  # noqa: E402
import policies  # noqa: E402


def load_p3():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return engine.load_rules(os.path.join(root, "rules_v06_realboard_p3.json"))


class TestBoardFactsV061(unittest.TestCase):
    def test_counts(self):
        b = board.Board(load_p3())
        walkable = b.width * b.height - len(b.blocked)
        self.assertEqual((b.width, b.height), (19, 13))
        self.assertEqual(len(b.blocked), 140)
        self.assertEqual(walkable, 107)

    def test_every_gate_reaches_every_street_cell(self):
        b = board.Board(load_p3())
        walkable = {(x, y) for x in range(b.width) for y in range(b.height)
                    if (x, y) not in b.blocked}
        for gate in b.gates.values():
            self.assertEqual(set(b.distances(gate)), walkable)

    def test_seal_triangle_and_colocations(self):
        b = board.Board(load_p3())
        self.assertEqual(b.seal_sites["cellars"], b.districts["A"])
        self.assertEqual(b.seal_sites["guard_barracks"], b.districts["F"])
        self.assertEqual(b.seal_sites["peristyle"], b.checkpoint)
        self.assertEqual(b.emperor, b.gates["P2"])
        self.assertEqual(b.distance(b.emperor, b.retreat), 1)

    def test_checkpoint_distances(self):
        b = board.Board(load_p3())
        self.assertEqual(b.distance(b.gates["P0"], b.checkpoint), 6)
        self.assertEqual(b.distance(b.gates["P2"], b.checkpoint), 6)
        self.assertEqual(b.distance(b.gates["P1"], b.checkpoint), 9)
        self.assertEqual(b.distance(b.gates["P3"], b.checkpoint), 9)

    def test_no_path_crosses_a_building(self):
        b = board.Board(load_p3())
        specials = (list(b.gates.values()) + list(b.districts.values())
                    + [b.checkpoint] + b.glory_posts + list(b.seal_sites.values())
                    + [b.emperor, b.retreat])
        for a in specials:
            for c in specials:
                path = b.path(a, c)
                for cell in path:
                    self.assertNotIn(cell, b.blocked)


class TestBalancedSeVariant(unittest.TestCase):
    def test_registered_and_versioned(self):
        self.assertIn("balanced_se", policies.POLICIES)
        self.assertEqual(policies.BALANCED_SE_VERSION, "balanced-se-v061.1")

    def test_plays_a_full_legal_game(self):
        rules = load_p3()
        pols = {p: "balanced_se" for p in ("P0", "P1", "P2", "P3")}
        state = engine.new_game(rules, 4242, "se_test", pols)
        import random
        prng = random.Random("se")
        guard = 0
        while not engine.is_finished(state):
            guard += 1
            self.assertLess(guard, 4000)
            obs = engine.observe(state, state["active_player"])
            aid, _ = policies.act("balanced_se", obs, prng)
            engine.apply_action(state, state["active_player"],
                                obs["turn_id"], aid, "se test")
        self.assertIn(state["status"], ("finished", "draw"))

    def test_original_policies_unchanged(self):
        self.assertEqual(
            sorted(set(policies.POLICIES) - {"balanced_se"}),
            ["aggressive", "balanced", "greedy", "random"])


if __name__ == "__main__":
    unittest.main()
