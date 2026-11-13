"""Checks for the V0.9.4 black-and-white A4 print-and-play kit.

The kit is generated art, so these tests pin the contract a family
relies on when they print it: page sizes and counts, board geometry
against the rules JSON, every symbol inside a printable area of at
least one tile, tracker counts, and the printed prose matching the
released V0.9 numbers.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader

import engine
from tools import make_a4_print_kit as kit

REPO = Path(__file__).resolve().parents[1]
PRINT = REPO / "print"
A4_SHORT_PT = 595.2756   # 210 mm
A4_LONG_PT = 841.8898    # 297 mm


def page_text(name, page_index):
    return PdfReader(PRINT / name).pages[page_index].extract_text()


def whole_text(name):
    # Wrapping changes with type size; assertions concern the printed words.
    return " ".join(" ".join(p.extract_text() for p in
                             PdfReader(PRINT / name).pages).split())


class BoardPages(unittest.TestCase):
    FILE = "dioclet-board-4xA4-BW.pdf"

    def test_four_a4_landscape_pages(self):
        reader = PdfReader(PRINT / self.FILE)
        self.assertEqual(len(reader.pages), 4)
        for page in reader.pages:
            self.assertAlmostEqual(float(page.mediabox.width), A4_LONG_PT, places=1)
            self.assertAlmostEqual(float(page.mediabox.height), A4_SHORT_PT, places=1)

    def test_every_sheet_carries_its_page_number(self):
        for index, expected in enumerate(("PAGE 1 OF 4", "PAGE 2 OF 4",
                                          "PAGE 3 OF 4", "PAGE 4 OF 4")):
            self.assertIn(expected, page_text(self.FILE, index))

    def test_gate_names_printed_on_the_board(self):
        text = whole_text(self.FILE)
        for name in kit.GATE_NAMES.values():
            for word in name.split(" - "):
                self.assertIn(word, text)

    def test_building_hatch_clip_uses_board_coordinates(self):
        # The northwest building's inset hatch rectangle must share the
        # point scale of its outline, rather than appearing near the origin.
        page = PdfReader(PRINT / self.FILE).pages[0]
        expected = (80.5 * kit.mm, 219.5 * kit.mm,
                    117.5 * kit.mm, 117.5 * kit.mm)
        rectangles = [tuple(float(v) for v in args)
                      for args, operator in page.get_contents().operations
                      if operator == b"re"]
        self.assertTrue(any(all(abs(a - b) < 0.001
                                for a, b in zip(rect, expected))
                            for rect in rectangles))


class DocumentPages(unittest.TestCase):
    FILES = {
        "dioclet-player-sheets-A4-BW.pdf": 2,
        "dioclet-cards-tokens-A4-BW.pdf": 3,
        "dioclet-rulebook-A4-BW.pdf": 7,
        "dioclet-quick-reference-A4-BW.pdf": 1,
        "dioclet-teaching-guide-A4-BW.pdf": 1,
        "dioclet-playtest-form-A4-BW.pdf": 2,
        "dioclet-print-instructions-A4-BW.pdf": 2,
    }

    def test_a4_portrait_page_counts(self):
        for name, count in self.FILES.items():
            reader = PdfReader(PRINT / name)
            self.assertEqual(len(reader.pages), count, name)
            for page in reader.pages:
                self.assertAlmostEqual(float(page.mediabox.width), A4_SHORT_PT,
                                       places=1, msg=name)
                self.assertAlmostEqual(float(page.mediabox.height), A4_LONG_PT,
                                       places=1, msg=name)

    def test_combined_kit_starts_with_the_five_board_pages(self):
        reader = PdfReader(PRINT / "dioclet-complete-print-kit-A4-BW.pdf")
        expected = 4 + 1 + sum(self.FILES.values())
        self.assertEqual(len(reader.pages), expected)
        for page in reader.pages[:5]:
            self.assertAlmostEqual(float(page.mediabox.width), A4_LONG_PT, places=1)

    def test_succession_map_is_one_landscape_page(self):
        reader = PdfReader(PRINT / "dioclet-succession-map-A4-BW.pdf")
        self.assertEqual(len(reader.pages), 1)
        page = reader.pages[0]
        self.assertAlmostEqual(float(page.mediabox.width), A4_LONG_PT, places=1)
        self.assertAlmostEqual(float(page.mediabox.height), A4_SHORT_PT, places=1)


class BoardMatchesRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = engine.load_rules(str(REPO / kit.RULES_FILE))
        cls.L = kit.build_layout(cls.rules)
        cls.board = cls.L["board"]
        cls.manifest = json.loads((PRINT / "kit-manifest.json").read_text())

    def test_counts(self):
        blocked = {tuple(cell) for cell in self.rules["board"]["blocked"]}
        spaces = {cell for cell, _ in self.L["spaces"]}
        self.assertEqual(len(spaces), 97)
        self.assertEqual(len(blocked), 150)
        self.assertEqual(len(self.rules["board"]["buildings"]), 6)
        # A cell is either walkable or blocked, never both.
        self.assertFalse(spaces & blocked)
        counts = self.manifest["counts"]
        self.assertEqual(counts["street_spaces"], 97)
        self.assertEqual(counts["blocked"], 150)
        self.assertEqual(counts["buildings"], 6)
        self.assertEqual(counts["gates"], len(self.board.gates))
        self.assertEqual(counts["districts"], len(self.board.districts))
        self.assertEqual(counts["glory_posts"], len(self.board.glory_posts))
        self.assertEqual(self.rules["gameplay_mode"], "succession-v1")

    def test_special_positions_match_rules(self):
        layout = self.manifest["layout"]
        for pid, cell in self.board.gates.items():
            self.assertEqual(layout["specials_mm"]["gates"][pid],
                             [round(v, 2) for v in self.L["pos"](tuple(cell))])
        self.assertEqual(layout["specials_mm"]["checkpoint"],
                         [round(v, 2) for v in self.L["pos"](tuple(self.board.checkpoint))])
        self.assertNotIn("factions", layout["specials_mm"])

    def test_tiles_are_a4_with_shared_overlap_on_each_cut(self):
        layout = self.manifest["layout"]
        cut_x, cut_y = layout["cut_lines_mm"]["x"], layout["cut_lines_mm"]["y"]
        overlap = layout["overlap_mm"]
        self.assertEqual(layout["page_mm"], [kit.PAGE_W, kit.PAGE_H])
        art = layout["art_bounds_mm"]
        # The four windows tile the art 2x2: each cut line sits in the
        # middle of the overlap band shared by two neighbouring pages.
        self.assertAlmostEqual(art[2] - art[0], 2 * kit.PAGE_W - overlap, places=3)
        self.assertAlmostEqual(art[3] - art[1], 2 * kit.PAGE_H - overlap, places=3)
        self.assertAlmostEqual(cut_x, art[0] + kit.PAGE_W - overlap / 2, places=3)
        self.assertAlmostEqual(cut_y, art[1] + kit.PAGE_H - overlap / 2, places=3)
        xs = {x0 for x0, y0, _ in layout["tiles"].values()}
        ys = {y0 for x0, y0, _ in layout["tiles"].values()}
        self.assertEqual(len(xs), 2)
        self.assertEqual(len(ys), 2)
        self.assertAlmostEqual(min(xs) + kit.PAGE_W - overlap, max(xs), places=3)
        self.assertAlmostEqual(min(ys) + kit.PAGE_H - overlap, max(ys), places=3)

    def test_cut_strokes_clear_the_print_margin_on_every_tile(self):
        # Include half the 0.5-point stroke, not only its centre.
        half_stroke = 0.25 / kit.mm
        for x0, y0, _ in self.L["tiles"].values():
            for coordinate, edge, extent in (
                    (self.L["cut"]["x"], x0, kit.PAGE_W),
                    (self.L["cut"]["y"], y0, kit.PAGE_H)):
                offset = coordinate - edge
                self.assertGreaterEqual(offset - half_stroke, kit.SAFE)
                self.assertLessEqual(offset + half_stroke, extent - kit.SAFE)

    def test_every_space_clears_the_safe_zone_on_some_tile(self):
        layout = self.manifest["layout"]
        safe = layout["safe_mm"]
        tiles = [(x0, y0) for x0, y0, _ in layout["tiles"].values()]
        specials = layout["specials_mm"]
        # (center, drawn radius) per symbol kind, matching draw_board().
        symbols = ([(tuple(v), 9.2) for v in layout["space_positions_mm"].values()]
                   + [(tuple(v), 11.4) for v in specials["gates"].values()]
                   + [(tuple(v), 10.6) for v in specials["districts"].values()]
                   + [(tuple(specials["checkpoint"]), 11.2)]
                   + [(tuple(v), 9.6) for v in specials["glory_posts"]])
        self.assertGreater(len(symbols), 100)
        for (px, py), radius in symbols:
            box = (px - radius, py - radius, px + radius, py + radius)
            self.assertTrue(any(
                box[0] - x0 >= safe and box[1] - y0 >= safe
                and box[2] - x0 <= kit.PAGE_W - safe
                and box[3] - y0 <= kit.PAGE_H - safe
                for x0, y0 in tiles),
                f"symbol at ({px},{py}) r{radius} has no tile with a printable copy")


class PrintedRulesMatchRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = engine.load_rules(str(REPO / kit.RULES_FILE))

    def test_guarded_values_still_match_the_rules(self):
        for (section, key), value in kit.PRINTED_RULES_VALUES.items():
            actual = self.rules[section].get(key)
            if actual is None and value == 0:
                actual = 0   # the engine reads absent cost keys as free
            self.assertEqual(actual, value,
                             f"{section}.{key} drifted from the printed prose")
        for key, value in kit.PRINTED_TOP_LEVEL.items():
            self.assertEqual(self.rules.get(key), value)
        abilities = self.rules["combat"].get("abilities")
        self.assertEqual(abilities,
                         {name: {"type": kind, "value": value}
                          for name, (kind, value) in kit.PRINTED_ABILITIES.items()})

    def test_refuse_to_build_guard_rejects_v081(self):
        # The V0.8.1 rules pay a first-claim reward and carry no ability
        # table; the guard must stop before printing the old game.
        import subprocess
        import sys as _sys
        result = subprocess.run(
            [_sys.executable, "tools/make_a4_print_kit.py",
             "--rules", "rules_v08_succession.json"],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("update the kit prose", result.stderr)

    def test_rulebook_pins_the_economy_numbers(self):
        text = whole_text("dioclet-rulebook-A4-BW.pdf")
        self.assertIn("mandatory fee of 1 Prestige", text)          # contest fee
        self.assertIn("hold at most 3 Prestige", text)              # glory cap
        self.assertIn("A 4, 5 or 6 earns 1 Prestige", text)         # guard post
        self.assertIn("round 24", text)                             # round limits
        self.assertIn("Two ordinary six-sided dice for movement", text)
        self.assertIn("on a tie the attacker wins", text)
        self.assertIn("Marcus wins; the claim dies", text)          # example
        self.assertIn("leaving him with 2", text)                   # example math

    def test_rulebook_pins_the_v092_mechanics(self):
        text = whole_text("dioclet-rulebook-A4-BW.pdf")
        self.assertIn("at most one item bonus", text)               # ability cap
        self.assertIn("never a sum", text)
        self.assertIn("two full rounds", text)                      # claim window
        self.assertIn("shame", text)                                # loser pays
        self.assertIn("pugio", text)                                # tie winner
        self.assertIn("face up at random", text)                    # start reveals
        self.assertNotIn("acclaimed emperor", text)                 # window replaced it

    def test_rulebook_pins_the_twin_board_flow(self):
        text = whole_text("dioclet-rulebook-A4-BW.pdf")
        self.assertIn("succession map", text)                       # the second board
        self.assertIn("Every pawn returns", text)                   # gate reset
        self.assertIn("to its gate on the succession map", text)
        self.assertIn("east side, on the east-west street", text)   # army meeting place
        self.assertIn("west side, on the east-west street", text)   # officials
        self.assertIn("north side, on the north-south street", text)  # elites
        self.assertIn("the only Prestige income there", text)       # duel-only income
        self.assertIn("Meeting places can only be visited during the "
                      "succession phase", text)
        self.assertIn("the palace map leaves the table", text)
        self.assertNotIn("You may gain support in either phase", text)

    def test_refuse_to_build_guard_rejects_v093_single_board(self):
        # V0.9.3 has no board_level2; the twin-board prose must not
        # print on top of a single-board ruleset.
        import subprocess
        import sys as _sys
        result = subprocess.run(
            [_sys.executable, "tools/make_a4_print_kit.py",
             "--rules", "rules_v093_succession.json"],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("update the kit prose", result.stderr)

    def test_no_boost_prose_survives_anywhere(self):
        # 0.9.3 removed the optional +2 duel boost; if it ever comes
        # back, the prose (and this check) must be rewritten on purpose.
        for name in ("dioclet-rulebook-A4-BW.pdf",
                     "dioclet-quick-reference-A4-BW.pdf",
                     "dioclet-teaching-guide-A4-BW.pdf",
                     "dioclet-player-sheets-A4-BW.pdf",
                     "dioclet-cards-tokens-A4-BW.pdf",
                     "dioclet-succession-map-A4-BW.pdf"):
            text = whole_text(name)
            self.assertNotIn("boost", text.lower(), name)
            self.assertNotIn("+2", text, name)

    def test_player_sheets_list_all_trackers(self):
        text = whole_text("dioclet-player-sheets-A4-BW.pdf")
        for item in self.rules["equipment"]:
            self.assertIn(item.upper().replace("_", " "), text.upper())
        self.assertIn("PRESTIGE (hold at most 3", text)
        for faction in ("Army", "Imperial officials", "City elites"):
            self.assertIn(faction, text)

    def test_cards_cover_the_six_items_and_identical_backs(self):
        fronts = page_text("dioclet-cards-tokens-A4-BW.pdf", 0)
        for item in self.rules["equipment"]:
            self.assertIn(item.replace("_", " ").upper(), fronts.upper())
        # Six backs, each the same two-line title (one string per line).
        backs = page_text("dioclet-cards-tokens-A4-BW.pdf", 1)
        self.assertEqual(backs.count("DIOCLETIAN'S"), 6)
        self.assertEqual(backs.count("PALACE"), 6)

    def test_tokens_page_matches_game_limits(self):
        tokens = page_text("dioclet-cards-tokens-A4-BW.pdf", 2)
        self.assertEqual(tokens.count("City phase (max 24 rounds):"), 1)
        self.assertEqual(tokens.count("Succession phase (max 24 rounds):"), 1)
        self.assertIn("PAWN", tokens.upper())  # fold-up pawns I-IV


class SuccessionMapMatchesRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = engine.load_rules(str(REPO / kit.RULES_FILE))
        cls.S = kit.build_succession_layout(cls.rules)
        cls.board = cls.S["board"]
        cls.manifest = json.loads((PRINT / "kit-manifest.json").read_text())

    def test_counts(self):
        blocked = {tuple(cell) for cell in self.rules["board_level2"]["blocked"]}
        spaces = {cell for cell, _ in self.S["spaces"]}
        self.assertEqual(len(spaces), 57)
        self.assertEqual(len(blocked), 60)
        self.assertFalse(spaces & blocked)
        counts = self.manifest["counts_level2"]
        self.assertEqual(counts["street_spaces"], 57)
        self.assertEqual(counts["blocked"], 60)
        self.assertEqual(counts["gates"], 4)
        self.assertEqual(counts["blocks"], 4)
        self.assertEqual(counts["glory_posts"], 0)

    def test_special_positions_match_rules(self):
        layout = self.manifest["layout"]["succession_map_mm"]
        specials = layout["specials_mm"]
        for pid, cell in self.board.gates.items():
            self.assertEqual(specials["gates"][pid],
                             [round(v, 2) for v in self.S["pos"](tuple(cell))])
        self.assertEqual(specials["checkpoint"],
                         [round(v, 2) for v in self.S["pos"](tuple(self.board.checkpoint))])
        for faction, cell in self.rules["succession"]["factions"].items():
            self.assertEqual(specials["factions"][faction],
                             [round(v, 2) for v in self.S["pos"](tuple(cell))])
        # Compass sanity: the gates sit where the prose says.
        self.assertEqual(self.board.gates["P0"], (6, 0))   # north
        self.assertEqual(self.board.gates["P1"], (12, 4))  # east
        self.assertEqual(self.board.gates["P2"], (6, 8))   # south
        self.assertEqual(self.board.gates["P3"], (0, 4))   # west

    def test_every_symbol_clears_the_page_border(self):
        # One page, no tiling: every symbol must fit inside the
        # decorative border in one printable copy.
        special = ({tuple(g) for g in self.board.gates.values()}
                   | {tuple(c) for c in self.rules["succession"]["factions"].values()}
                   | {tuple(self.board.checkpoint)})
        for cell, (x, y) in self.S["spaces"]:
            radius = 7.4 if tuple(cell) in special else 6.2
            self.assertGreaterEqual(x - radius, 12.0, f"cell {cell} clips the border")
            self.assertLessEqual(x + radius, kit.PAGE_W - 12.0, f"cell {cell}")
            self.assertGreaterEqual(y - radius, 9.0, f"cell {cell}")
            self.assertLessEqual(y + radius, kit.PAGE_H - 9.0, f"cell {cell}")

    def test_page_names_its_marks(self):
        text = whole_text("dioclet-succession-map-A4-BW.pdf")
        for word in ("THE SUCCESSION MAP", "ARMY", "OFFICIALS", "ELITES",
                     "PERISTYLE", "CITY BLOCK", "GOLDEN GATE", "SILVER GATE",
                     "BRONZE GATE", "IRON GATE", "faction meeting place",
                     "NO CUTTING NEEDED"):
            self.assertIn(word, text)

    def test_meeting_places_sit_one_per_street_arm(self):
        # The printed faction directions must match the rules cells:
        # elites north on the cardo, officials west and army east on
        # the full-width east-west street, none on the Peristyle.
        factions = self.rules["succession"]["factions"]
        self.assertEqual(factions["elites"], [6, 3])
        self.assertEqual(factions["officials"], [3, 4])
        self.assertEqual(factions["army"], [9, 4])
        for cell in factions.values():
            self.assertNotEqual(tuple(cell), tuple(self.board.checkpoint))


if __name__ == "__main__":
    unittest.main()
