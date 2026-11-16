# ABOUTME: Board geometry regression tests for the six-block cardo map:
# ABOUTME: counts, main streets, gates, distances, and reachability.
"""Regression tests for six intact blocks and the two main axes."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import board  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_board_rules(name="rules_v073_sixblocks_cardo.json"):
    """The raw V0.7 map JSON, wrapped in the current palace-map shape.

    These files predate the rules schema, so the loader translates their
    seat-id gate keys to compass names and renames the districts and
    guard posts to the keys the board module reads (the history files
    still name the posts with the old word).
    """
    with open(os.path.join(ROOT, "experiments/rules", name),
              encoding="utf-8") as fh:
        raw = json.load(fh)["board"]
    raw["gates"] = dict(zip(("north", "east", "south", "west"),
                            (raw["gates"][pid] for pid in ("P0", "P1", "P2", "P3"))))
    raw["treasure_entries"] = raw.pop("districts")
    raw["guard_posts"] = raw.pop("glory_posts")
    return {"palace": {"map": raw}}


class TestBoardFactsV073(unittest.TestCase):
    def test_counts(self):
        b = board.Board(load_board_rules())
        walkable = b.width * b.height - len(b.blocked)
        self.assertEqual((b.width, b.height), (19, 13))
        self.assertEqual(len(b.blocked), 150)
        self.assertEqual(walkable, 97)

    def test_six_intact_blocks_with_one_card_each(self):
        rules = load_board_rules()
        board.validate_six_block_layout(rules)
        b = board.Board(rules)
        remaining = set(b.blocked)
        components = []
        while remaining:
            todo = [remaining.pop()]
            component = set(todo)
            for x, y in todo:
                for dx, dy in board.DIRECTIONS:
                    cell = (x + dx, y + dy)
                    if cell in remaining:
                        remaining.remove(cell)
                        component.add(cell)
                        todo.append(cell)
            components.append(component)
        self.assertEqual(len(components), 6)
        self.assertEqual(sorted(map(len, components)), [25] * 6)
        buildings = rules["palace"]["map"]["buildings"]
        self.assertEqual({bld["district"] for bld in buildings}, set("ABCDEF"))
        self.assertTrue(all(not bld.get("pierced_by") for bld in buildings))

    def test_old_eight_block_map_fails_the_layout_contract(self):
        rules = load_board_rules("rules_v072_cardo.json")
        with self.assertRaisesRegex(ValueError, "six intact blocks, found 8"):
            board.validate_six_block_layout(rules)

    def test_cardo_and_decumanus_run_end_to_end(self):
        b = board.Board(load_board_rules())
        for y in range(b.height):
            self.assertNotIn((6, y), b.blocked)
        for x in range(b.width):
            self.assertNotIn((x, 6), b.blocked)

    def test_doors_on_the_two_main_streets(self):
        # As in the real palace: north and south doors at the ends
        # of the cardo, east and west doors at the ends of the
        # decumanus.
        b = board.Board(load_board_rules())
        self.assertEqual(b.gates["P0"], (6, 0))
        self.assertEqual(b.gates["P2"], (6, 12))
        self.assertEqual(b.gates["P1"], (18, 6))
        self.assertEqual(b.gates["P3"], (0, 6))
        for gate in b.gates.values():
            self.assertNotIn(gate, b.blocked)

    def test_checkpoint_distances(self):
        # The cardo uses an existing street. The east gate is farther
        # from the crossing; balance must be measured on this layout.
        b = board.Board(load_board_rules())
        self.assertEqual(b.distance(b.gates["P0"], b.checkpoint), 6)
        self.assertEqual(b.distance(b.gates["P2"], b.checkpoint), 6)
        self.assertEqual(b.distance(b.gates["P1"], b.checkpoint), 12)
        self.assertEqual(b.distance(b.gates["P3"], b.checkpoint), 6)

    def test_entry_travel_sums(self):
        # Record actual geometry; this is not a claim of fair seats.
        b = board.Board(load_board_rules())
        for p, expect in (("P0", 66), ("P1", 90), ("P2", 66), ("P3", 90)):
            total = sum(b.distance(b.gates[p], e)
                        for e in b.districts.values())
            self.assertEqual(total, expect, p)

    def test_every_gate_reaches_every_street_cell(self):
        b = board.Board(load_board_rules())
        walkable = {(x, y) for x in range(b.width) for y in range(b.height)
                    if (x, y) not in b.blocked}
        for gate in b.gates.values():
            self.assertEqual(set(b.distances(gate)), walkable)

    def test_no_path_crosses_a_building(self):
        b = board.Board(load_board_rules())
        specials = (list(b.gates.values()) + list(b.districts.values())
                    + [b.checkpoint] + b.guard_posts)
        for a in specials:
            for c in specials:
                path = b.path(a, c)
                for cell in path:
                    self.assertNotIn(cell, b.blocked)


if __name__ == "__main__":
    unittest.main()
