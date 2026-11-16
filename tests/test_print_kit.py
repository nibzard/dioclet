"""Checks for the V0.10 black-and-white A4 print-and-play kit.

The kit is generated art, so these tests pin the contract a family
relies on when they print it: page sizes and counts, board geometry
against the rules JSON, every symbol inside a printable area of at
least one tile, tracker counts, and the printed prose matching the
released V0.9 numbers.
"""

import itertools
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
PRINT_BW = PRINT / "bw"     # the black-and-white edition
A4_SHORT_PT = 595.2756   # 210 mm
A4_LONG_PT = 841.8898    # 297 mm


def page_text(name, page_index):
    return PdfReader(PRINT_BW / name).pages[page_index].extract_text()


def whole_text(name):
    # Wrapping changes with type size; assertions concern the printed words.
    return " ".join(" ".join(p.extract_text() for p in
                             PdfReader(PRINT_BW / name).pages).split())


class BoardPages(unittest.TestCase):
    FILE = "imperial-rivals-305ad-board-4xA4-BW.pdf"

    def test_four_a4_landscape_pages(self):
        reader = PdfReader(PRINT_BW / self.FILE)
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
        page = PdfReader(PRINT_BW / self.FILE).pages[0]
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
        "imperial-rivals-305ad-player-sheets-A4-BW.pdf": 2,
        "imperial-rivals-305ad-cards-tokens-A4-BW.pdf": 5,
        "imperial-rivals-305ad-rulebook-A4-BW.pdf": 8,
        "imperial-rivals-305ad-quick-reference-A4-BW.pdf": 1,
        "imperial-rivals-305ad-teaching-guide-A4-BW.pdf": 1,
        "imperial-rivals-305ad-playtest-form-A4-BW.pdf": 2,
        "imperial-rivals-305ad-print-instructions-A4-BW.pdf": 2,
    }

    def test_a4_portrait_page_counts(self):
        for name, count in self.FILES.items():
            reader = PdfReader(PRINT_BW / name)
            self.assertEqual(len(reader.pages), count, name)
            for page in reader.pages:
                self.assertAlmostEqual(float(page.mediabox.width), A4_SHORT_PT,
                                       places=1, msg=name)
                self.assertAlmostEqual(float(page.mediabox.height), A4_LONG_PT,
                                       places=1, msg=name)

    def test_combined_kit_puts_the_pages_to_cut_last(self):
        # The rules first; the print instructions right before the
        # pages to cut (boards, then cards and tokens); no playtest form.
        reader = PdfReader(PRINT_BW / "imperial-rivals-305ad-complete-print-kit-A4-BW.pdf")
        form = self.FILES["imperial-rivals-305ad-playtest-form-A4-BW.pdf"]
        expected = 4 + 4 + sum(self.FILES.values()) - form
        self.assertEqual(len(reader.pages), expected)
        cards = self.FILES["imperial-rivals-305ad-cards-tokens-A4-BW.pdf"]
        first_board = expected - cards - 8
        landscape = [i for i, page in enumerate(reader.pages)
                     if float(page.mediabox.width) > float(page.mediabox.height)]
        self.assertEqual(landscape, list(range(first_board, first_board + 8)))
        texts = [reader.pages[i].extract_text() for i in range(expected)]
        self.assertIn("RULES", texts[0].upper())
        self.assertIn("PRINT AND ASSEMBLE", texts[first_board - 2])
        self.assertIn("PRINT AND ASSEMBLE", texts[first_board - 1])
        self.assertIn("TREASURE LOCATION CARDS", texts[expected - cards])
        self.assertIn("SUCCESSION MAP", texts[first_board + 7].upper())
        self.assertFalse(any("PLAYTEST RECORD" in t for t in texts))

    def test_succession_map_is_four_landscape_pages(self):
        reader = PdfReader(PRINT_BW / "imperial-rivals-305ad-succession-map-A4-BW.pdf")
        self.assertEqual(len(reader.pages), 4)
        for page in reader.pages:
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
        blocked = {tuple(cell) for cell in self.rules["palace"]["map"]["blocked"]}
        spaces = {cell for cell, _ in self.L["spaces"]}
        self.assertEqual(len(spaces), 97)
        self.assertEqual(len(blocked), 150)
        self.assertEqual(len(self.rules["palace"]["map"]["buildings"]), 6)
        # A cell is either walkable or blocked, never both.
        self.assertFalse(spaces & blocked)
        counts = self.manifest["counts"]
        self.assertEqual(counts["street_spaces"], 97)
        self.assertEqual(counts["blocked"], 150)
        self.assertEqual(counts["buildings"], 6)
        self.assertEqual(counts["gates"], len(self.board.gates))
        self.assertEqual(counts["districts"], len(self.board.districts))
        self.assertEqual(counts["guard_posts"], len(self.board.guard_posts))
        self.assertEqual(self.rules["game"]["rules_version"], "0.10.2")

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
                   + [(tuple(v), 9.6) for v in specials["guard_posts"]])
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
            self.assertEqual(self.rules[section][key], value,
                             f"{section}.{key} drifted from the printed prose")
        for (section, key), value in kit.PRINTED_TOP_LEVEL.items():
            self.assertEqual(self.rules[section][key], value)
        abilities = self.rules["treasures"]["abilities"]
        self.assertEqual(abilities,
                         {name: {"type": kind, "value": value}
                          for name, (kind, value) in kit.PRINTED_ABILITIES.items()})

    def test_refuse_to_build_guard_rejects_a_changed_fee(self):
        # Any drift from the printed numbers must stop the build before a
        # family prints prose that no longer matches the rules.
        import subprocess
        import sys as _sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / "rules.json"
            rules = json.loads((REPO / kit.RULES_FILE).read_text())
            rules["succession"]["contest_fee"] = 2
            mutated.write_text(json.dumps(rules))
            result = subprocess.run(
                [_sys.executable, "tools/make_a4_print_kit.py",
                 "--rules", str(mutated)],
                capture_output=True, text=True, cwd=str(REPO))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("update the kit prose", result.stderr)

    def test_rulebook_pins_the_economy_numbers(self):
        text = whole_text("imperial-rivals-305ad-rulebook-A4-BW.pdf")
        self.assertIn("mandatory fee of 1 Prestige", text)          # contest fee
        self.assertIn("hold at most 3 Prestige", text)              # prestige cap
        self.assertIn("A 4, 5 or 6 earns 1 Prestige", text)         # guard post
        self.assertIn("round 24", text)                             # round limits
        self.assertIn("Two ordinary six-sided dice for movement", text)
        self.assertIn("on a tie the attacker wins", text)
        self.assertIn("Marcus wins; the claim dies", text)          # example
        self.assertIn("leaving him with 2", text)                   # example math

    def test_rulebook_pins_the_v092_mechanics(self):
        text = whole_text("imperial-rivals-305ad-rulebook-A4-BW.pdf")
        self.assertIn("at most one item bonus", text)               # ability cap
        self.assertIn("never a sum", text)
        self.assertIn("two full rounds", text)                      # claim window
        self.assertIn("shame", text)                                # loser pays
        self.assertIn("pugio", text)                                # tie winner
        self.assertIn("face up at random", text)                    # start reveals
        self.assertNotIn("acclaimed emperor", text)                 # window replaced it

    def test_pugio_tiebreak_is_stated_everywhere(self):
        # A playtest disagreement: the sheet filed the pugio under defense
        # and the card said only "Wins tied duels", so players read the
        # tie-break as a defense-only extra that cannot combine with the
        # gladius. The mechanic is unchanged (D42, D54); the wording pins
        # it down in every printed place a player looks.
        rulebook = whole_text("imperial-rivals-305ad-rulebook-A4-BW.pdf")
        self.assertIn("passive tie-break", rulebook)
        self.assertIn("gladius and pugio together are legal", rulebook)
        self.assertIn("Compare the final totals", rulebook)      # order of ops
        self.assertIn("If both or neither hold one", rulebook)   # the tie case
        self.assertIn("Both players own all six items", rulebook)  # example
        cards = whole_text("imperial-rivals-305ad-cards-tokens-A4-BW.pdf")
        self.assertIn("Both or neither: the attacker wins", cards)
        self.assertIn("Always active", cards)
        sheets = whole_text("imperial-rivals-305ad-player-sheets-A4-BW.pdf")
        self.assertIn("TIE-BREAK - ALWAYS ON", sheets)           # own group
        quick = " ".join(whole_text("imperial-rivals-305ad-quick-reference-A4-BW.pdf").split())
        self.assertIn("tie: the lone pugio holder wins, else the attacker", quick)

    def test_rulebook_pins_the_twin_board_flow(self):
        text = whole_text("imperial-rivals-305ad-rulebook-A4-BW.pdf")
        self.assertIn("succession map", text)                       # the second board
        self.assertIn("Every pawn returns", text)                   # gate reset
        self.assertIn("to its gate on the succession map", text)
        self.assertIn("six faction cards", text)                    # blind support
        self.assertIn("the circles marked ? on the succession map", text)
        self.assertIn("That is a search", text)
        self.assertIn("An empty street gives nothing", text)
        self.assertIn("nine steps from the Peristyle", text)        # pinwheel gates
        self.assertIn("four guard posts", text)                     # succession posts
        self.assertIn("three steps east of the palace crossing", text)  # Peristyle moves
        self.assertIn("Guard post (star, on both maps)", text)
        self.assertNotIn("the only Prestige income there", text)
        self.assertIn("Faction cards exist only in the succession phase", text)
        self.assertNotIn("east side, on the east-west street", text)  # old fixed sites
        self.assertIn("the palace map leaves the table", text)
        self.assertNotIn("You may gain support in either phase", text)

    def test_pre_cleanup_rules_files_no_longer_load(self):
        # The retired experiment rules carry switches the engine no
        # longer reads; the loader must refuse them outright.
        import subprocess
        import sys as _sys
        result = subprocess.run(
            [_sys.executable, "tools/make_a4_print_kit.py",
             "--rules", "experiments/rules/rules_v08_succession.json"],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing top-level keys", result.stderr)

    def test_no_boost_prose_survives_anywhere(self):
        # 0.9.3 removed the optional +2 duel boost; if it ever comes
        # back, the prose (and this check) must be rewritten on purpose.
        for name in ("imperial-rivals-305ad-rulebook-A4-BW.pdf",
                     "imperial-rivals-305ad-quick-reference-A4-BW.pdf",
                     "imperial-rivals-305ad-teaching-guide-A4-BW.pdf",
                     "imperial-rivals-305ad-player-sheets-A4-BW.pdf",
                     "imperial-rivals-305ad-cards-tokens-A4-BW.pdf",
                     "imperial-rivals-305ad-succession-map-A4-BW.pdf"):
            text = whole_text(name)
            self.assertNotIn("boost", text.lower(), name)
            self.assertNotIn("+2", text, name)

    def test_reference_and_rulebook_teach_the_prestige_reserve(self):
        # In the four-seat Haiku game every rival held 0 Prestige when a
        # claim was proclaimed, and one spent its next point on support
        # instead of the contest fee; nobody could contest.
        quick = " ".join(whole_text("imperial-rivals-305ad-quick-reference-A4-BW.pdf").split())
        self.assertIn("Keep 1 in reserve: with 0 Prestige you cannot contest a claim.", quick)
        rulebook = whole_text("imperial-rivals-305ad-rulebook-A4-BW.pdf")
        self.assertIn("Keep 1 Prestige in reserve.", rulebook)

    def test_quick_reference_says_the_peristyle_moves(self):
        # In the 0.10.2 table game three of four seats were caught out by
        # the Peristyle sitting at (6,6) on the palace map and (9,6) on
        # the succession map, which share one street grid.
        quick = " ".join(whole_text("imperial-rivals-305ad-quick-reference-A4-BW.pdf").split())
        self.assertIn("Its Peristyle is 3 steps EAST of the palace one", quick)

    def test_quick_reference_states_the_six_item_checkpoint_claim(self):
        # In a four-agent playtest every seat looked for "claim the
        # checkpoint" on the palace map without knowing it needs all six
        # items; the quick reference listed the action but not the rule.
        text = " ".join(whole_text("imperial-rivals-305ad-quick-reference-A4-BW.pdf").split())
        self.assertIn("own ALL SIX items and stand at the Peristyle", text)
        self.assertIn("palace round 24", text)

    def test_player_sheets_list_all_trackers(self):
        text = whole_text("imperial-rivals-305ad-player-sheets-A4-BW.pdf")
        for item in self.rules["treasures"]["items"]:
            self.assertIn(item.upper().replace("_", " "), text.upper())
        self.assertIn("PRESTIGE - one counter on the track", text)
        self.assertIn("keep in", text)                              # the reserve
        self.assertIn("A claim wins at the END of the round", text)  # claim window
        self.assertNotIn("Setup: two treasure districts", text)
        for faction in ("Army", "Imperial officials", "City elites"):
            self.assertIn(faction, text)

    def test_cards_cover_the_six_items_and_identical_backs(self):
        fronts = page_text("imperial-rivals-305ad-cards-tokens-A4-BW.pdf", 0)
        for item in self.rules["treasures"]["items"]:
            self.assertIn(item.replace("_", " ").upper(), fronts.upper())
        # Six backs, each the same two-line title (one string per line).
        backs = page_text("imperial-rivals-305ad-cards-tokens-A4-BW.pdf", 1)
        self.assertEqual(backs.count("IMPERIAL"), 6)
        self.assertEqual(backs.count("RIVALS"), 6)

    def test_tokens_page_matches_game_limits(self):
        tokens = page_text("imperial-rivals-305ad-cards-tokens-A4-BW.pdf", 2)
        self.assertEqual(tokens.count("City phase (max 24 rounds):"), 1)
        self.assertEqual(tokens.count("Succession phase (max 24 rounds):"), 1)
        self.assertIn("PAWN", tokens.upper())  # fold-up pawns I-IV


class SuccessionMapMatchesRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = engine.load_rules(str(REPO / kit.RULES_FILE))
        cls.S = kit.build_succession_layout(cls.rules)
        cls.L = kit.build_layout(cls.rules)
        cls.board = cls.S["board"]
        cls.manifest = json.loads((PRINT / "kit-manifest.json").read_text())

    def symbols(self):
        """(centre, drawn radius) for every symbol, as draw_succession_map draws it."""
        special = ({tuple(g) for g in self.board.gates.values()}
                   | set(self.S["card_spaces"]) | {tuple(self.board.checkpoint)}
                   | {tuple(p) for p in self.board.guard_posts})
        out = [(xy, 9.2) for cell, xy in self.S["spaces"] if tuple(cell) not in special]
        out += [(self.S["pos"](tuple(c)), 9.6) for c in self.board.guard_posts]
        out += [(self.S["pos"](tuple(c)), 11.4) for c in self.board.gates.values()]
        out += [(self.S["pos"](c), 10.6) for c in self.S["card_spaces"]]
        out += [(self.S["pos"](tuple(self.board.checkpoint)), 11.2)]
        return out

    def test_counts(self):
        blocked = {tuple(cell) for cell in self.rules["succession"]["map"]["blocked"]}
        spaces = {cell for cell, _ in self.S["spaces"]}
        self.assertEqual(len(spaces), 97)
        self.assertEqual(len(blocked), 150)
        self.assertFalse(spaces & blocked)
        counts = self.manifest["counts_succession"]
        self.assertEqual(counts["street_spaces"], 97)
        self.assertEqual(counts["blocked"], 150)
        self.assertEqual(counts["gates"], 4)
        self.assertEqual(counts["blocks"], 6)
        self.assertEqual(counts["card_spaces"], 6)
        self.assertEqual(counts["guard_posts"], 4)

    def test_special_positions_match_rules(self):
        layout = self.manifest["layout"]["succession_map_mm"]
        specials = layout["specials_mm"]
        for pid, cell in self.board.gates.items():
            self.assertEqual(specials["gates"][pid],
                             [round(v, 2) for v in self.S["pos"](tuple(cell))])
        self.assertEqual(specials["checkpoint"],
                         [round(v, 2) for v in self.S["pos"](tuple(self.board.checkpoint))])
        self.assertEqual(specials["card_spaces"],
                         [[round(v, 2) for v in self.S["pos"](tuple(c))]
                          for c in self.rules["succession"]["map"]["card_spaces"]])
        self.assertEqual(specials["guard_posts"],
                         [[round(v, 2) for v in self.S["pos"](tuple(c))]
                          for c in self.rules["succession"]["map"]["guard_posts"]])
        self.assertEqual(self.board.guard_posts, [(0, 2), (18, 10), (2, 0), (16, 12)])

    def test_every_card_space_opens_one_block_through_a_door(self):
        # The four centre-street cards touch two blocks each; the door
        # shows which one. West of the Peristyle a card opens the block
        # to the south, east of it the block to the north.
        doors = self.S["card_doors"]
        blocks = self.S["blocks"]
        self.assertEqual(set(doors), set(self.S["card_spaces"]))
        self.assertEqual(sorted(i for i, _ in doors.values()), list(range(6)))
        numerals = ("I", "II", "III", "IV", "V", "VI")
        opened = {cell: numerals[i] for cell, (i, _) in doors.items()}
        self.assertEqual(opened, {(3, 0): "I", (15, 12): "VI", (3, 6): "IV",
                                  (15, 6): "III", (7, 6): "V", (11, 6): "II"})
        for (x, y), (i, side) in doors.items():
            x0, y0, x1, y1 = blocks[i]
            self.assertTrue(x0 <= x <= x1)
            self.assertEqual(y, y0 - 1 if side == "north" else y1 + 1)
            # Half-turn symmetry: the turned card opens the turned block.
            j, other = doors[(18 - x, 12 - y)]
            self.assertEqual(blocks[j], (18 - x1, 12 - y1, 18 - x0, 12 - y0))
            self.assertNotEqual(side, other)

    def test_one_card_for_each_block(self):
        # D53: six blocks, one faction card space beside each.
        blocks = self.S["blocks"]

        def touches(cell, block):
            x0, y0, x1, y1 = block
            return any(x0 <= cell[0] + dx <= x1 and y0 <= cell[1] + dy <= y1
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        cards = self.S["card_spaces"]
        self.assertEqual(len(blocks), 6)
        self.assertTrue(any(all(touches(c, b) for c, b in zip(cards, order))
                            for order in itertools.permutations(blocks)))

        # Compass sanity: the gates sit where the prose says.
        self.assertEqual(self.board.gates["P0"], (6, 0))    # north
        self.assertEqual(self.board.gates["P1"], (18, 6))   # east
        self.assertEqual(self.board.gates["P2"], (12, 12))  # south
        self.assertEqual(self.board.gates["P3"], (0, 6))    # west

    def test_same_footprint_and_cuts_as_the_palace_board(self):
        # The two boards tape back to back, so they must match exactly.
        self.assertEqual(self.S["art"], self.L["art"])
        self.assertEqual(self.S["cut"], self.L["cut"])
        self.assertEqual(self.S["tiles"], self.L["tiles"])
        self.assertEqual(self.manifest["layout"]["succession_map_mm"]["art_bounds_mm"],
                         list(self.L["art"]))

    def test_no_symbol_crosses_a_cut_line(self):
        cut_x, cut_y = self.S["cut"]["x"], self.S["cut"]["y"]
        for (x, y), r in self.symbols():
            self.assertFalse(x - r < cut_x < x + r, f"symbol at ({x}, {y}) crosses the upright cut")
            self.assertFalse(y - r < cut_y < y + r, f"symbol at ({x}, {y}) crosses the cross cut")

    def test_every_symbol_clears_the_safe_zone_on_some_tile(self):
        tiles = [(x0, y0) for x0, y0, _ in self.S["tiles"].values()]
        safe = kit.SAFE
        for (px, py), r in self.symbols():
            self.assertTrue(any(
                px - r - x0 >= safe and py - r - y0 >= safe
                and px + r - x0 <= kit.PAGE_W - safe and py + r - y0 <= kit.PAGE_H - safe
                for x0, y0 in tiles), f"symbol at ({px},{py}) has no printable copy")

    def test_each_tile_prints_two_registration_crosses_off_the_streets(self):
        knockout = 5.2
        for page_no, (x0, y0, _) in self.S["tiles"].items():
            shown = [(ax, ay) for ax, ay in self.S["reg_marks"]
                     if 11 < ax - x0 < kit.PAGE_W - 11 and 11 < ay - y0 < kit.PAGE_H - 11]
            self.assertEqual(len(shown), 2, f"tile {page_no}")
        for ax, ay in self.S["reg_marks"]:
            for (x, y), r in self.symbols():
                self.assertGreater((ax - x) ** 2 + (ay - y) ** 2, (r + knockout) ** 2,
                                   f"cross at ({ax}, {ay}) covers a street symbol")

    def test_page_names_its_marks(self):
        text = whole_text("imperial-rivals-305ad-succession-map-A4-BW.pdf")
        for word in ("THE SUCCESSION MAP", "PERISTYLE", "CITY BLOCK", "GOLDEN GATE",
                     "SILVER GATE", "BRONZE GATE", "IRON GATE", "faction card space",
                     "SUCCESSION MAP - PAGE 1 OF 4", "SUCCESSION MAP - PAGE 4 OF 4"):
            self.assertIn(word, text)

    def test_faction_cards_print_three_factions_and_three_blanks(self):
        fronts = page_text("imperial-rivals-305ad-cards-tokens-A4-BW.pdf", 3)
        for word in ("FACTION CARDS", "ARMY", "OFFICIALS", "ELITES"):
            self.assertIn(word, fronts)
        self.assertEqual(fronts.count("EMPTY STREET"), 3)
        backs = page_text("imperial-rivals-305ad-cards-tokens-A4-BW.pdf", 4)
        self.assertIn("FACTION CARD BACKS", backs)
        self.assertEqual(backs.count("FACTION CARD"), 1 + 6)     # header + six backs


if __name__ == "__main__":
    unittest.main()
