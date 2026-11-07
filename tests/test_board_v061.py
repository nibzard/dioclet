"""Board regression tests: six-block board facts and balanced_se.

The adopted board is rules_v071_realgates.json (V0.7.1, 2026-11-07):
the designer's six blocks, one card per block, streets on the
perimeter, two internal vertical streets, one central east-west
street, and every gate opening onto a street."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import board  # noqa: E402
import engine  # noqa: E402
import policies  # noqa: E402


def load_board_rules():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return engine.load_rules(os.path.join(root, "rules_v071_realgates.json"))


class TestBoardFactsV07(unittest.TestCase):
    def test_counts(self):
        b = board.Board(load_board_rules())
        walkable = b.width * b.height - len(b.blocked)
        self.assertEqual((b.width, b.height), (19, 13))
        self.assertEqual(len(b.blocked), 150)
        self.assertEqual(walkable, 97)

    def test_exactly_six_blocks(self):
        # The design rule: six blocks (3 columns by 2 rows), each
        # 5x5, one card per block. The V0.6 cardo split the middle
        # column into four strips; V0.7 removes it.
        b = board.Board(load_board_rules())
        seen, blocks = set(), []
        for cell in b.blocked:
            if cell in seen:
                continue
            group, queue = set(), [cell]
            while queue:
                cur = queue.pop()
                if cur in group:
                    continue
                group.add(cur)
                x, y = cur
                for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if n in b.blocked:
                        queue.append(n)
            seen |= group
            blocks.append(group)
        self.assertEqual(len(blocks), 6)
        for group in blocks:
            xs = [x for x, _ in group]
            ys = [y for _, y in group]
            self.assertEqual((max(xs) - min(xs) + 1,
                              max(ys) - min(ys) + 1), (5, 5))

    def test_every_gate_reaches_every_street_cell(self):
        b = board.Board(load_board_rules())
        walkable = {(x, y) for x in range(b.width) for y in range(b.height)
                    if (x, y) not in b.blocked}
        for gate in b.gates.values():
            self.assertEqual(set(b.distances(gate)), walkable)

    def test_seal_triangle_and_colocations(self):
        b = board.Board(load_board_rules())
        self.assertEqual(b.seal_sites["cellars"], b.districts["A"])
        self.assertEqual(b.seal_sites["guard_barracks"], b.districts["F"])
        self.assertEqual(b.seal_sites["peristyle"], b.checkpoint)
        self.assertEqual(b.emperor, b.gates["P2"])
        self.assertEqual(b.distance(b.emperor, b.retreat), 1)

    def test_checkpoint_distances(self):
        # Gates on the vertical streets (V0.7.1): every gate is
        # exactly 9 from the checkpoint.
        b = board.Board(load_board_rules())
        for gate in b.gates.values():
            self.assertEqual(b.distance(gate, b.checkpoint), 9)

    def test_gates_open_onto_streets(self):
        # As in the real palace: the north and south doors stand on
        # the internal vertical streets, the east and west doors on
        # the central east-west street. No gate faces a block wall.
        b = board.Board(load_board_rules())
        self.assertEqual(b.gates["P0"], (12, 0))
        self.assertEqual(b.gates["P2"], (6, 12))
        self.assertIn(b.gates["P0"][0], (6, 12))
        self.assertIn(b.gates["P2"][0], (6, 12))
        for p in ("P1", "P3"):
            self.assertEqual(b.gates[p][1], 6)
        for gate in b.gates.values():
            self.assertNotIn(gate, b.blocked)
        # The Emperor keeps the south gate; the retreat hall is one
        # step north on the same street.
        self.assertEqual(b.emperor, b.gates["P2"])
        self.assertEqual(b.retreat, (6, 11))
        self.assertEqual(b.distance(b.emperor, b.retreat), 1)

    def test_entry_travel_sums_balance(self):
        # The structural tension: north and south gates sit closer to
        # the cards (sum 66 each), east and west closer to the
        # checkpoint, and the cheapest two-seal tour costs the same
        # from every gate.
        b = board.Board(load_board_rules())
        for p, expect in (("P0", 66), ("P1", 90), ("P2", 66), ("P3", 90)):
            total = sum(b.distance(b.gates[p], e)
                        for e in b.districts.values())
            self.assertEqual(total, expect, p)

    def test_no_path_crosses_a_building(self):
        b = board.Board(load_board_rules())
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
        rules = load_board_rules()
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
