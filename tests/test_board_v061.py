"""Board regression tests: the real street plan and balanced_se.

The adopted board is rules_v072_cardo.json (V0.7.2, 2026-11-08): the
real palace plan. Cardo and decumanus cross at the center; the four
doors sit at their ends; six buildings hold one card each, the two
middle buildings pierced by the cardo lane."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import board  # noqa: E402
import engine  # noqa: E402
import policies  # noqa: E402


def load_board_rules():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return engine.load_rules(os.path.join(root, "rules_v072_cardo.json"))


class TestBoardFactsV072(unittest.TestCase):
    def test_counts(self):
        b = board.Board(load_board_rules())
        walkable = b.width * b.height - len(b.blocked)
        self.assertEqual((b.width, b.height), (19, 13))
        self.assertEqual(len(b.blocked), 140)
        self.assertEqual(walkable, 107)

    def test_six_buildings_cover_every_blocked_cell(self):
        # The blocked strips form eight cell groups, but the board
        # declares six buildings: the two middle ones are pierced by
        # the cardo lane, so their strips belong to one building.
        rules = load_board_rules()
        b = board.Board(rules)
        buildings = rules["board"]["buildings"]
        self.assertEqual(len(buildings), 6)
        self.assertEqual(len([x for x in buildings if x.get("pierced_by")]), 2)
        covered = set()
        for bld in buildings:
            for x in range(bld["x0"], bld["x1"] + 1):
                for y in range(bld["y0"], bld["y1"] + 1):
                    covered.add((x, y))
        lane = {(9, y) for y in range(1, 12) if y != 6}
        self.assertEqual(covered, set(b.blocked) | lane)

    def test_cardo_and_decumanus_run_end_to_end(self):
        b = board.Board(load_board_rules())
        for y in range(b.height):
            self.assertNotIn((9, y), b.blocked)
        for x in range(b.width):
            self.assertNotIn((x, 6), b.blocked)

    def test_doors_on_the_two_main_streets(self):
        # As in the real palace: north and south doors at the ends
        # of the cardo, east and west doors at the ends of the
        # decumanus. The Emperor keeps the south door; the retreat
        # hall is one step north on the cardo.
        b = board.Board(load_board_rules())
        self.assertEqual(b.gates["P0"], (9, 0))
        self.assertEqual(b.gates["P2"], (9, 12))
        self.assertEqual(b.gates["P1"], (18, 6))
        self.assertEqual(b.gates["P3"], (0, 6))
        for gate in b.gates.values():
            self.assertNotIn(gate, b.blocked)
        self.assertEqual(b.emperor, b.gates["P2"])
        self.assertEqual(b.retreat, (9, 11))
        self.assertEqual(b.distance(b.emperor, b.retreat), 1)

    def test_checkpoint_distances(self):
        # The checkpoint sits at the crossing. The board is a
        # rectangle, so north and south walk 6 and east and west 9.
        b = board.Board(load_board_rules())
        self.assertEqual(b.distance(b.gates["P0"], b.checkpoint), 6)
        self.assertEqual(b.distance(b.gates["P2"], b.checkpoint), 6)
        self.assertEqual(b.distance(b.gates["P1"], b.checkpoint), 9)
        self.assertEqual(b.distance(b.gates["P3"], b.checkpoint), 9)

    def test_entry_travel_sums_balance(self):
        # North and south gates hold the shorter card tour (60
        # versus 84); east and west hold the shorter checkpoint
        # walk. The tension trades off between the seat pairs.
        b = board.Board(load_board_rules())
        for p, expect in (("P0", 60), ("P1", 84), ("P2", 60), ("P3", 84)):
            total = sum(b.distance(b.gates[p], e)
                        for e in b.districts.values())
            self.assertEqual(total, expect, p)

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
