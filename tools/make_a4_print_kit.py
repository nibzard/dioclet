#!/usr/bin/env python3
# ABOUTME: Generate the A4 print-and-play kit PDFs and the kit manifest
# ABOUTME: from the adopted rules file, reading rule values from it.
"""Generate the A4 print-and-play kit for Imperial Rivals: 305 AD.

Everything prints on ordinary A4 paper with black ink only. The game
uses two boards. The palace board is one complete vector drawing of
the treasure map (19x13 cells, 97 street spaces, six intact blocks),
divided at print time into four overlapping A4 landscape tiles that
assemble into one large board (about A2). The succession map has the
same footprint and street grid (19x13 cells, six blocks, six faction
card spaces, one for each block) and
tiles onto four pages the same way, so the two boards can be taped back
to back. All other documents are A4 portrait.

Outputs into print/bw/ (black and white):
  imperial-rivals-305ad-board-4xA4-BW.pdf        four tiled palace-board pages (landscape)
  imperial-rivals-305ad-succession-map-A4-BW.pdf four tiled succession-map pages (landscape)
  imperial-rivals-305ad-player-sheets-A4-BW.pdf  four player mats (two per page)
  imperial-rivals-305ad-cards-tokens-A4-BW.pdf   treasure cards, tokens, faction cards
  imperial-rivals-305ad-rulebook-A4-BW.pdf       family rulebook
  imperial-rivals-305ad-quick-reference-A4-BW.pdf
  imperial-rivals-305ad-teaching-guide-A4-BW.pdf
  imperial-rivals-305ad-playtest-form-A4-BW.pdf
  imperial-rivals-305ad-print-instructions-A4-BW.pdf
  imperial-rivals-305ad-complete-print-kit-A4-BW.pdf (rules, quick reference, guide
                                   and sheets first; then the print instructions
                                   and every page to cut; no playtest form)
With --art, into print/ (the default edition):
  imperial-rivals-305ad-board-4xA4-ART.pdf, imperial-rivals-305ad-succession-map-ART.pdf,
  imperial-rivals-305ad-cards-tokens-ART.pdf, imperial-rivals-305ad-complete-print-kit-A4-ART.pdf
With --color, into print/color/ (the full-colour edition for colour printers):
  imperial-rivals-305ad-board-4xA4-COLOR.pdf, imperial-rivals-305ad-succession-map-COLOR.pdf,
  imperial-rivals-305ad-cards-tokens-COLOR.pdf, imperial-rivals-305ad-complete-print-kit-A4-COLOR.pdf
Always into print/:
  kit-manifest.json (layout facts used by the tests)

Run: python3 tools/make_a4_print_kit.py [--rules RULES_FILE] [--art] [--color]
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

import engine  # noqa: E402
from board import Board, validate_six_block_layout  # noqa: E402

RULES_FILE = "rules/imperial-rivals-v0.10.2.json"
OUT_DIR = "print"                         # ART edition and the manifest
BW_DIR = os.path.join(OUT_DIR, "bw")      # black-and-white edition
COLOR_DIR = os.path.join(OUT_DIR, "color")  # full-colour edition
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Brand names (Brand & Naming Specification v1.0, 15 November 2026).
# "Diocletian's Palace" stays in story copy only, never as the title.
BRAND = "Imperial Rivals"
EDITION = "305 AD"
PRODUCT = f"{BRAND}: {EDITION}"
DESCRIPTOR = "The Roman Succession"
TAGLINE = "Claim the throne. Survive the challenge."


# ---------------------------------------------------------------------------
# Rules values in prose. Every rule number in the printed text is read
# from the rules JSON through these helpers; only presentation (icons,
# colours, gate names) and rules the JSON cannot express stay static.

_NUMBER_WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
                 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
                 11: "eleven", 12: "twelve"}
_ORDINAL_WORDS = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
                  6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
                  11: "eleventh", 12: "twelfth"}


def count_word(n):
    """The printed word for a small rule count, else the numeral."""
    return _NUMBER_WORDS.get(n, str(n))


def ordinal_word(n):
    """'first'..'twelfth' for a round count in prose, else None."""
    return _ORDINAL_WORDS.get(n)


def full_rounds(n):
    """'one full round' / 'two full rounds' for a round count in prose."""
    return f"{count_word(n)} full round{'' if n == 1 else 's'}"


def printed_values(rules):
    """Every rule number the kit prose states, read from the rules JSON."""
    s, p = rules["succession"], rules["prestige"]
    window = s["claim_window_rounds"]
    if ordinal_word(window) is None:
        raise SystemExit(f"printed text cannot phrase a claim window of "
                         f"{window} rounds; update the kit prose")
    cap = p["cap"]
    if cap < 2:
        raise SystemExit("printed text draws a Prestige track with a "
                         "reserve box and a cap box above the cap")
    return {
        "players": rules["game"]["players"],
        "dice": rules["movement"]["dice"],
        "die_sides": rules["movement"]["die_sides"],
        "cap": cap,
        "guard_roll": p["guard_post_min_roll"],
        "guard_reward": p["guard_post_reward"],
        "duel_win": p["duel_win_reward"],
        "duel_loss": p["duel_loss_penalty"],
        "duel_range": rules["duels"]["range"],
        "tie_winner": rules["duels"]["tie_winner"],
        "support_cost": s["support_cost"],
        "contest_fee": s["contest_fee"],
        "factions_to_proclaim": s["factions_to_proclaim"],
        "window": window,
        "city_rounds": rules["palace"]["max_rounds"],
        "succession_rounds": s["max_rounds"],
        "grace": rules["palace"]["rounds_after_checkpoint"],
        "items_required": rules["palace"]["checkpoint_items_required"],
        "items": rules["treasures"]["items"],
        "start_face_up": rules["treasures"]["start_face_up"],
        "factions": s["faction_cards"]["factions"],
        "empty_streets": s["faction_cards"]["empty"],
    }


def twin_geometry(rules):
    """(east offset, equal gate distance) of the succession Peristyle.

    The prose states both numbers: 'N steps east of the palace
    crossing' and 'every gate is N steps from the Peristyle'.
    """
    palace_cp = rules["palace"]["map"]["checkpoint"]
    twin_cp = rules["succession"]["map"]["checkpoint"]
    east = twin_cp[0] - palace_cp[0]
    if east <= 0 or twin_cp[1] != palace_cp[1]:
        raise SystemExit("printed text places the succession Peristyle on "
                         "the palace crossing's street row, east of it")
    gates = rules["succession"]["map"]["gates"]
    steps = {abs(g[0] - twin_cp[0]) + abs(g[1] - twin_cp[1]) for g in gates.values()}
    if len(steps) != 1:
        raise SystemExit("printed text says every gate sits the same number "
                         "of steps from the succession Peristyle")
    return east, steps.pop()


FACTION_DISPLAY = {"army": "Army", "officials": "Imperial officials",
                   "elites": "City elites"}
_FACTION_CARDS = {"army": ("ARMY", "shield"), "officials": ("OFFICIALS", "column"),
                  "elites": ("ELITES", "laurel")}
_TREASURE_CARDS = {"pugio": ("Pugio", "dagger"), "pilum": ("Pilum", "pilum"),
                   "galea": ("Galea", "helmet"), "scutum": ("Scutum", "scutum"),
                   "gladius": ("Gladius", "gladius"),
                   "lorica_segmentata": ("Lorica Segmentata", "armor")}

# Card flavour per rules ability type; {v} is the ability value and
# {tie} the duels.tie_winner side from the rules JSON.
_CARD_ABILITY_TEXT = {
    "attack_bonus": "+{v} to your attack.",
    "defense_bonus": "+{v} to your defense.",
    "attack_vs_claimant": "+{v} attack vs the claimant.",
    "win_ties": "You win tied duels if only you hold it. Both or neither: "
                "the {tie} wins. Always active.",
    "reveal_district": "Once a game: reveal any district.",
    "prevent_displacement": "Once: a beaten claimant stays put.",
}


def treasure_card_rows(rules):
    """Treasure card rows (name, icon, flavour), read from the rules JSON."""
    tie = rules["duels"]["tie_winner"]
    rows = []
    for item in rules["treasures"]["items"]:
        if item not in _TREASURE_CARDS:
            raise SystemExit(f"no printed card design for the treasure item {item}")
        name, icon = _TREASURE_CARDS[item]
        ability = rules["treasures"]["abilities"][item]
        template = _CARD_ABILITY_TEXT.get(ability["type"])
        if template is None:
            raise SystemExit(f"no printed card text for the ability type "
                             f"{ability['type']}")
        rows.append((name, icon, template.format(v=ability["value"], tie=tie)))
    return rows


def faction_card_rows(rules):
    """Faction card rows (name, badge, lines), read from the rules JSON."""
    cfg = rules["succession"]["faction_cards"]
    rows = []
    for faction in cfg["factions"]:
        if faction not in _FACTION_CARDS:
            raise SystemExit(f"no printed card design for the faction {faction}")
        name, badge = _FACTION_CARDS[faction]
        rows.append((name, badge,
                     f"Support costs {rules['succession']['support_cost']} Prestige.",
                     "No roll."))
    rows.extend(("EMPTY STREET", None, "Nobody meets here.", "Search another card.")
                for _ in range(cfg["empty"]))
    return rows


_DEFAULT_RULES = engine.load_rules(os.path.join(REPO_ROOT, RULES_FILE))
KIT_VERSION = f"prototype print kit V{_DEFAULT_RULES['game']['rules_version']}"

# ---------------------------------------------------------------------------
# Board layout, in millimetres. Y grows upward; north is at the top.
# Grid cell (x, y) from the rules JSON uses y=0 as the north row, so the
# artwork flips it: art_y = MB + (rows - 1 - y) * CELL + CELL / 2.

CELL = 25.5
ML, MB = 50.0, 36.0                       # grid left / bottom margins
OVERLAP = 14.0                            # cut guides sit 7 mm from page edges
PAGE_W, PAGE_H = 297.0, 210.0             # A4 landscape
SAFE = 6.0                                # keep-out from page edges

GATE_NAMES = {"P0": "GOLDEN GATE - NORTH", "P1": "SILVER GATE - EAST",
              "P2": "BRONZE GATE - SOUTH", "P3": "IRON GATE - WEST"}


def build_layout(rules, section="palace"):
    """All geometric facts, computed once and shared by every page.

    The palace board and the succession map share one footprint and
    one street grid, so both use these tile windows, cut lines and
    registration crosses.
    """
    b = Board(rules, section)
    rows, cols = b.height, b.width
    grid_w, grid_h = cols * CELL, rows * CELL

    def pos(cell):
        x, y = cell
        return (ML + x * CELL + CELL / 2.0, MB + (rows - 1 - y) * CELL + CELL / 2.0)

    # Tile windows. The vertical cut line runs between grid columns 9
    # and 10 (inside the block band, no street circles); the horizontal
    # cut line between the decumanus (row 6) and the blocks south of
    # it, so no movement-space centre falls inside either band.
    cut_x = ML + 10 * CELL
    cut_y = MB + (rows - 7) * CELL         # boundary between rows 6 and 7
    left = (cut_x - PAGE_W + OVERLAP / 2.0, cut_x + OVERLAP / 2.0)
    right = (cut_x - OVERLAP / 2.0, cut_x - OVERLAP / 2.0 + PAGE_W)
    bottom = (cut_y - PAGE_H + OVERLAP / 2.0, cut_y + OVERLAP / 2.0)
    top = (cut_y - OVERLAP / 2.0, cut_y - OVERLAP / 2.0 + PAGE_H)
    tiles = {"1": (left[0], top[1] - PAGE_H, "top left"),
             "2": (right[0], top[1] - PAGE_H, "top right"),
             "3": (left[0], bottom[0], "bottom left"),
             "4": (right[0], bottom[0], "bottom right")}
    # Registration crosses: fixed artwork points clear of street
    # circles and block letters, near both cut lines. Every tile
    # prints exactly two, so families can level the pages while
    # taping: one pair along the vertical cut, one along the
    # horizontal cut.
    reg_marks = [(cut_x - 12.0, 300.0), (cut_x + 12.0, 300.0),   # vertical cut, top tiles
                 (cut_x - 12.0, 160.0), (cut_x + 12.0, 160.0),   # vertical cut, bottom tiles
                 # The horizontal-cut pairs must share x so families can
                 # stack them vertically when taping. The decumanus street
                 # row (circles x 62.75..521.75, y 192.6..211) leaves no
                 # room for a 9.6 mm crosshair anywhere along it, so both
                 # pairs sit west/east of the row ends, 12 mm off the cut.
                 (40.0, 201.0), (560.0, 201.0),                  # horizontal cut, top tiles
                 (40.0, 177.0), (560.0, 177.0)]                  # horizontal cut, bottom tiles
    spaces = sorted((tuple(cell), pos(cell)) for cell in
                    {(x, y) for x in range(cols) for y in range(rows)
                     if (x, y) not in b.blocked})
    return {
        "board": b, "rules": rules, "pos": pos, "rows": rows, "cols": cols,
        "grid": (ML, MB, grid_w, grid_h),
        "art": (left[0], bottom[0], right[1], top[1]),
        "cut": {"x": cut_x, "y": cut_y}, "reg_marks": reg_marks,
        "overlap": OVERLAP,
        "tiles": tiles, "spaces": spaces,
        "cell": CELL, "safe": SAFE, "version": KIT_VERSION,
        "sheet_note": ("SUCCESSION MAP - PAGE {} OF 4 - PRINT AT 100%"
                       if section == "succession" else "PAGE {} OF 4 - PRINT AT 100%"),
    }


# ---------------------------------------------------------------------------
# Vector primitives. All take layout coordinates in mm.

def _star(c, x, y, r):
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.42
        import math
        a = math.pi / 2.0 + i * math.pi / 5.0
        pts.append((x + rad * math.cos(a), y + rad * math.sin(a)))
    p = c.beginPath()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    p.close()
    c.drawPath(p, stroke=1, fill=0)


def _octagon(c, x, y, r):
    import math
    pts = [(x + r * math.cos(math.pi / 8.0 + i * math.pi / 4.0),
            y + r * math.sin(math.pi / 8.0 + i * math.pi / 4.0)) for i in range(8)]
    p = c.beginPath()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    p.close()
    c.drawPath(p, stroke=1, fill=0)


def _shield(c, x, y, r):
    p = c.beginPath()
    p.moveTo(x - r * 0.8, y + r * 0.75)
    p.lineTo(x + r * 0.8, y + r * 0.75)
    p.lineTo(x + r * 0.8, y - r * 0.15)
    p.curveTo(x + r * 0.8, y - r * 0.9, x, y - r, x, y - r)
    p.curveTo(x, y - r, x - r * 0.8, y - r * 0.9, x - r * 0.8, y - r * 0.15)
    p.close()
    c.drawPath(p, stroke=1, fill=0)


def _column(c, x, y, r):
    w, top, base = r * 0.75, y + r, y - r
    c.line(x - w, top, x + w, top)
    c.line(x - w, top - r * 0.12, x + w, top - r * 0.12)
    c.line(x - w, base, x + w, base)
    c.line(x - w, base + r * 0.12, x + w, base + r * 0.12)
    for dx in (-w * 0.45, 0, w * 0.45):
        c.line(x + dx, top - r * 0.12, x + dx, base + r * 0.12)


def _laurel(c, x, y, r):
    import math
    c.arc(x - r * 0.7, y - r * 0.8, x + r * 0.7, y + r * 0.8,
          startAng=145, extent=250)
    for side in (-1, 1):
        for i in range(5):
            a = math.radians(25 + i * 30)
            lx = x + side * r * 0.7 * math.sin(a)
            ly = y - r * 0.8 * math.cos(a)
            c.saveState()
            c.translate(lx, ly)
            c.rotate(side * (35 - i * 22))
            c.ellipse(-r * 0.12, -r * 0.22, r * 0.12, r * 0.22)
            c.restoreState()


def _arch(c, x, y, r):
    w, h = r * 0.95, r * 1.1
    p = c.beginPath()
    p.moveTo(x - w, y - h)
    p.lineTo(x - w, y + h * 0.1)
    p.curveTo(x - w, y + h, x + w, y + h, x + w, y + h * 0.1)
    p.lineTo(x + w, y - h)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    c.line(x - w * 0.55, y - h, x - w * 0.55, y + h * 0.55)
    c.line(x + w * 0.55, y - h, x + w * 0.55, y + h * 0.55)


def _crosshair(c, x, y, r=4.0):
    c.circle(x, y, r, stroke=1, fill=0)
    c.line(x - r * 1.5, y, x + r * 1.5, y)
    c.line(x, y - r * 1.5, x, y + r * 1.5)


def _hatch(c, x0, y0, w, h, gap=7.0):
    """Draw clipped building hatching from coordinates in millimetres."""
    c.saveState()
    p = c.beginPath()
    p.rect(x0 * mm, y0 * mm, w * mm, h * mm)
    c.clipPath(p, stroke=0, fill=0)
    c.setLineWidth(0.25)
    step = gap * 2
    d = x0 - h
    while d < x0 + w:
        c.line(d * mm, y0 * mm, (d + h) * mm, (y0 + h) * mm)
        d += step
    c.restoreState()


def _centered(c, x, y, text, font, size, dy=0.0):
    c.setFont(font, size)
    c.drawCentredString(x * mm, (y + dy) * mm, text)


# ---------------------------------------------------------------------------
# The complete board artwork, drawn once per tile inside that tile's clip.

def draw_board(c, L):
    b, rules = L["board"], L["rules"]
    prestige = rules["prestige"]
    guard_roll = prestige["guard_post_min_roll"]
    guard_reward = prestige["guard_post_reward"]
    pos = L["pos"]
    ml, mb, gw, gh = L["grid"]
    art = L["art"]
    import math

    # Outer decorative border (thin double rule) and corner ticks.
    bx0, by0, bx1, by1 = 19.0, 16.0, art[2] - 6.0, art[3] - 7.0
    c.setLineWidth(1.1)
    c.rect(bx0 * mm, by0 * mm, (bx1 - bx0) * mm, (by1 - by0) * mm)
    c.setLineWidth(0.4)
    c.rect((bx0 + 1.6) * mm, (by0 + 1.6) * mm, (bx1 - bx0 - 3.2) * mm, (by1 - by0 - 3.2) * mm)

    # Title band, above the north row of the grid.
    c.setLineWidth(0.0)
    _centered(c, (art[0] + art[2]) / 2.0, art[3] - 15.0, BRAND.upper(),
              "Times-Bold", 30)
    _centered(c, (art[0] + art[2]) / 2.0, art[3] - 23.0,
              f"{EDITION}  ·  DIOCLETIAN'S PALACE, SPLIT", "Times-Roman", 12.5)
    # Version lives on the document footers and in kit-manifest.json,
    # not on the board artwork itself.

    # North indicator (top right), below the sheet-number corner.
    nx, ny = art[2] - 37.0, art[3] - 22.0
    c.setLineWidth(1.0)
    p = c.beginPath()
    p.moveTo(nx * mm, (ny + 7) * mm)
    p.lineTo((nx - 2.6) * mm, (ny - 1) * mm)
    p.lineTo((nx + 2.6) * mm, (ny - 1) * mm)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    c.line(nx * mm, (ny - 1) * mm, nx * mm, (ny - 6.5) * mm)
    _centered(c, nx, ny - 12.5, "N", "Times-Bold", 11)

    # Buildings: light outline, sparse hatch, district letter, block note.
    for bld in rules["palace"]["map"]["buildings"]:
        x0 = ml + bld["x0"] * CELL + 2.4
        y0 = mb + (L["rows"] - 1 - bld["y1"]) * CELL + 2.4
        w = (bld["x1"] - bld["x0"] + 1) * CELL - 4.8
        h = (bld["y1"] - bld["y0"] + 1) * CELL - 4.8
        c.setLineWidth(1.2)
        c.rect(x0 * mm, y0 * mm, w * mm, h * mm)
        c.setLineWidth(0.8)
        c.rect((x0 + 1.7) * mm, (y0 + 1.7) * mm, (w - 3.4) * mm, (h - 3.4) * mm)
        _hatch(c, x0 + 2.6, y0 + 2.6, w - 5.2, h - 5.2, gap=8.5)
        cx, cy = x0 + w / 2.0, y0 + h / 2.0
        # White knockout plates keep the letter and caption crisp over
        # the hatching on any printer.
        c.saveState()
        c.setFillColorRGB(1, 1, 1)
        c.rect((cx - 14) * mm, (cy - 9) * mm, 28 * mm, 17 * mm, stroke=0, fill=1)
        c.rect((cx - 19) * mm, (cy - 17.6) * mm, 38 * mm, 6.4 * mm, stroke=0, fill=1)
        c.restoreState()
        _centered(c, cx, cy - 2.6, bld["district"], "Times-Bold", 40)
        _centered(c, cx, cy - 15.5, "PALACE BLOCK", "Helvetica", 8)

    # Streets: open circles. Cells with their own symbol (guard posts,
    # treasure entries, gates, the Peristyle) get no plain circle.
    special = ({tuple(g) for g in b.guard_posts}
               | {tuple(cell) for cell in b.districts.values()}
               | {tuple(cell) for cell in b.gates.values()}
               | {tuple(b.checkpoint)})
    for cell, (x, y) in L["spaces"]:
        if tuple(cell) in special:
            continue
        c.setLineWidth(1.0)
        c.circle(x * mm, y * mm, 9.2 * mm, stroke=1, fill=0)

    # Treasure entries: double circle with the district letter.
    for name, cell in sorted(b.districts.items()):
        x, y = pos(tuple(cell))
        c.setLineWidth(1.6)
        c.circle(x * mm, y * mm, 10.6 * mm, stroke=1, fill=0)
        c.setLineWidth(0.7)
        c.circle(x * mm, y * mm, 7.6 * mm, stroke=1, fill=0)
        _centered(c, x, y, name, "Times-Bold", 15, dy=-1.6)

    # Guard posts: star plus roll reminder.
    for cell in b.guard_posts:
        x, y = pos(tuple(cell))
        c.setLineWidth(1.3)
        _star(c, x * mm, (y + 1.4) * mm, 9.6 * mm)
        _centered(c, x, y - 6.6, f"{guard_roll}+", "Helvetica-Bold", 6.5)

    # Gates: doorway arch in a bold ring, name above. The band above
    # each gate ring is free of circles, blocks, and both cut lines.
    # "gate / start" in the legend explains the starting squares.
    for pid, cell in sorted(b.gates.items()):
        x, y = pos(tuple(cell))
        c.setLineWidth(2.0)
        c.circle(x * mm, y * mm, 11.4 * mm, stroke=1, fill=0)
        c.setLineWidth(1.5)
        _arch(c, x * mm, (y + 0.8) * mm, 7.8 * mm)
        _centered(c, x, y + 13.4, GATE_NAMES[pid], "Helvetica-Bold", 6.8)

    # Peristyle: octagon at the crossing. On the palace map the
    # crossing only opens the succession (the checkpoint claim); the
    # proclaiming happens on the succession map's Peristyle.
    px, py = pos(tuple(b.checkpoint))
    c.setLineWidth(2.0)
    _octagon(c, px * mm, py * mm, 11.2 * mm)
    c.setLineWidth(0.8)
    _octagon(c, px * mm, py * mm, 8.2 * mm)
    _centered(c, px, py - 1.6, "X", "Times-Bold", 10)
    # Label above the octagon: below it, the text top would sit 0.4 mm
    # from the horizontal cut line and a wandering cut would shave it.
    _centered(c, px, py + 13.4, "PERISTYLE", "Helvetica-Bold", 6.8)

    # (The cardo and decumanus street names live in the legend caption;
    # the board itself stays symbol-only. The faction meeting places
    # sit on the succession map, not here.)

    # Legend band below the grid, two rows so every label keeps air.
    row_defs = [
        (by0 + 15.4, [("circle", "street space"),
                      ("double", "treasure entry (take equipment)"),
                      ("arch", "gate / start"),
                      ("octagon", "Peristyle - claim here to open the succession"),
                      ("star", f"guard post: roll {guard_roll}+ for "
                               f"{guard_reward} Prestige")]),
        (by0 + 7.2, [("hatch", "building - no entry"),
                     ("blank", "faction meeting places live on the succession map")]),
    ]
    legend_positions = ((25, 115, 245, 355, 450), (25, 130))
    for (sy, entries), positions in zip(row_defs, legend_positions):
        for (kind, label), x in zip(entries, positions):
            c.setLineWidth(1.0)
            if kind == "circle":
                c.circle(x * mm, sy * mm, 3.0 * mm)
                x += 7.0
            elif kind == "double":
                c.setLineWidth(1.4)
                c.circle(x * mm, sy * mm, 3.4 * mm)
                c.setLineWidth(0.6)
                c.circle(x * mm, sy * mm, 2.2 * mm)
                x += 8.0
            elif kind == "arch":
                _arch(c, x * mm, sy * mm, 3.0 * mm)
                x += 7.0
            elif kind == "octagon":
                _octagon(c, x * mm, sy * mm, 3.4 * mm)
                x += 8.0
            elif kind == "star":
                _star(c, x * mm, sy * mm, 3.6 * mm)
                x += 8.5
            elif kind == "shield":
                _shield(c, x * mm, sy * mm, 3.2 * mm)
                x += 7.0
            elif kind == "column":
                _column(c, x * mm, (sy + 0.4) * mm, 3.0 * mm)
                x += 7.0
            elif kind == "laurel":
                _laurel(c, x * mm, (sy + 0.4) * mm, 3.4 * mm)
                x += 8.5
            elif kind == "hatch":
                c.setLineWidth(0.8)
                c.rect(x * mm, (sy - 2.8) * mm, 5.6 * mm, 5.6 * mm)
                c.setLineWidth(0.25)
                for d in (1.4, 3.0, 4.6):
                    c.line((x + d) * mm, (sy - 2.8) * mm, (x + d - 2.2) * mm, (sy + 2.8) * mm)
                x += 9.0
            c.setFont("Helvetica", 9.5)
            c.drawString(x * mm, (sy - 1.1) * mm, label)


def draw_tile_furniture(c, L, page_no, window):
    """Page furniture in page coordinates.

    The board assembles by butt-join: every tile prints dashed cut
    lines wherever a cut line crosses it, the family cuts on the
    dashes, and the straight edges are taped together from the back.
    The sheet number sits in the outer corner of each tile, inside
    the artwork margin, so it stays readable on the loose sheet and
    looks like a map folio number on the assembled board.
    """
    x0, y0 = window[0], window[1]
    cut_x = L["cut"]["x"] - x0        # vertical cut line on this page
    cut_y = L["cut"]["y"] - y0        # horizontal cut line on this page

    c.setLineWidth(0.5)
    for cx, cy, dx, dy in ((0, 0, 1, 1), (PAGE_W, 0, -1, 1),
                           (0, PAGE_H, 1, -1), (PAGE_W, PAGE_H, -1, -1)):
        c.line((cx + 3 * dx) * mm, cy * mm, (cx + 8 * dx) * mm, cy * mm)
        c.line(cx * mm, (cy + 3 * dy) * mm, cx * mm, (cy + 8 * dy) * mm)

    # Dashed cut guides: both cut lines appear on every tile they
    # cross, at identical artwork positions on both neighbours.
    c.setDash(2.2, 2.2)
    c.setLineWidth(0.5)
    if 0 < cut_x < PAGE_W:
        c.line(cut_x * mm, 9 * mm, cut_x * mm, (PAGE_H - 9) * mm)
    if 0 < cut_y < PAGE_H:
        c.line(9 * mm, cut_y * mm, (PAGE_W - 9) * mm, cut_y * mm)
    c.setDash()

    # Registration crosses near the cut lines. Both neighbouring tiles
    # print one, at fixed artwork points clear of page edges, so the
    # family can level the quadrants while taping.
    c.setLineWidth(0.55)
    for ax, ay in L["reg_marks"]:
        px, py = ax - x0, ay - y0
        if 11 < px < PAGE_W - 11 and 11 < py < PAGE_H - 11:
            c.saveState()
            c.setFillColorRGB(1, 1, 1)
            c.circle(px * mm, py * mm, 5.2 * mm, stroke=0, fill=1)
            c.restoreState()
            _crosshair(c, px * mm, py * mm, 3.2 * mm)

    # Sheet number in the outer corner of the tile (the corner of the
    # assembled board this page becomes), in page coordinates.
    note = L["sheet_note"].format(page_no)
    c.setFont("Helvetica-Bold", 6.2)
    if page_no in ("1", "3"):
        ax, ay = L["art"][0] + 11, (383.5 if page_no == "1" else 19.0)
    else:
        ax, ay = L["art"][2] - 7.5, (383.5 if page_no == "2" else 19.0)
    if page_no in ("1", "3"):
        c.drawString((ax - x0) * mm, (ay - y0) * mm, note)
    else:
        c.drawRightString((ax - x0) * mm, (ay - y0) * mm, note)


def board_pdf(path, L):
    c = pdfcanvas.Canvas(path, pagesize=landscape(A4))
    c.setTitle(f"{PRODUCT} - board (4 x A4, black and white)")
    c.setAuthor("dioclet print kit")
    for page_no in ("1", "2", "3", "4"):
        x0, y0, _ = L["tiles"][page_no]
        c.saveState()
        p = c.beginPath()
        p.rect(0, 0, PAGE_W * mm, PAGE_H * mm)
        c.clipPath(p, stroke=0, fill=0)
        c.translate(-x0 * mm, -y0 * mm)
        draw_board(c, L)
        c.restoreState()
        draw_tile_furniture(c, L, page_no, (x0, y0))
        c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# The succession map: the palace board's footprint, tiled 2 x 2 at the
# same scale and on the same cut lines, so the two boards can be taped
# back to back into one board that turns over.

def build_succession_layout(rules):
    """Geometric facts for the succession map, sharing the palace tiling."""
    S = build_layout(rules, "succession")
    b = S["board"]
    palace = Board(rules)
    if (b.width, b.height) != (palace.width, palace.height) or b.blocked != palace.blocked:
        raise SystemExit("the succession map must use the palace board's street grid")
    # The succession map declares no building footprints; its six
    # blocks are the connected components of blocked cells, drawn as
    # their exact bounding boxes (each component is a rectangle).
    remaining, components = set(b.blocked), []
    while remaining:
        start = remaining.pop()
        group, queue = {start}, [start]
        while queue:
            cur = queue.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in remaining:
                    remaining.remove(nxt)
                    group.add(nxt)
                    queue.append(nxt)
        components.append(group)
    blocks = []
    for group in components:
        xs = [c[0] for c in group]
        ys = [c[1] for c in group]
        blocks.append((min(xs), min(ys), max(xs), max(ys)))
    blocks.sort(key=lambda r: (r[1], r[0]))    # north-west first (y 0 is north)
    cards = [tuple(c) for c in rules["succession"]["map"]["card_spaces"]]
    S.update(blocks=blocks, card_spaces=cards,
             card_doors=_card_doors(cards, blocks, tuple(b.checkpoint)),
             grid_w=S["cols"] * CELL, grid_h=S["rows"] * CELL)
    return S


def _card_doors(cards, blocks, checkpoint):
    """Which block each faction card space opens: {card: (block index, side)}.

    A card that touches one block opens that block. A card on the
    centre street touches the block north of it and the block south of
    it: west of the Peristyle it opens the south block, east of it the
    north block, so the doors look the same after a half-turn. Every
    block must get exactly one card. Side is the block edge that holds
    the door ("north" or "south"; y 0 is north).
    """
    def touches(cell, block):
        x0, y0, x1, y1 = block
        return x0 <= cell[0] <= x1 and cell[1] in (y0 - 1, y1 + 1)

    doors = {}
    for cell in cards:
        near = [i for i, block in enumerate(blocks) if touches(cell, block)]
        if len(near) > 1:
            want_south = cell[0] < checkpoint[0]
            near = [i for i in near if (blocks[i][1] > cell[1]) == want_south]
        if len(near) != 1:
            raise SystemExit(f"faction card space {cell} does not open exactly one block")
        i = near[0]
        doors[cell] = (i, "north" if blocks[i][1] > cell[1] else "south")
    if sorted(i for i, _ in doors.values()) != list(range(len(blocks))):
        raise SystemExit("every block needs exactly one faction card space")
    return doors


def _door(c, x, y, side, scale=1.0):
    """A doorway in a block wall at (x, y) mm, opening toward its card.

    Drawn as if the card sits above the wall; a south-edge door is the
    same drawing turned half a circle.
    """
    c.saveState()
    c.translate(x * mm, y * mm)
    if side == "south":
        c.rotate(180)
    c.scale(scale, scale)
    c.setFillColorRGB(1, 1, 1)
    c.rect(-6.8 * mm, -7.0 * mm, 13.6 * mm, 7.6 * mm, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.rect(-6.8 * mm, -6.2 * mm, 1.8 * mm, 6.2 * mm, stroke=0, fill=1)
    c.rect(5.0 * mm, -6.2 * mm, 1.8 * mm, 6.2 * mm, stroke=0, fill=1)
    c.setLineWidth(1.0)
    _arch(c, 0, -3.3 * mm, 3.0 * mm)
    c.restoreState()


def _card_space(c, x, y, r):
    """A faction card space: bold ring, a face-down card with a '?'."""
    c.setLineWidth(1.8)
    c.circle(x * mm, y * mm, r * mm, stroke=1, fill=0)
    w, h = r * 0.80, r * 1.10
    c.setLineWidth(1.0)
    c.roundRect((x - w / 2) * mm, (y - h / 2) * mm, w * mm, h * mm, r * 0.10 * mm,
                stroke=1, fill=0)
    _centered(c, x, y - r * 0.30, "?", "Times-Bold", r * 1.55)


def _knockout_label(c, x, y, text, font="Helvetica-Bold", size=6.8):
    """Centred text on a tight white plate, so hatch never crosses it."""
    w = c.stringWidth(text, font, size) / mm
    c.saveState()
    c.setFillColorRGB(1, 1, 1)
    c.rect((x - w / 2.0 - 1.2) * mm, (y - 0.9) * mm, (w + 2.4) * mm, (size * 0.36 + 1.6) * mm,
           stroke=0, fill=1)
    c.restoreState()
    _centered(c, x, y, text, font, size)


def draw_succession_map(c, S):
    b, rules = S["board"], S["rules"]
    prestige = rules["prestige"]
    guard_roll = prestige["guard_post_min_roll"]
    guard_reward = prestige["guard_post_reward"]
    support_cost = rules["succession"]["support_cost"]
    pos = S["pos"]
    ml, mb = S["grid"][0], S["grid"][1]
    art = S["art"]

    # Outer border, title band and north arrow, as on the palace board.
    bx0, by0, bx1, by1 = 19.0, 16.0, art[2] - 6.0, art[3] - 7.0
    c.setLineWidth(1.1)
    c.rect(bx0 * mm, by0 * mm, (bx1 - bx0) * mm, (by1 - by0) * mm)
    c.setLineWidth(0.4)
    c.rect((bx0 + 1.6) * mm, (by0 + 1.6) * mm, (bx1 - bx0 - 3.2) * mm, (by1 - by0 - 3.2) * mm)
    c.setLineWidth(0.0)
    _centered(c, (art[0] + art[2]) / 2.0, art[3] - 15.0, "THE SUCCESSION MAP",
              "Times-Bold", 30)
    _centered(c, (art[0] + art[2]) / 2.0, art[3] - 23.0,
              f"{PRODUCT.upper()}  ·  {DESCRIPTOR.upper()}", "Times-Roman", 12.5)
    nx, ny = art[2] - 37.0, art[3] - 22.0
    c.setLineWidth(1.0)
    p = c.beginPath()
    p.moveTo(nx * mm, (ny + 7) * mm)
    p.lineTo((nx - 2.6) * mm, (ny - 1) * mm)
    p.lineTo((nx + 2.6) * mm, (ny - 1) * mm)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    c.line(nx * mm, (ny - 1) * mm, nx * mm, (ny - 6.5) * mm)
    _centered(c, nx, ny - 12.5, "N", "Times-Bold", 11)

    # City blocks: double outline, sparse hatch, numeral on a plate.
    numerals = ("I", "II", "III", "IV", "V", "VI")
    for index, (x0, y0, x1, y1) in enumerate(S["blocks"]):
        bx = ml + x0 * CELL + 2.4
        by = mb + (S["rows"] - 1 - y1) * CELL + 2.4
        bw = (x1 - x0 + 1) * CELL - 4.8
        bh = (y1 - y0 + 1) * CELL - 4.8
        c.setLineWidth(1.2)
        c.rect(bx * mm, by * mm, bw * mm, bh * mm)
        c.setLineWidth(0.8)
        c.rect((bx + 1.7) * mm, (by + 1.7) * mm, (bw - 3.4) * mm, (bh - 3.4) * mm)
        _hatch(c, bx + 2.6, by + 2.6, bw - 5.2, bh - 5.2, gap=8.5)
        cx, cy = bx + bw / 2.0, by + bh / 2.0
        if bx < S["cut"]["x"] < bx + bw:
            # A middle block: keep its plate whole, west of the cut.
            cx = min(cx, S["cut"]["x"] - 3.0 - 17.0)
        c.saveState()
        c.setFillColorRGB(1, 1, 1)
        c.rect((cx - 14) * mm, (cy - 9) * mm, 28 * mm, 17 * mm, stroke=0, fill=1)
        c.rect((cx - 17) * mm, (cy - 17.6) * mm, 34 * mm, 6.4 * mm, stroke=0, fill=1)
        c.restoreState()
        _centered(c, cx, cy - 2.6, numerals[index], "Times-Bold", 34)
        _centered(c, cx, cy - 15.5, "CITY BLOCK", "Helvetica", 8)

    # Doors: each block opens toward its one faction card space.
    for cell, (index, side) in S["card_doors"].items():
        x0, y0, x1, y1 = S["blocks"][index]
        edge = (mb + (S["rows"] - y0) * CELL - 2.4 if side == "north"
                else mb + (S["rows"] - 1 - y1) * CELL + 2.4)
        _door(c, pos(cell)[0], edge, side)

    # Streets: open circles; special cells carry their own symbols.
    special = ({tuple(g) for g in b.gates.values()} | set(S["card_spaces"])
               | {tuple(g) for g in b.guard_posts} | {tuple(b.checkpoint)})
    for cell, (x, y) in S["spaces"]:
        if tuple(cell) in special:
            continue
        c.setLineWidth(1.0)
        c.circle(x * mm, y * mm, 9.2 * mm, stroke=1, fill=0)

    # Faction card spaces: one face-down card each, dealt at the change.
    for cell in S["card_spaces"]:
        x, y = pos(cell)
        _card_space(c, x, y, 10.6)

    # Guard posts: star plus roll reminder, as on the palace map.
    for cell in b.guard_posts:
        x, y = pos(tuple(cell))
        c.setLineWidth(1.3)
        _star(c, x * mm, (y + 1.4) * mm, 9.6 * mm)
        _centered(c, x, y - 6.6, f"{guard_roll}+", "Helvetica-Bold", 6.5)

    # Gates: arch in a bold ring, name above on a plate (the south gate
    # sits under a block, so its name crosses the block frame).
    for pid, cell in sorted(b.gates.items()):
        x, y = pos(tuple(cell))
        c.setLineWidth(2.0)
        c.circle(x * mm, y * mm, 11.4 * mm, stroke=1, fill=0)
        c.setLineWidth(1.5)
        _arch(c, x * mm, (y + 0.8) * mm, 7.8 * mm)
        _knockout_label(c, x, y + 13.4, GATE_NAMES[pid])

    # Peristyle: octagon on the middle street, label above (the horizontal
    # cut runs 1.5 mm below the octagon).
    px, py = pos(tuple(b.checkpoint))
    c.setLineWidth(2.0)
    _octagon(c, px * mm, py * mm, 11.2 * mm)
    c.setLineWidth(0.8)
    _octagon(c, px * mm, py * mm, 8.2 * mm)
    _centered(c, px, py - 1.6, "X", "Times-Bold", 10)
    _knockout_label(c, px, py + 13.4, "PERISTYLE")

    # Legend band below the grid, two rows; entries flow left to right.
    row_defs = [
        (by0 + 15.4, [("circle", "street space"),
                      ("card", f"faction card space: search, then "
                               f"{support_cost} Prestige for support"),
                      ("arch", "gate / return here"),
                      ("octagon", "Peristyle - proclaim here")]),
        (by0 + 7.2, [("hatch", "building - no entry"),
                     ("door", "door: the block a card space opens"),
                     ("star", f"guard post: roll {guard_roll}+ for "
                              f"{guard_reward} Prestige")]),
    ]
    for sy, entries in row_defs:
        x = 40.0
        for kind, label in entries:
            c.setLineWidth(1.0)
            if kind == "circle":
                c.circle(x * mm, sy * mm, 3.0 * mm)
                x += 7.0
            elif kind == "card":
                _card_space(c, x, sy, 3.4)
                x += 8.0
            elif kind == "arch":
                _arch(c, x * mm, sy * mm, 3.0 * mm)
                x += 7.0
            elif kind == "octagon":
                _octagon(c, x * mm, sy * mm, 3.4 * mm)
                x += 8.0
            elif kind == "star":
                _star(c, x * mm, sy * mm, 3.6 * mm)
                x += 8.5
            elif kind == "door":
                c.setLineWidth(0.8)
                c.line((x - 4.0) * mm, (sy + 2.6) * mm, (x + 5.0) * mm, (sy + 2.6) * mm)
                _door(c, x + 0.5, sy + 2.6, "north", scale=0.55)
                x += 9.0
            elif kind == "hatch":
                c.setLineWidth(0.8)
                c.rect(x * mm, (sy - 2.8) * mm, 5.6 * mm, 5.6 * mm)
                c.setLineWidth(0.25)
                for d in (1.4, 3.0, 4.6):
                    c.line((x + d) * mm, (sy - 2.8) * mm, (x + d - 2.2) * mm, (sy + 2.8) * mm)
                x += 9.0
            c.setFont("Helvetica", 9.5)
            c.drawString(x * mm, (sy - 1.1) * mm, label)
            x += c.stringWidth(label, "Helvetica", 9.5) / mm + 12.0


def succession_map_pdf(path, rules):
    S = build_succession_layout(rules)
    c = pdfcanvas.Canvas(path, pagesize=landscape(A4))
    c.setTitle(f"{PRODUCT} - succession map (4 x A4, black and white)")
    c.setAuthor("dioclet print kit")
    for page_no in ("1", "2", "3", "4"):
        x0, y0, _ = S["tiles"][page_no]
        c.saveState()
        p = c.beginPath()
        p.rect(0, 0, PAGE_W * mm, PAGE_H * mm)
        c.clipPath(p, stroke=0, fill=0)
        c.translate(-x0 * mm, -y0 * mm)
        draw_succession_map(c, S)
        c.restoreState()
        draw_tile_furniture(c, S, page_no, (x0, y0))
        c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Text helpers for the portrait documents.

PW, PH = 210.0, 297.0


def new_doc(path, title, landscape_pages=False):
    c = pdfcanvas.Canvas(path, pagesize=A4)
    c.setTitle(title)
    c.setAuthor(f"{BRAND} print kit")
    return c


def doc_header(c, title, subtitle=None):
    c.setLineWidth(1.4)
    c.line(16 * mm, (PH - 20) * mm, (PW - 16) * mm, (PH - 20) * mm)
    c.setFont("Times-Bold", 19)
    c.drawCentredString(PW / 2.0 * mm, (PH - 15.5) * mm, title)
    if subtitle:
        c.setFont("Times-Italic", 9.5)
        c.drawCentredString(PW / 2.0 * mm, (PH - 25.5) * mm, subtitle)
    c.setLineWidth(0.4)
    c.line(16 * mm, (PH - 28.5) * mm, (PW - 16) * mm, (PH - 28.5) * mm)


def doc_footer(c, page, total=None):
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(PW / 2.0 * mm, 9 * mm,
                        f"{PRODUCT} - {KIT_VERSION} - page {page}"
                        + (f" of {total}" if total else ""))
    c.setLineWidth(0.4)
    c.line(16 * mm, 13 * mm, (PW - 16) * mm, 13 * mm)


def para(c, text, x, y, w, size=9.6, leading=None, font="Times-Roman", indent=0.0):
    """Simple word wrap; returns the y after the last line."""
    leading = leading or size * 1.38 / mm
    c.setFont(font, size)
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if c.stringWidth(trial, font, size) <= (w - indent) * mm:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    for i, line in enumerate(lines):
        c.drawString((x + (indent if i else 0)) * mm, y * mm, line)
        y -= leading
    return y


def wrap_lines(c, text, w, size=9.6, font="Times-Roman"):
    """Measure how many wrapped lines ``text`` needs at this size."""
    c.setFont(font, size)
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if c.stringWidth(trial, font, size) <= w * mm:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def bullet(c, text, x, y, w, size=9.6, marker="-", indent=4.5):
    c.setFont("Times-Roman", size)
    c.drawString(x * mm, y * mm, marker)
    return para(c, text, x + indent, y, w - indent, size=size)


def section(c, title, y, size=13):
    c.setFont("Times-Bold", size)
    c.drawString(16 * mm, y * mm, title)
    c.setLineWidth(0.7)
    c.line(16 * mm, (y - 1.8) * mm, (PW - 16) * mm, (y - 1.8) * mm)
    return y - 7.0


def box(c, x, y, w, h, label=None, lw=1.0, dashed=False):
    if dashed:
        c.setDash(2, 2)
    c.setLineWidth(lw)
    c.rect(x * mm, y * mm, w * mm, h * mm)
    c.setDash()
    if label:
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString((x + w / 2.0) * mm, (y + h / 2.0 - 1.4) * mm, label)


def checkbox(c, x, y, s=4.6):
    c.setLineWidth(0.9)
    c.rect(x * mm, y * mm, s * mm, s * mm)


def ruler100(c, x, y):
    c.setLineWidth(0.8)
    c.line(x * mm, y * mm, (x + 100) * mm, y * mm)
    for i in range(0, 101, 5):
        h = 3.4 if i % 10 == 0 else 2.0
        c.line((x + i) * mm, y * mm, (x + i) * mm, (y + h) * mm)
        if i % 10 == 0:
            c.setFont("Helvetica", 5.5)
            c.drawCentredString((x + i) * mm, (y - 3.6) * mm, str(i))
    c.setFont("Helvetica", 6.5)
    c.drawString((x + 104) * mm, (y + 0.5) * mm, "mm - must measure 100 mm")


# ---------------------------------------------------------------------------
# Player sheets.

def _mat_head(c, x, y, w, title):
    """A section title with a thin rule under it."""
    c.setFont("Helvetica-Bold", 7.8)
    c.drawString(x * mm, y * mm, title)
    c.setLineWidth(0.5)
    c.line(x * mm, (y - 1.6) * mm, (x + w) * mm, (y - 1.6) * mm)


def _fit(c, text, font, size, width):
    """The largest size up to `size` at which `text` fits in `width` mm."""
    while size > 6.0 and c.stringWidth(text, font, size) / mm > width:
        size -= 0.2
    return size


def player_mat(c, x, y, w, h, numeral, rules):
    """One player's mat: identity, equipment, Prestige, and the succession.

    Built around what players asked about in play: which item bonus
    counts, why to keep 1 Prestige, which supports they hold, and when
    a standing claim wins.
    """
    v = printed_values(rules)
    # The mat files each item under the ability kind its column assumes.
    abilities = rules["treasures"]["abilities"]
    for item, kind in (("gladius", "attack_bonus"),
                       ("pilum", "attack_vs_claimant"),
                       ("scutum", "defense_bonus"),
                       ("pugio", "win_ties"),
                       ("galea", "reveal_district"),
                       ("lorica_segmentata", "prevent_displacement")):
        if abilities[item]["type"] != kind:
            raise SystemExit(f"the printed mat files the {item} under its "
                             f"{kind} ability; update the kit prose")
    gladius_v = abilities["gladius"]["value"]
    pilum_v = abilities["pilum"]["value"]
    scutum_v = abilities["scutum"]["value"]
    cap = v["cap"]
    guard_roll = v["guard_roll"]
    guard_reward = v["guard_reward"]
    duel_win = v["duel_win"]
    duel_loss = v["duel_loss"]
    support_cost = v["support_cost"]
    contest_fee = v["contest_fee"]
    duel_range = v["duel_range"]
    req = v["factions_to_proclaim"]
    win = v["window"]
    dice = v["dice"]

    c.setLineWidth(1.4)
    c.rect(x * mm, y * mm, w * mm, h * mm)
    c.setLineWidth(0.5)
    c.rect((x + 1.4) * mm, (y + 1.4) * mm, (w - 2.8) * mm, (h - 2.8) * mm)

    # Header: the numeral plate, name, and the gate to circle.
    top = y + h
    c.setLineWidth(1.0)
    c.rect((x + 5) * mm, (top - 17) * mm, 24 * mm, 12.5 * mm)
    _centered(c, x + 17, top - 8.6, "PLAYER", "Helvetica-Bold", 6.4)
    _centered(c, x + 17, top - 15.2, numeral, "Times-Bold", 17)
    c.setFont("Times-Roman", 9.5)
    c.drawString((x + 34) * mm, (top - 9) * mm, "Name ____________________________")
    c.setFont("Helvetica-Bold", 6.8)
    c.drawString((x + 34) * mm, (top - 15.4) * mm, "YOUR GATE (circle one; the same on both maps):")
    gx = x + 34 + c.stringWidth("YOUR GATE (circle one; the same on both maps):",
                                "Helvetica-Bold", 6.8) / mm + 3
    for gate in ("GOLDEN · N", "SILVER · E", "BRONZE · S", "IRON · W"):
        gw = c.stringWidth(gate, "Helvetica", 7.2) / mm + 4
        c.setLineWidth(0.5)
        c.roundRect(gx * mm, (top - 17.4) * mm, gw * mm, 5.4 * mm, 1.2 * mm)
        c.setFont("Helvetica", 7.2)
        c.drawString((gx + 2) * mm, (top - 15.4) * mm, gate)
        gx += gw + 2
    c.setLineWidth(0.8)
    c.line((x + 4) * mm, (top - 20.5) * mm, (x + w - 4) * mm, (top - 20.5) * mm)

    colw = (w - 16) / 3.0
    cols = [x + 4, x + 8 + colw, x + 12 + 2 * colw]
    c.setLineWidth(0.4)
    for cx in cols[1:]:
        c.line((cx - 2) * mm, (y + 24) * mm, (cx - 2) * mm, (top - 23) * mm)
    y0 = top - 27

    # Column 1: equipment, grouped by when it helps.
    cx, ty = cols[0], y0
    _mat_head(c, cx, ty, colw, "EQUIPMENT - tick what you collect")
    ty -= 6.6
    groups = [("IN ATTACK", [("Gladius", f"+{gladius_v} when you attack", False),
                             ("Pilum", f"+{pilum_v} attacking the claimant", False)]),
              ("IN DEFENSE", [("Scutum", f"+{scutum_v} when you defend", False)]),
              ("TIE-BREAK - ALWAYS ON", [("Pugio", "you win tied duels", False)]),
              ("ONCE PER GAME - tick used", [("Galea", "action: reveal a card", True),
                                             ("Lorica", "segmentata: stay if beaten", True)])]
    for title, items in groups:
        c.setFont("Helvetica-Oblique", 6.4)
        c.drawString(cx * mm, ty * mm, title)
        ty -= 5.6
        for name, hint, once in items:
            checkbox(c, cx, ty - 0.6, 4.0)
            c.setFont("Times-Bold", 9.2)
            c.drawString((cx + 5.6) * mm, ty * mm, name)
            hx = cx + 5.6 + max(13.5, c.stringWidth(name, "Times-Bold", 9.2) / mm + 2.0)
            room = colw - (hx - cx) - (6.0 if once else 0)
            size = _fit(c, hint, "Times-Italic", 7.8, room)
            c.setFont("Times-Italic", size)
            c.drawString(hx * mm, ty * mm, hint)
            if once:
                c.setLineWidth(0.7)
                c.circle((cx + colw - 2.2) * mm, (ty + 1.3) * mm, 2.0 * mm)
            ty -= 6.0
        ty -= 0.8
    note = "In a duel add ONE best bonus - never a sum."
    c.setFont("Times-Bold", _fit(c, note, "Times-Bold", 8.4, colw - 1))
    c.drawString(cx * mm, ty * mm, note)

    # Column 2: the Prestige track and where Prestige comes from and goes.
    cx, ty = cols[1], y0
    _mat_head(c, cx, ty, colw, "PRESTIGE - one counter on the track")
    ty -= 15.5
    box = (colw - 3) / (cap + 1)
    notes = {0: ("cannot", "contest"), 1: ("keep in", "reserve"),
             cap: ("cap - more", "is lost")}
    for i in range(cap + 1):
        bx = cx + i * (box + 1)
        c.setLineWidth(1.6 if i == 1 else 0.9)
        c.rect(bx * mm, ty * mm, box * mm, 10 * mm)
        _centered(c, bx + box / 2, ty + 3.2, str(i), "Times-Bold", 13)
        for k, line in enumerate(notes.get(i, ())):
            _centered(c, bx + box / 2, ty - 3.4 - k * 3.0, line, "Helvetica", 6.3)
    ty -= 13.5
    rows = [("EARN", [f"+{duel_win}  win any duel",
                      f"+{guard_reward}  guard post: roll {guard_roll}+"]),
            ("SPEND", [f"-{support_cost}  a faction's support",
                       f"-{contest_fee}  fee to contest a claim"]),
            ("LOSE", [f"-{duel_loss}  to the bank when you lose a duel"])]
    for label, lines in rows:
        c.setFont("Helvetica-Bold", 6.8)
        c.drawString(cx * mm, ty * mm, label)
        for line in lines:
            size = _fit(c, line, "Times-Roman", 8.6, colw - 12)
            c.setFont("Times-Roman", size)
            c.drawString((cx + 11) * mm, ty * mm, line)
            ty -= 4.4
        ty -= 1.4

    # Column 3: supports, the claim window, and the turn.
    cx, ty = cols[2], y0
    _mat_head(c, cx, ty, colw,
              f"SUPPORT - {count_word(req)} different to proclaim")
    ty -= 7.6
    for faction in v["factions"]:
        name, sym = FACTION_DISPLAY[faction], _FACTION_CARDS[faction][1]
        checkbox(c, cx, ty - 0.6, 4.0)
        c.setFont("Times-Bold", 9.2)
        c.drawString((cx + 5.6) * mm, ty * mm, name)
        sx = cx + colw - 4
        c.setLineWidth(0.8)
        if sym == "shield":
            _shield(c, sx * mm, (ty + 1.4) * mm, 2.4 * mm)
        elif sym == "column":
            _column(c, sx * mm, (ty + 1.6) * mm, 2.2 * mm)
        else:
            _laurel(c, sx * mm, (ty + 1.6) * mm, 2.6 * mm)
        ty -= 6.2
    ty -= 2.6
    # A claim proclaimed in round R wins at the end of round R + window.
    _mat_head(c, cx, ty, colw, "CLAIM WINDOW")
    ty -= 6.2
    for line in ("A claim wins at the END of the",
                 f"{ordinal_word(win)} full round AFTER its proclaim round."):
        c.setFont("Times-Roman", _fit(c, line, "Times-Roman", 8.4, colw))
        c.drawString(cx * mm, ty * mm, line)
        ty -= 4.2
    ty -= 2.2
    c.setFont("Times-Roman", 8.4)
    c.drawString(cx * mm, ty * mm, "Proclaimed round ____  wins ____")
    ty -= 5.6
    c.drawString(cx * mm, ty * mm, f"Contest: fee {contest_fee}, within "
                                   f"{duel_range} circles.")
    ty -= 5.6
    c.setFont("Times-Bold", 8.4)
    c.drawString(cx * mm, ty * mm, f"Your turn: roll {dice} dice, move, one action.")

    # The road to the throne: the whole game in five steps.
    c.setLineWidth(0.8)
    c.line((x + 4) * mm, (y + 21.5) * mm, (x + w - 4) * mm, (y + 21.5) * mm)
    c.setFont("Helvetica-Bold", 7.8)
    c.drawString((x + 4) * mm, (y + 16.5) * mm, "THE ROAD TO THE THRONE")
    steps = [("PALACE MAP", f"Collect all {count_word(v['items_required'])} items"),
             ("PALACE MAP", "Claim at the Peristyle"),
             ("SUCCESSION MAP", "Search the ? cards"),
             ("SUCCESSION MAP", f"Buy {count_word(req)} different supports"),
             ("SUCCESSION MAP", "Proclaim, then hold the claim")]
    sx0 = x + 4
    sw = (w - 8 - 4 * 3.0) / 5.0
    for i, (where, what) in enumerate(steps):
        bx = sx0 + i * (sw + 3.0)
        c.setLineWidth(0.6)
        c.roundRect(bx * mm, (y + 4.5) * mm, sw * mm, 9.6 * mm, 1.4 * mm)
        _centered(c, bx + sw / 2, y + 10.6, f"{i + 1}  {where}", "Helvetica-Bold", 5.8)
        size = _fit(c, what, "Times-Roman", 8.0, sw - 2)
        _centered(c, bx + sw / 2, y + 6.4, what, "Times-Roman", size)
        if i < 4:
            ax = bx + sw + 0.4
            p = c.beginPath()
            p.moveTo(ax * mm, (y + 10.3) * mm)
            p.lineTo((ax + 2.2) * mm, (y + 9.3) * mm)
            p.lineTo(ax * mm, (y + 8.3) * mm)
            p.close()
            c.drawPath(p, stroke=0, fill=1)


def player_sheets_pdf(path, rules):
    c = new_doc(path, f"{PRODUCT} - player sheets")
    for page in range(2):
        doc_header(c, "PLAYER SHEETS", "one mat per player - pencil ticks, one counter on the Prestige track")
        w, h = PW - 32.0, 114.0
        y0 = PH - 40 - h
        for i, numeral in enumerate(("I", "II") if page == 0 else ("III", "IV")):
            player_mat(c, 16.0, y0 - i * (h + 8), w, h, numeral, rules)
        doc_footer(c, page + 1, 2)
        c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Cards and tokens.

CARD_W, CARD_H = 55.0, 75.0
# Card rows for the committed art edition; the drawn editions rebuild
# these from the rules JSON passed into the PDF functions.
CARDS = treasure_card_rows(_DEFAULT_RULES)


def draw_equipment_icon(c, kind, x, y, s):
    """Simple line icons, all within a box of size s centred on (x, y)."""
    c.setLineWidth(1.3)
    if kind == "dagger":
        p = c.beginPath()
        p.moveTo(x * mm, (y + s * 0.45) * mm)
        p.lineTo((x - s * 0.10) * mm, (y - s * 0.05) * mm)
        p.lineTo(x * mm, (y - s * 0.18) * mm)
        p.lineTo((x + s * 0.10) * mm, (y - s * 0.05) * mm)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line(x * mm, (y - s * 0.18) * mm, x * mm, (y - s * 0.34) * mm)
        c.line((x - s * 0.14) * mm, (y - s * 0.30) * mm, (x + s * 0.14) * mm, (y - s * 0.30) * mm)
        c.line(x * mm, (y - s * 0.34) * mm, x * mm, (y - s * 0.46) * mm)
    elif kind == "pilum":
        c.line(x * mm, (y - s * 0.42) * mm, x * mm, (y + s * 0.30) * mm)
        p = c.beginPath()
        p.moveTo(x * mm, (y + s * 0.48) * mm)
        p.lineTo((x - s * 0.07) * mm, (y + s * 0.28) * mm)
        p.lineTo((x + s * 0.07) * mm, (y + s * 0.28) * mm)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line((x - s * 0.14) * mm, (y - s * 0.10) * mm, (x + s * 0.14) * mm, (y - s * 0.10) * mm)
    elif kind == "helmet":
        p = c.beginPath()
        p.moveTo((x - s * 0.30) * mm, (y - s * 0.05) * mm)
        p.curveTo((x - s * 0.30) * mm, (y + s * 0.42) * mm, (x + s * 0.30) * mm,
                  (y + s * 0.42) * mm, (x + s * 0.30) * mm, (y - s * 0.05) * mm)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line((x - s * 0.34) * mm, (y - s * 0.05) * mm, (x + s * 0.34) * mm, (y - s * 0.05) * mm)
        c.line((x - s * 0.34) * mm, (y - s * 0.05) * mm, (x - s * 0.34) * mm, (y - s * 0.30) * mm)
        c.line((x + s * 0.34) * mm, (y - s * 0.05) * mm, (x + s * 0.34) * mm, (y - s * 0.18) * mm)
    elif kind == "scutum":
        p = c.beginPath()
        p.moveTo((x - s * 0.22) * mm, (y + s * 0.42) * mm)
        p.curveTo((x - s * 0.40) * mm, (y + s * 0.10) * mm, (x - s * 0.40) * mm,
                  (y - s * 0.28) * mm, (x - s * 0.22) * mm, (y - s * 0.42) * mm)
        p.moveTo((x + s * 0.22) * mm, (y + s * 0.42) * mm)
        p.curveTo((x + s * 0.40) * mm, (y + s * 0.10) * mm, (x + s * 0.40) * mm,
                  (y - s * 0.28) * mm, (x + s * 0.22) * mm, (y - s * 0.42) * mm)
        c.drawPath(p, stroke=1, fill=0)
        c.line((x - s * 0.31) * mm, (y + s * 0.28) * mm, (x - s * 0.31) * mm, (y - s * 0.30) * mm)
        c.line((x + s * 0.31) * mm, (y + s * 0.28) * mm, (x + s * 0.31) * mm, (y - s * 0.30) * mm)
        c.line((x - s * 0.22) * mm, (y + s * 0.42) * mm, (x + s * 0.22) * mm, (y + s * 0.42) * mm)
        c.line((x - s * 0.24) * mm, (y - s * 0.40) * mm, (x + s * 0.24) * mm, (y - s * 0.40) * mm)
    elif kind == "gladius":
        p = c.beginPath()
        p.moveTo(x * mm, (y + s * 0.48) * mm)
        p.lineTo((x - s * 0.06) * mm, (y - s * 0.10) * mm)
        p.lineTo((x + s * 0.06) * mm, (y - s * 0.10) * mm)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line((x - s * 0.16) * mm, (y - s * 0.14) * mm, (x + s * 0.16) * mm, (y - s * 0.14) * mm)
        c.line(x * mm, (y - s * 0.14) * mm, x * mm, (y - s * 0.36) * mm)
        c.circle(x * mm, (y - s * 0.40) * mm, s * 0.05 * mm)
    elif kind == "armor":
        p = c.beginPath()
        p.moveTo((x - s * 0.26) * mm, (y + s * 0.42) * mm)
        p.lineTo((x + s * 0.26) * mm, (y + s * 0.42) * mm)
        p.lineTo((x + s * 0.22) * mm, (y - s * 0.42) * mm)
        p.lineTo((x - s * 0.22) * mm, (y - s * 0.42) * mm)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        for dy in (0.24, 0.06, -0.12, -0.30):
            c.line((x - s * (0.24 - abs(dy) * 0.06)) * mm, (y + s * dy) * mm,
                   (x + s * (0.24 - abs(dy) * 0.06)) * mm, (y + s * dy) * mm)


def cards_tokens_pdf(path, rules):
    c = new_doc(path, f"{PRODUCT} - cards and tokens")
    v = printed_values(rules)
    cards = treasure_card_rows(rules)
    letters = sorted(rules["palace"]["map"]["treasure_entries"])
    first, last = letters[0], letters[-1]
    up = v["start_face_up"]
    if rules["treasures"]["abilities"]["pugio"]["type"] != "win_ties":
        raise SystemExit("printed card notes call the pugio a tie-break; "
                         "update the kit prose")

    # Page 1: the treasure location cards.
    doc_header(c, "TREASURE LOCATION CARDS", "cut on the outer border - identical backs on the next page")
    x0, y0 = 16.0, PH - 32.5 - CARD_H
    for i, (name, icon, flavor) in enumerate(cards):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        c.setLineWidth(1.6)
        c.rect(cx * mm, cy * mm, CARD_W * mm, CARD_H * mm)
        c.setLineWidth(0.5)
        c.rect((cx + 2.0) * mm, (cy + 2.0) * mm, (CARD_W - 4.0) * mm, (CARD_H - 4.0) * mm)
        # An arch frames the larger equipment drawing without a solid fill.
        c.setLineWidth(0.6)
        mid = cx + CARD_W / 2.0
        frame = c.beginPath()
        frame.moveTo((mid - 19) * mm, (cy + 28) * mm)
        frame.lineTo((mid - 19) * mm, (cy + 47) * mm)
        frame.curveTo((mid - 19) * mm, (cy + 68) * mm,
                      (mid + 19) * mm, (cy + 68) * mm,
                      (mid + 19) * mm, (cy + 47) * mm)
        frame.lineTo((mid + 19) * mm, (cy + 28) * mm)
        frame.close()
        c.drawPath(frame, stroke=1, fill=0)
        draw_equipment_icon(c, icon, cx + CARD_W / 2.0, cy + 45.0, 31.0)
        c.setLineWidth(0.6)
        c.line((cx + 7) * mm, (cy + 25) * mm,
               (cx + CARD_W - 7) * mm, (cy + 25) * mm)
        _centered(c, cx + CARD_W / 2.0, cy + 20.0, name.upper(), "Times-Bold", 10.5)
        # The ability text may run to several lines (the pugio card spells
        # out the both-or-neither case); keep it inside the frame above the
        # footer line by stepping the size down before it grows past three
        # lines.
        size = 7.0
        lines = wrap_lines(c, flavor, CARD_W - 10.0, size=size, font="Times-Italic")
        while len(lines) > 3 and size > 5.8:
            size -= 0.2
            lines = wrap_lines(c, flavor, CARD_W - 10.0, size=size, font="Times-Italic")
        fy = cy + 13.5 + (len(lines) - 1) * 1.7
        for ln in lines:
            _centered(c, cx + CARD_W / 2.0, fy, ln, "Times-Italic", size)
            fy -= 3.4
        _centered(c, cx + CARD_W / 2.0, cy + 5.5, "PALACE TREASURE - LOCATION CARD",
                  "Helvetica", 5.2)
    y = y0 - (CARD_H + 5.0) - 9.0
    para(c, f"Shuffle face down and deal one card to each treasure entry "
            f"{first}-{last}. Then turn {count_word(up)} of the "
            f"{count_word(len(cards))} face up at random - everyone sees "
            f"those {count_word(up)} treasures from the start. Each card "
            f"states its ability; in a duel count one best number bonus "
            f"per side, never a sum - the pugio is a tie-break, not a "
            f"number bonus, and it works next to the one you counted.",
         16, y, PW - 32, size=8.4)
    doc_footer(c, 1)
    c.showPage()

    # Page 2: identical card backs (print single-sided, then fold or glue).
    doc_header(c, "CARD BACKS", f"{count_word(len(cards))} identical tiles - glue or fold behind each card")
    for i in range(len(cards)):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        c.setLineWidth(1.2)
        c.rect(cx * mm, cy * mm, CARD_W * mm, CARD_H * mm)
        c.setLineWidth(0.5)
        c.rect((cx + 2.6) * mm, (cy + 2.6) * mm, (CARD_W - 5.2) * mm, (CARD_H - 5.2) * mm)
        c.setLineWidth(0.9)
        _laurel(c, (cx + CARD_W / 2.0) * mm, (cy + CARD_H / 2.0 + 3.5) * mm, 12.5 * mm)
        _centered(c, cx + CARD_W / 2.0, cy + CARD_H / 2.0 - 10.5,
                  "IMPERIAL", "Times-Bold", 9.5)
        _centered(c, cx + CARD_W / 2.0, cy + CARD_H / 2.0 - 15.5,
                  "RIVALS", "Times-Bold", 9.5)
    doc_footer(c, 2)
    c.showPage()

    # Page 3: pawns, prestige, support markers, claim marker, phase track.
    doc_header(c, "TOKENS", "cut out - fold the pawns and tape them upright")
    y = PH - 42
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(16 * mm, y * mm, "PLAYER PAWNS (fold in half, tape or glue)")
    y -= 30
    for i, numeral in enumerate(("I", "II", "III", "IV")):
        px = 18.0 + i * 44.0
        c.setLineWidth(1.4)
        c.rect(px * mm, y * mm, 34.0 * mm, 26.0 * mm)
        c.setLineWidth(0.5)
        c.line((px + 17.0) * mm, y * mm, (px + 17.0) * mm, (y + 26.0) * mm)
        c.setDash(2, 2)
        c.line(px * mm, y * mm, (px + 34.0) * mm, y * mm)
        c.setDash()
        c.setFont("Times-Bold", 20)
        c.drawCentredString((px + 8.5) * mm, (y + 9.5) * mm, numeral)
        c.drawCentredString((px + 25.5) * mm, (y + 9.5) * mm, numeral)
        c.setFont("Helvetica", 4.8)
        c.drawCentredString((px + 8.5) * mm, (y + 4.0) * mm, "fold")
    y -= 12
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(16 * mm, y * mm, "PRESTIGE COUNTERS (16)")
    y -= 10
    for i in range(16):
        px = 20.0 + (i % 8) * 22.0
        py = y - (i // 8) * 20.0
        c.setLineWidth(1.0)
        c.circle(px * mm, py * mm, 7.6 * mm)
        _centered(c, px, py + 1.3, "1", "Times-Bold", 10)
        _centered(c, px, py - 3.2, "PRESTIGE", "Helvetica", 4.2)
    y -= 46
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(16 * mm, y * mm, "FACTION SUPPORT MARKERS (2 of each)")
    y -= 6
    kinds = tuple(_FACTION_CARDS[f] for f in v["factions"])
    for i, (label, sym) in enumerate(kinds):
        px = 24.0 + i * 58.0
        for j in range(2):
            cx = px + j * 20.0
            c.setLineWidth(1.0)
            c.circle(cx * mm, (y - 4) * mm, 7.6 * mm)
            c.setLineWidth(0.9)
            if sym == "shield":
                _shield(c, cx * mm, (y - 3.6) * mm, 4.2 * mm)
            elif sym == "column":
                _column(c, cx * mm, (y - 3.2) * mm, 3.8 * mm)
            else:
                _laurel(c, cx * mm, (y - 3.2) * mm, 4.4 * mm)
    y -= 24
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(16 * mm, y * mm, "PENDING CLAIM MARKER")
    c.setLineWidth(1.6)
    c.rect(18 * mm, (y - 22) * mm, 44.0 * mm, 20.0 * mm)
    _centered(c, 40, y - 11.0, "CLAIM", "Times-Bold", 13)
    _centered(c, 40, y - 17.0, "pending", "Helvetica", 6)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(76 * mm, y * mm, "FIRST CHALLENGER MARKER")
    c.setLineWidth(1.6)
    c.rect(78 * mm, (y - 22) * mm, 44.0 * mm, 20.0 * mm)
    _centered(c, 100, y - 11.0, "FIRST", "Times-Bold", 12)
    _centered(c, 100, y - 17.0, "challenger", "Helvetica", 6)
    c.setFont("Times-Roman", 7.6)
    c.drawString(130 * mm, (y - 4) * mm, "Place FIRST CHALLENGER on the board when a player")
    c.drawString(130 * mm, (y - 9) * mm, "claims the checkpoint. It marks the round when the")
    c.drawString(130 * mm, (y - 14) * mm, "succession phase will begin.")

    y -= 34
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(16 * mm, y * mm, "ROUND AND PHASE TRACK")
    y -= 5
    c.setFont("Times-Roman", 8)
    c.drawString(16 * mm, y * mm, f"City phase (max {v['city_rounds']} rounds):")
    for i in range(v["city_rounds"]):
        box(c, 58.0 + i * 5.6, y - 1.6, 4.6, 5.2, lw=0.7)
        if (i + 1) % 6 == 0:
            c.setFont("Helvetica", 4.6)
            c.drawCentredString((60.3 + i * 5.6) * mm, (y - 5.4) * mm, str(i + 1))
    y -= 10
    c.setFont("Times-Roman", 8)
    c.drawString(16 * mm, y * mm,
                 f"Succession phase (max {v['succession_rounds']} rounds):")
    for i in range(v["succession_rounds"]):
        box(c, 58.0 + i * 5.6, y - 1.6, 4.6, 5.2, lw=0.7)
    y -= 8
    grace = v["grace"]
    c.setFont("Times-Italic", 7.4)
    c.drawString(16 * mm, y * mm,
                 f"The city phase ends {grace} full round{'' if grace == 1 else 's'} "
                 f"after the first checkpoint claim (or at round {v['city_rounds']}). "
                 f"Track rounds only if you use the {v['city_rounds']}-round limits.")
    doc_footer(c, 3)
    c.showPage()

    # The next pages: the faction cards and their backs.
    faction_cards_pages(c, first_page=4, rules=rules)
    c.save()


# Faction card rows for the committed art edition; the drawn editions
# rebuild these from the rules JSON passed into the PDF functions.
FACTION_CARDS = faction_card_rows(_DEFAULT_RULES)


def _faction_badge(c, kind, x, y, r):
    c.setLineWidth(1.4)
    if kind == "shield":
        _shield(c, x * mm, y * mm, r * mm)
    elif kind == "column":
        _column(c, x * mm, y * mm, r * 0.9 * mm)
    elif kind == "laurel":
        _laurel(c, x * mm, y * mm, r * mm)


def faction_cards_pages(c, first_page, rules):
    """The faction deck from the rules JSON, and its identical backs."""
    cards = faction_card_rows(rules)
    support_cost = rules["succession"]["support_cost"]
    x0, y0 = 16.0, PH - 32.5 - CARD_H
    doc_header(c, "FACTION CARDS", "for the succession map - identical backs on the next page")
    for i, (name, badge, line1, line2) in enumerate(cards):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        mid = cx + CARD_W / 2.0
        c.setLineWidth(1.6)
        c.rect(cx * mm, cy * mm, CARD_W * mm, CARD_H * mm)
        c.setLineWidth(0.5)
        c.rect((cx + 2.0) * mm, (cy + 2.0) * mm, (CARD_W - 4.0) * mm, (CARD_H - 4.0) * mm)
        c.setLineWidth(0.8)
        c.circle(mid * mm, (cy + 46.0) * mm, 17.0 * mm)
        if badge:
            _faction_badge(c, badge, mid, cy + 46.0, 11.0)
        else:
            # A blank: an empty street circle, dashed.
            c.setDash(2, 2)
            c.circle(mid * mm, (cy + 46.0) * mm, 9.0 * mm)
            c.setDash()
        c.setLineWidth(0.6)
        c.line((cx + 7) * mm, (cy + 25) * mm, (cx + CARD_W - 7) * mm, (cy + 25) * mm)
        _centered(c, mid, cy + 19.0, name, "Times-Bold", 11)
        _centered(c, mid, cy + 13.0, line1, "Times-Italic", 7.6)
        _centered(c, mid, cy + 9.0, line2, "Times-Italic", 7.6)
        _centered(c, mid, cy + 4.5, "SUCCESSION - FACTION CARD", "Helvetica", 5.2)
    y = y0 - (CARD_H + 5.0) - 9.0
    para(c, f"Keep these {count_word(len(cards))} cards aside during the palace "
            f"phase. At the change, shuffle them face down and put one on each "
            f"card space - the circles marked ? on the succession map. End your "
            f"move on a card space and turn its card face up: that is a search. "
            f"A face-up faction card stays on the map; stop there and pay "
            f"{support_cost} Prestige for that faction's support.",
         16, y, PW - 32, size=8.4)
    doc_footer(c, first_page)
    c.showPage()

    doc_header(c, "FACTION CARD BACKS",
               f"{count_word(len(cards))} identical tiles - glue or fold behind each card")
    for i in range(len(cards)):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        mid = cx + CARD_W / 2.0
        c.setLineWidth(1.2)
        c.rect(cx * mm, cy * mm, CARD_W * mm, CARD_H * mm)
        c.setLineWidth(0.5)
        c.rect((cx + 2.6) * mm, (cy + 2.6) * mm, (CARD_W - 5.2) * mm, (CARD_H - 5.2) * mm)
        # Three small badges round a large '?': unmistakably not a
        # treasure card back (those carry one large laurel).
        c.setLineWidth(1.4)
        c.circle(mid * mm, (cy + 42.0) * mm, 15.0 * mm)
        _centered(c, mid, cy + 35.5, "?", "Times-Bold", 46)
        for kind, dx in (("shield", -14.0), ("column", 0.0), ("laurel", 14.0)):
            c.setLineWidth(0.9)
            _faction_badge(c, kind, mid + dx, cy + 17.0, 3.6)
        _centered(c, mid, cy + 8.0, "FACTION CARD", "Times-Bold", 9.5)
    doc_footer(c, first_page + 1)
    c.showPage()


# ---------------------------------------------------------------------------
# The drawn kit: the same geometry with the hand-drawn art from art/.
# Assets are produced by:
#   python3 art/export_layout.py
#   cd art && npm ci && node render.mjs
# and land in art/build/assets/. Missing assets fail loudly; the
# black-and-white kit never depends on them.

# The full-colour edition is the same drawing with watercolour glazes,
# rendered with `node render.mjs --color` into art/build/assets-color/.
# It uses the same layout, tiling, and cut furniture as the drawn kit.

ART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "art", "build", "assets")
COLOR_ART_DIR = ART_DIR + "-color"


def art_asset(name, asset_dir=ART_DIR):
    path = os.path.join(asset_dir, name)
    if not os.path.exists(path):
        flag = " --color" if asset_dir == COLOR_ART_DIR else ""
        raise SystemExit(
            f"art asset {name} not found under {asset_dir}. Build it first:\n"
            f"  python3 art/export_layout.py && (cd art && npm ci && node render.mjs{flag})")
    return path


def art_board_pdf(path, L, asset_dir=ART_DIR, label="drawn art"):
    """The palace board with the drawn artwork under the same tiling."""
    art_tiled_pdf(path, L, "palace-board.png", f"{PRODUCT} - board (4 x A4, {label})",
                  asset_dir)


def art_tiled_pdf(path, L, asset, title, asset_dir=ART_DIR):
    """A full-board artwork tiled onto four A4 pages under the BW furniture."""
    img = art_asset(asset, asset_dir)
    ax0, ay0, ax1, ay1 = L["art"]
    c = pdfcanvas.Canvas(path, pagesize=landscape(A4))
    c.setTitle(title)
    c.setAuthor("dioclet print kit")
    for page_no in ("1", "2", "3", "4"):
        x0, y0, _ = L["tiles"][page_no]
        c.saveState()
        p = c.beginPath()
        p.rect(0, 0, PAGE_W * mm, PAGE_H * mm)
        c.clipPath(p, stroke=0, fill=0)
        # Shift artwork coordinates into this tile's window first, as
        # board_pdf does, so each page shows its own quarter. The PNG
        # row 0 is the north edge, so it maps directly onto the
        # rectangle from ay0 (south) to ay1 (north).
        c.translate(-x0 * mm, -y0 * mm)
        c.drawImage(img, ax0 * mm, ay0 * mm, width=(ax1 - ax0) * mm,
                    height=(ay1 - ay0) * mm)
        c.restoreState()
        # Cut guides and registration crosses on top of the art, exactly
        # where the black-and-white tiles print them. The furniture
        # takes page coordinates; it subtracts the tile origin itself.
        draw_tile_furniture(c, L, page_no, (x0, y0))
        c.showPage()
    c.save()


def art_succession_pdf(path, S, asset_dir=ART_DIR, label="drawn art"):
    """The succession map: same footprint, tiles and cut lines as the board."""
    art_tiled_pdf(path, S, "succession-map.png",
                  f"{PRODUCT} - succession map (4 x A4, {label})", asset_dir)


def art_cards_tokens_pdf(path, asset_dir=ART_DIR, label="drawn art"):
    """Card fronts with bleed, identical art backs, and the token sheet."""
    c = new_doc(path, f"{PRODUCT} - cards and tokens ({label})")
    art_asset_here = lambda name: art_asset(name, asset_dir)
    back = art_asset_here("card-back.png")
    cards = [art_asset_here(f"card-{i + 1}-{icon}.png")
             for i, (_n, icon, _t) in enumerate(CARDS)]

    # Page 1: the six fronts. The PNGs carry a 2 mm bleed margin, so the
    # image anchor sits 2 mm outside the cut rectangle.
    doc_header(c, "TREASURE LOCATION CARDS", "cut on the dashed line - art backs on the next page")
    x0, y0 = 16.0, PH - 32.5 - CARD_H
    for i in range(6):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        c.drawImage(cards[i], (cx - 2.0) * mm, (cy - 2.0) * mm,
                    width=(CARD_W + 4.0) * mm, height=(CARD_H + 4.0) * mm)
    doc_footer(c, 1)
    c.showPage()

    # Page 2: six identical backs, square to the fronts.
    doc_header(c, "CARD BACKS", "glue or fold behind each card - all six are identical")
    for i in range(6):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        c.drawImage(back, (cx - 2.0) * mm, (cy - 2.0) * mm,
                    width=(CARD_W + 4.0) * mm, height=(CARD_H + 4.0) * mm)
    doc_footer(c, 2)
    c.showPage()

    # Page 3: the token sheet, cut guides drawn into the art.
    doc_header(c, "TOKENS", "cut on the dashed lines - fold the pawns and tape them upright")
    c.drawImage(art_asset_here("tokens-sheet.png"), 0, 0, width=PW * mm, height=PH * mm)
    doc_footer(c, 3)
    c.showPage()

    # Pages 4 and 5: the faction cards and their shared back.
    fronts = [art_asset_here(f"faction-{kind}.png") for kind in ("army", "officials", "elites")]
    fronts += [art_asset_here(f"faction-empty-{n}.png") for n in (1, 2, 3)]
    doc_header(c, "FACTION CARDS", "for the succession map - art backs on the next page")
    for i in range(6):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        c.drawImage(fronts[i], (cx - 2.0) * mm, (cy - 2.0) * mm,
                    width=(CARD_W + 4.0) * mm, height=(CARD_H + 4.0) * mm)
    y = y0 - (CARD_H + 5.0) - 9.0
    para(c, "Keep these six cards aside during the palace phase. At the change, shuffle "
            "them face down and put one on each card space - the circles marked ? on the "
            "succession map. End your move on a card space and turn its card face up: "
            "that is a search.", 16, y, PW - 32, size=8.4)
    doc_footer(c, 4)
    c.showPage()
    doc_header(c, "FACTION CARD BACKS", "glue or fold behind each faction card - all six are identical")
    back = art_asset_here("faction-back.png")
    for i in range(6):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        c.drawImage(back, (cx - 2.0) * mm, (cy - 2.0) * mm,
                    width=(CARD_W + 4.0) * mm, height=(CARD_H + 4.0) * mm)
    doc_footer(c, 5)
    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Rulebook.

def rulebook_pages(rules):
    """The rulebook page list, with every rule number from the rules JSON."""
    v = printed_values(rules)
    east, gate_steps = twin_geometry(rules)
    a = rules["treasures"]["abilities"]
    dice, sides = v["dice"], v["die_sides"]
    cap = v["cap"]
    gr, gw = v["guard_roll"], v["guard_reward"]
    dw, dl = v["duel_win"], v["duel_loss"]
    rng, tie = v["duel_range"], v["tie_winner"]
    sc, cf = v["support_cost"], v["contest_fee"]
    req, win = v["factions_to_proclaim"], v["window"]
    city_rounds, succ_rounds = v["city_rounds"], v["succession_rounds"]
    grace, items_req = v["grace"], v["items_required"]
    items, up = v["items"], v["start_face_up"]
    n_items = len(items)
    factions = v["factions"]
    n_factions = len(factions)
    empty = v["empty_streets"]
    n_cards = n_factions + empty
    players = v["players"]
    letters = sorted(rules["palace"]["map"]["treasure_entries"])
    item_list = ", ".join(n.replace("_", " ") for n in items[:-1]) \
        + ", or " + items[-1].replace("_", " ")
    disp = [FACTION_DISPLAY[f] for f in factions]
    faction_list = ", the ".join(disp[:-1]) + " and the " + disp[-1]
    n_guard_posts = len(rules["succession"]["map"]["guard_posts"])
    return [
    ("The goal", [
        ("h", "What you are trying to do"),
        ("p", "305 AD. Diocletian has retired to his palace at Split, and "
              f"{count_word(players)} rivals prepare a claim to the throne. "
              "Collect equipment to become strong, earn Prestige to pay for help, and "
              f"win the support of {count_word(req)} of the {count_word(n_factions)} "
              f"factions in the city. Then stand at "
              "the Peristyle, the great crossing of the palace, and proclaim your claim. "
              f"If none of your {count_word(players - 1)} rivals can stop it, the throne is yours."),
        ("h", "What you need"),
        ("b", "This printed kit: the palace board and the succession map (four "
              "taped pages each, the same size), "
              f"{count_word(n_items)} treasure cards, {count_word(n_cards)} "
              "faction cards, the tokens, and one player sheet per person."),
        ("b", f"{count_word(dice).capitalize()} ordinary {count_word(sides)}-sided dice "
              f"for movement, and one {count_word(sides)}-sided die for "
              "fights (any die works for both - you just need "
              f"{count_word(dice + 1)} dice in total)."),
        ("b", "A small pawn per player. Coins or buttons work. The paper pawns in "
              "this kit also work."),
        ("b", f"About 45 to 75 minutes for {count_word(players)} players learning the game."),
        ("h", "How to set up"),
        ("n", "Assemble both boards (see the assembly sheet). Lay the palace map "
              f"face up; the succession map and the {count_word(n_cards)} faction cards "
              "wait until "
              "the succession begins. Each player picks a pawn and a player "
              "sheet, and writes their name on it."),
        ("n", f"Shuffle the {count_word(n_items)} treasure cards face down. Place one "
              f"on each treasure "
              f"entry, the double circles marked {letters[0]} to {letters[-1]}. Then turn "
              f"{count_word(up)} of the {count_word(n_items)} "
              f"face up at random - everyone sees those {count_word(up)} treasures "
              "from the start."),
        ("n", "Give each player a random gate: Golden (north), Silver (east), Bronze "
              "(south), or Iron (west). Put your pawn on your gate."),
        ("n", "Choose a starting player at random. The start moves one seat clockwise "
              "at the beginning of every round."),
    ]),
    ("Your turn", [
        ("h", "One turn, three steps"),
        ("n", f"Roll {count_word(dice)} dice. The total is the maximum number of steps you may take."),
        ("n", "Move your pawn along the street circles, one circle per step, north, "
              "south, east or west. You may stop before using the whole roll and you "
              "may pass through circles occupied by other pawns."),
        ("n", "Do one action where you stand - or do nothing. Taking treasure, "
              "standing guard, duelling, searching a faction card, gaining "
              "support, proclaiming and revealing a district (with the galea) "
              "are all actions. You never "
              "do two of these on the same turn."),
        ("h", "What counts as movement"),
        ("p", "The white circles are streets. The hatched blocks are buildings: "
              "nobody walks through them. All movement and all distances are counted "
              "along street circles, not across buildings."),
        ("p", "Guard duty and duels are actions of a moving turn: you must move at "
              "least one circle first. Taking treasure, searching a card, gaining "
              "support, claiming the checkpoint and proclaiming may be done "
              "without moving."),
        ("h", "Rounds and turns"),
        ("p", "A round is one turn for every player, in clockwise order from the "
              "starting player. After the last player, a new round begins and the "
              "start moves one seat clockwise, so nobody always plays first."),
    ]),
    ("Treasure and equipment", [
        ("h", f"The {count_word(n_items)} treasures"),
        ("p", f"Each treasure entry (double circle, {letters[0]} to {letters[-1]}) "
              f"holds one face-down card: "
              f"{item_list}. {count_word(up).capitalize()} of "
              f"the {count_word(n_items)} start face up. End your move on an entry to take that "
              "card's action: reveal the card to everyone and mark the item on "
              "your player sheet."),
        ("p", "Every player can collect every item once. The cards stay on the board "
              "face up once revealed; they are never taken away, stolen, or lost. If "
              "you are the first to stop at an entry, you learn for everyone what "
              "waits there."),
        ("h", "What each item does"),
        ("p", "Every item carries one ability that lasts the whole game:"),
        ("t", [["Item", "Mark", "Ability"],
               ["Gladius", "sword", f"+{a['gladius']['value']} to your attack in any duel you start"],
               ["Scutum", "shield", f"+{a['scutum']['value']} to your defense in any duel"],
               ["Pilum", "javelin", f"+{a['pilum']['value']} to your attack against the standing claimant"],
               ["Pugio", "dagger", "you win tied duels"],
               ["Galea", "helmet", "once per game, as your action: reveal any one "
                "face-down treasure card, wherever it is"],
               ["Lorica segmentata", "armor", "once per game: when your claim is "
                "beaten, keep your square instead of returning to your gate"]]),
        ("p", "In a duel each side adds at most one item bonus - the best one that "
              "applies, never a sum. The gladius, the pilum and the scutum are "
              "number bonuses: they never stack. If you hold both the gladius and "
              f"the pilum and attack the claimant, you still add only +{a['gladius']['value']}."),
        ("p", "The pugio is not a number bonus. It is a passive tie-break that "
              "works by itself, next to your chosen number bonus, whenever the two "
              "final duel totals are equal - gladius and pugio together are legal, "
              f"gladius and pilum together still add only +{a['gladius']['value']}. Cross an item out on "
              "your sheet when its once-per-game ability is used."),
        ("p", "Collecting happens only while the palace phase lasts. When the "
              "succession begins the palace map leaves the table and your items "
              "are fixed - what you hold is what you fight with. Nothing is ever "
              "granted for free: if you want an item, walk and get it in time."),
    ]),
    ("Prestige", [
        ("h", "Earning Prestige"),
        ("b", "Guard post (star, on both maps): end a move there and roll one "
              f"die. A {gr}, {gr + 1} or {gr + 2} earns {gw} Prestige."),
        ("b", f"Win a duel: the winner of any duel earns {dw} Prestige."),
        ("p", f"You can hold at most {cap} Prestige. Any reward above "
              f"{count_word(cap)} is lost - "
              "spend it or waste it."),
        ("h", "Duels"),
        ("p", f"End your move within {count_word(rng)} street circles of a rival and you may duel "
              "them as your action. Resolve the duel in this order:"),
        ("n", "Both players roll one die."),
        ("n", "Each side adds its one best item bonus for that side - never a sum. "
              "The pugio adds no number; do nothing with it yet."),
        ("n", "Compare the final totals. The higher total wins the duel."),
        ("n", "Only if the totals are equal, apply the tie-break: if exactly one "
              "side holds the pugio, that side wins. If both or neither hold one, "
              f"the tie is ordinary - on a tie the {tie} wins."),
        ("n", f"The winner earns {dw} Prestige. The loser pays {dl} Prestige to the bank "
              "as shame, as much as they hold. Nobody loses equipment or support."),
        ("h", "Spending Prestige"),
        ("b", f"{sc} Prestige: one faction's support (next page). Searching a "
              "faction card is free."),
        ("b", f"{cf} Prestige: the mandatory fee to contest a proclaimed claim (next page)."),
        ("p", "Keep 1 Prestige in reserve. A rival can proclaim at any time, and "
              "with 0 Prestige you cannot contest the claim - you can only watch "
              f"the {count_word(win)} round{'s' if win != 1 else ''} run out."),
    ]),
    ("Factions and the claim", [
        ("h", f"The {count_word(n_factions)} factions"),
        ("p", f"{count_word(n_factions).capitalize()} groups in the city can back "
              f"your claim: the {faction_list}. Nobody knows where they meet until "
              f"the succession begins. Their meeting places are hidden among "
              f"{count_word(n_cards)} "
              "faction cards on the succession map:"),
        ("t", [["Card", "Badge", "What it does"]]
              + [[disp[i], _FACTION_CARDS[faction][1],
                  f"support for {sc} Prestige, no roll"]
                 for i, faction in enumerate(factions)]
              + [["Empty street " f"({empty} cards)", "none",
                  "nothing - search another card"]]),
        ("h", "Searching the faction cards"),
        ("n", f"At the change, shuffle the {count_word(n_cards)} faction cards face down and put one "
              "on each card space - the circles marked ? on the succession map. "
              "Each block has one card space, in front of its door."),
        ("n", "End your move on a card space and turn its card face up as your "
              "action. That is a search. Everyone sees the card, and it stays "
              "face up for the rest of the game."),
        ("n", f"Stand on a face-up faction card and spend {sc} Prestige as your action "
              "to gain that faction's support. An empty street gives nothing."),
        ("p", "Every faction can support every player, but each faction supports "
              "each player only once. Support lasts the whole game. Faction cards "
              "exist only in the succession phase - during the palace phase "
              "nobody can sell you their backing."),
        ("h", "From the city to the succession"),
        ("p", "The game has two phases and two boards. In the palace phase everyone "
              "collects equipment and Prestige on the large board. The first player "
              f"who owns all {count_word(items_req)} items may stand at the Peristyle and claim the "
              "checkpoint as their action. Finish that round, then "
              f"{count_word(grace)} more full "
              f"round{'s' if grace != 1 else ''}, and the succession phase begins. If nobody claims by the end "
              f"of round {city_rounds}, the succession begins anyway."),
        ("p", "At the change, the palace map leaves the table: turn the board "
              "over, or set it aside. Deal the faction cards. Every pawn returns "
              "to its gate on the succession map - the same compass gate it started "
              "from - and keeps everything it owns: items, Prestige, and any "
              "support already gained. From now on all movement, support, duels "
              f"and claims happen on the succession map. Every gate there is "
              f"{count_word(gate_steps)} "
              "steps from the Peristyle. The succession map has the same streets "
              "and blocks as the palace map, but its Peristyle is in a different "
              f"place: the octagon in the middle of the centre street, "
              f"{count_word(east)} steps "
              f"east of the palace crossing. It also has {count_word(n_guard_posts)} guard posts of its "
              "own, and duels still pay, so a broke player can earn the "
              "contest fee again."),
        ("h", "Proclaiming a claim"),
        ("n", "During the succession phase, stand at the Peristyle with support from "
              f"{count_word(req)} different factions."),
        ("n", "Use your action to proclaim your claim. Place the CLAIM marker on the "
              "Peristyle. Only one claim can stand at a time."),
        ("n", f"Your claim now stands inside a {count_word(win)}-round window. Rivals may cancel it "
              "only by winning a challenge duel (next page). Turns that pass "
              "without a challenge no longer crown anyone by themselves."),
        ("n", "If your turn comes while your claim stands and you are still at the "
              "Peristyle, you may maintain the claim as your action and stay put. "
              "Leaving the Peristyle by your own move cancels your claim."),
        ("n", f"If no rival cancels your claim before {full_rounds(win)} have passed, "
              "you are emperor and the game ends."),
    ]),
    ("Contesting a claim", [
        ("h", "How to contest"),
        ("p", "A rival can stop a claim by winning a challenge duel against the "
              f"claimant. To do it, end your move within {count_word(rng)} street "
              "circles of the claimant and duel them. Challenging a standing claim "
              f"costs a mandatory fee of {cf} Prestige, paid before you roll - even if "
              f"you lose. Without at least {cf} Prestige you cannot contest at all."),
        ("p", "The challenge itself is a normal duel, resolved in the five steps "
              "under Duels: one die each, your one best item bonus, then the "
              "tie-break if the totals match. A full challenge costs only the "
              f"{cf} Prestige fee."),
        ("h", "What happens on each result"),
        ("b", "You win: the claim is canceled. The claimant's pawn returns to their "
              "gate on the succession map - unless they have not used the lorica "
              "segmentata, which once per game lets a beaten claimant keep their "
              "square (the claim still dies). They keep all equipment, Prestige and "
              "support either way. The next claim may be proclaimed at any time."),
        ("b", "You lose: the claim stands. Your Prestige is spent either way, and "
              f"as in any duel the loser pays {dl} Prestige shame to the bank."),
        ("h", "An example challenge"),
        ("p", "Livia has proclaimed at the Peristyle with the Army and the elites "
              "behind her. Marcus, holding 2 Prestige, the gladius and the pilum, "
              f"moves next to the Peristyle. He pays the {cf} Prestige fee and duels. "
              f"His best item bonus is +{a['pilum']['value']} - the pilum also applies against a "
              "claimant, but one bonus only counts. He rolls 5 + 1 = 6. Livia "
              "holds the scutum and rolls 4 + 1 = 5. Marcus wins; the claim dies "
              f"and Livia pays {dl} Prestige shame. She has kept the lorica segmentata "
              "unused, so she stays at the Peristyle instead of walking back to her "
              f"gate on the succession map. Marcus earns {dw} Prestige for the duel "
              "win, leaving him with 2."),
        ("h", f"An example with all {count_word(items_req)} items"),
        ("p", f"Marcus challenges Livia's claim. Both players own all {count_word(items_req)} items. "
              f"Marcus attacks with the gladius (+{a['gladius']['value']}); Livia defends with the scutum "
              f"(+{a['scutum']['value']}). Both roll a 2, so both finish on 3. Each holds a pugio, so "
              "neither has the tie-break alone - the normal tie rule applies and "
              f"Marcus, the {tie}, wins. The claim is canceled, Livia pays {dl} "
              "Prestige shame, and she may still use the lorica segmentata to stay "
              f"at the Peristyle. Marcus earns {dw} Prestige."),
        ("h", "If nobody wins"),
        ("p", f"If no claim survives by the end of round {succ_rounds} of the succession phase, "
              "the game ends in a draw - the throne stays empty. This is rare."),
        ("h", "Remember"),
        ("b", "An ordinary duel is free. Challenging a claim always costs the "
              f"{cf} Prestige fee."),
        ("b", "Everything is public: positions, items, Prestige, support, and who "
              "has claimed what. Only the face-down treasure and faction cards and "
              "the next dice roll are hidden."),
    ]),
    ("Common questions", [
        ("q", "Can I pass through another pawn? Yes. Pawns never block a street."),
        ("q", "Can two pawns share a circle? Yes, any number may stand on one circle."),
        ("q", "Do I have to use my whole roll? No. Stop anywhere up to the total."),
        ("q", "Can I duel the claimant for free while no claim stands? Yes. Between "
              "claims the claimant is an ordinary rival and duels are free."),
        ("q", "Can I challenge the same claim twice? Yes - a failed challenge does "
              "not lock you out. Each attempt inside the window pays the fee again."),
        ("q", "What if both duelists hold the pugio? The normal tie rule applies: "
              f"the {tie} wins."),
        ("q", "Does the galea let me name an item? No. You name a district, not an "
              "item - the reveal turns up whatever card sits there."),
        ("q", f"What if I have {cap} Prestige and win a guard roll? Nothing happens - the cap is "
              f"{cap}. Spend some first."),
        ("q", "Can a faction support two different players? Yes - every faction can "
              "back every player once."),
        ("q", "What if I search an empty street? Nothing more happens. The card "
              "stays face up, so nobody searches there again."),
        ("q", "Can I proclaim twice? Yes, if your first claim is canceled, walk "
              "back and proclaim again. Support is never lost."),
        ("q", f"Can a claim be canceled after the window closes? No. "
              f"{full_rounds(win).capitalize()} unchallenged and the game is over."),
        ("q", f"Do treasures run out? No. Every player can mark each of the "
              f"{count_word(n_items)} items."),
        ("q", f"What if two players reach {count_word(items_req)} items on the same round? The first to "
              "claim at the Peristyle in turn order is the first challenger."),
        ("q", "Can we go back to the palace map once the succession begins? No. "
              "The change is one-way: from then on only the succession map is "
              "played."),
        ("q", "Which gate is mine on the succession map? The same compass gate "
              "you started from - Golden north, Silver east, Bronze south, Iron "
              "west."),
    ]),
    ]


def rulebook_pdf(path, rules):
    c = new_doc(path, f"{PRODUCT} - rulebook")
    page = 1
    doc_header(c, PRODUCT.upper(),
               f"{DESCRIPTOR} - rules for "
               f"{count_word(rules['game']['players'])} players")

    y = PH - 36
    c.setFont("Times-Bold", 11)
    c.drawString(22 * mm, y * mm, TAGLINE)
    y -= 6
    c.setFont("Times-Italic", 9.5)
    y = para(c, "Read pages 1 to 4 before the first turn. Use pages 5 to 8 for "
                "the succession phase and common questions.", 22, y, PW - 44)
    y -= 3

    def new_page():
        nonlocal page, y
        doc_footer(c, page)
        c.showPage()
        page += 1
        doc_header(c, f"{BRAND.upper()} - RULES", f"{EDITION} - {DESCRIPTOR}")
        y = PH - 36

    for section_index, (section_title, blocks) in enumerate(rulebook_pages(rules)):
        # Movement and equipment share a page; both are used each turn.
        if section_index and section_index != 2:
            new_page()
        elif section_index == 2:
            y -= 6
        y -= 2
        c.setFont("Times-Bold", 14)
        c.drawString(16 * mm, y * mm, section_title)
        y -= 3
        c.setLineWidth(0.8)
        c.line(16 * mm, y * mm, (PW - 16) * mm, y * mm)
        y -= 6
        step_number = 0
        for kind, content in blocks:
            if kind == "h":
                step_number = 0
                need = 12.0
            elif kind == "p":
                need = 11 * 1.38 / mm * len(wrap_lines(c, content, PW - 36, size=11)) + 2.0
            elif kind in ("b", "n"):
                need = 11 * 1.38 / mm * len(wrap_lines(c, content, PW - 41, size=11)) + 1.2
            elif kind == "q":
                rest = content.split("?", 1)[1] if "?" in content else ""
                need = 6.4 + 11 * 1.38 / mm * len(wrap_lines(c, rest.strip(), PW - 43, size=11))
            else:
                need = 7.4 * len(content) + 3.4
            if y - need < 24:
                new_page()
            if kind == "h":
                c.setFont("Times-Bold", 10.6)
                c.drawString(18 * mm, y * mm, content)
                y -= 5.6
            elif kind == "p":
                y = para(c, content, 18, y, PW - 36, size=11) - 3.0
            elif kind in ("b", "n", "q"):
                if kind == "n":
                    step_number += 1
                mark = {"b": "-", "n": f"{step_number}.", "q": "?"}[kind]
                if kind == "q":
                    c.setFont("Times-Bold", 11)
                    q = content.split("?")
                    c.drawString(18 * mm, y * mm, q[0] + "?")
                    rest = "?".join(q[1:]).strip()
                    y -= 5.4
                    if rest:
                        y = para(c, rest, 25, y, PW - 43, size=11) - 3.0
                else:
                    c.setFont("Times-Roman", 11)
                    c.drawString(18 * mm, y * mm, mark)
                    y = para(c, content, 23.5, y, PW - 41, size=11, indent=1.5) - 3.0
            elif kind == "t":
                rows, cols = content, len(content[0])
                widths = {2: (58.0, 118.0), 3: (44.0, 30.0, 102.0)}[cols]
                rh = 7.4
                for ri, row in enumerate(rows):
                    x = 18.0
                    for ci, cell_text in enumerate(row):
                        c.setLineWidth(0.7 if ri == 0 else 0.4)
                        c.rect(x * mm, (y - rh + 1.4) * mm, widths[ci] * mm, rh * mm)
                        c.setFont("Times-Bold" if ri == 0 else "Times-Roman", 8.8)
                        c.drawString((x + 2.2) * mm, (y - rh + 3.8) * mm, str(cell_text))
                        x += widths[ci]
                    y -= rh
                y -= 3.4
    doc_footer(c, page)
    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Quick reference, teaching guide, playtest form, print instructions.

def quick_reference_pdf(path, rules):
    c = new_doc(path, f"{PRODUCT} - quick reference")
    doc_header(c, "QUICK REFERENCE", "keep this beside the board")
    v = printed_values(rules)
    east, gate_steps = twin_geometry(rules)
    a = rules["treasures"]["abilities"]
    av, dv, pv = (a["gladius"]["value"], a["scutum"]["value"],
                  a["pilum"]["value"])
    dice, cap = v["dice"], v["cap"]
    gr, gw = v["guard_roll"], v["guard_reward"]
    dl = v["duel_loss"]
    sc, cf = v["support_cost"], v["contest_fee"]
    rng, tie = v["duel_range"], v["tie_winner"]
    req, win = v["factions_to_proclaim"], v["window"]
    city_rounds, succ_rounds = v["city_rounds"], v["succession_rounds"]
    grace, items_req = v["grace"], v["items_required"]
    factions = v["factions"]
    empty = v["empty_streets"]
    n_cards = len(factions) + empty
    y = PH - 36
    blocks = [
        ("YOUR TURN", [f"1. Roll {count_word(dice)} dice.", "2. Move up to the total; stop early if you like.",
                       "3. Do ONE action (or none): take treasure · guard duty · duel · "
                       "search a card · gain support · claim the checkpoint · proclaim · "
                       "maintain your claim."]),
        ("TWO MAPS", ["Palace map (large): treasures, the checkpoint claim.",
                      f"Claim the checkpoint: own ALL {count_word(items_req).upper()} items and "
                      f"stand at the Peristyle. "
                      f"The palace map ends {full_rounds(grace)} after the first claim, or after "
                      f"palace round {city_rounds} if nobody owns all {count_word(items_req)}.",
                      "Succession map (the back of the board): support, proclaiming, "
                      "the whole endgame. At the change everyone returns to their gate "
                      f"there. Its Peristyle is {east} steps EAST of the palace one; every "
                      f"gate is {gate_steps} steps from it."]),
        ("ROLLS", [f"Movement: {count_word(dice)} dice summed.",
                   f"Guard post: one die - {gr}+ earns {gw} Prestige (either map).",
                   "Duel: one die each + your one best item bonus; tie: the lone "
                   f"pugio holder wins, else the {tie}."]),
        ("EQUIPMENT (one best number bonus per side)", [
            f"Gladius +{av} attack · Scutum +{dv} defense · Pilum +{pv} vs the claimant.",
            "Pugio: lone holder wins ties (not a number bonus) · Galea once: "
            "reveal a district · Lorica once: stay when beaten."]),
        (f"PRESTIGE (cap {cap})", [f"Earn: guard post {gr}+ (either map) · any duel win.",
                              f"Spend: {sc} = faction support · {cf} = fee to contest a claim. "
                              "Searching is free.",
                              "Keep 1 in reserve: with 0 Prestige you cannot contest a claim.",
                              f"Lose: {dl} to the bank whenever you lose a duel."]),
        ("FACTION CARDS (succession map only)", [
            f"{count_word(n_cards).capitalize()} cards face down on the ? spaces: "
            f"{', '.join(factions)}, and "
            f"{count_word(empty)} empty streets.",
            "Search: end your move on a ? and turn the card face up (your action).",
            f"Support: on a face-up faction, {sc} Prestige, no roll. "
            f"{count_word(req).capitalize()} different "
            "factions needed to proclaim."]),
        ("PROCLAIM", [f"Succession phase, stand at the Peristyle, {req} supporters, "
                      "no other claim standing."]),
        ("CONTEST A CLAIM", [f"Move within {rng} circles of the claimant and duel them, "
                             "any turn inside the window.", f"Mandatory fee: {cf} Prestige "
                             "before you roll.", "Win: claim "
                             "canceled, claimant returns to their gate on the succession "
                             "map (lorica: stay put once), keeps everything."]),
        ("WINNING", [f"A claim that stands {full_rounds(win)} = emperor.",
                     f"No claim standing by succession round {succ_rounds} = draw."]),
    ]
    # The blocks must end above the footer rule (13 mm). Use the most
    # generous line pitch that fits; fail loudly if none does.
    wrapped = [[wrap_lines(c, line, 168.0, size=9.0, font="Helvetica") for line in lines]
               for _, lines in blocks]
    n_lines = sum(len(g) for groups in wrapped for g in groups)
    head, pad, gap, floor = 6.2, 4.0, 3.6, 16.0

    def bottom(pitch):
        return y - len(blocks) * (head + pad + gap) + gap - pitch * n_lines

    pitch = next((p for p in (5.6, 5.3, 5.0, 4.8, 4.6) if bottom(p) >= floor), None)
    if pitch is None:
        raise SystemExit("quick reference text does not fit on one page")
    for (title, _), groups in zip(blocks, wrapped):
        body_h = pitch * sum(len(group) for group in groups) + pad
        c.setLineWidth(1.1)
        c.rect(16 * mm, (y - head) * mm, (PW - 32) * mm, head * mm)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(18.5 * mm, (y - 4.4) * mm, title)
        y -= head
        c.setLineWidth(0.4)
        c.rect(16 * mm, (y - body_h) * mm, (PW - 32) * mm, body_h * mm)
        yy = y - 4.2
        c.setFont("Helvetica", 9.0)
        for group in groups:
            for line in group:
                c.drawString(19.5 * mm, yy * mm, line)
                yy -= pitch
        y = y - body_h - gap
    doc_footer(c, 1)
    c.showPage()
    c.save()


def teaching_guide_pdf(path, rules):
    c = new_doc(path, f"{PRODUCT} - five-minute teaching guide")
    page = 1
    doc_header(c, "TEACH IN FIVE MINUTES",
               "read aloud - seven steps, then two short demonstrations")
    v = printed_values(rules)
    a = rules["treasures"]["abilities"]
    av, dv, pv = (a["gladius"]["value"], a["scutum"]["value"],
                  a["pilum"]["value"])
    dice, cap = v["dice"], v["cap"]
    gr, gw = v["guard_roll"], v["guard_reward"]
    dw, dl = v["duel_win"], v["duel_loss"]
    sc, cf = v["support_cost"], v["contest_fee"]
    req, win = v["factions_to_proclaim"], v["window"]
    grace, items_req = v["grace"], v["items_required"]
    up, players = v["start_face_up"], v["players"]
    factions = v["factions"]
    n_factions, empty = len(factions), v["empty_streets"]
    n_cards = n_factions + empty
    letters = sorted(rules["palace"]["map"]["treasure_entries"])
    tie = v["tie_winner"]
    y = PH - 36
    steps = [
        ("The goal (30 seconds)", "Diocletian has retired and the throne is empty. "
         "You will collect gear, win friends, and try to crown yourself. The claim "
         f"your {count_word(players - 1)} rivals fail to stop inside "
         f"{count_word(win)} rounds wins the game."),
        ("Moving (30 seconds)", f"On your turn, roll {count_word(dice)} dice and move up to the "
         "total along the white circles. Streets only - the hatched blocks are "
         "buildings. Stop anywhere. Then do one thing. That is a whole turn."),
        ("Equipment (45 seconds)", f"The double circles {letters[0]} to {letters[-1]} each hold one piece "
         f"of gear - {count_word(up)} start face up. Stop on one and mark it on your sheet. Each "
         f"piece does one thing forever: the sword adds +{av} to attacks, the shield "
         f"+{dv} to defense, the javelin +{pv} against a claimant, the dagger breaks "
         "ties for its lone holder, the helmet reveals a district once, the "
         "armor saves you once. In a duel "
         "you count your one best bonus - never a sum."),
        ("Prestige (60 seconds)", "This coin symbol is Prestige - political clout. "
         f"Earn it at a star space: stop there, roll one die, {gr} or higher pays {gw}. "
         f"Win a duel: also {dw}. Lose a duel: pay {dl} back to the bank. You can hold "
         f"{count_word(cap)}. You will spend it on friends and on challenges."),
        ("Factions (45 seconds)", f"{count_word(n_factions).capitalize()} groups can back you - the Army, the "
         "officials, the city elites. Nobody knows where they meet. When the "
         f"succession begins, {count_word(n_cards)} faction cards go face down on the ? spaces of "
         f"the succession map - {count_word(n_factions)} factions, "
         f"{count_word(empty)} empty streets. Stop on a "
         f"card and turn it up. Find a faction and pay {sc} Prestige - it supports "
         f"you for the rest of the game. Get {count_word(req)} different factions behind you."),
        ("The endgame (60 seconds)", f"When someone holds all {count_word(items_req)} items they claim "
         "at the crossing - the Peristyle - and the succession begins: "
         f"{count_word(grace)} more "
         f"round{'s' if grace != 1 else ''}, then we turn the board over, and everyone starts again at their "
         "own gate. "
         "The whole race for the throne happens there: buy support, stand at the "
         f"Peristyle with {count_word(req)} backers and proclaim. Your rivals now have "
         f"{full_rounds(win)} "
         f"to stop you: move next to you, pay {cf} Prestige, and duel. Win the "
         "duel and the claim dies. Nobody does it in time and you are emperor."),
        ("Start (15 seconds)", "Random gates, random start, start moves clockwise "
         "each round. Youngest player rolls first if you like. Let's play."),
    ]
    for i, (title, text) in enumerate(steps, 1):
        c.setFont("Times-Bold", 11)
        c.drawString(16 * mm, y * mm, f"{i}. {title}")
        y -= 5.4
        y = para(c, f'"{text}"', 19, y, PW - 38, size=9.6, font="Times-Italic") - 2.6
    y -= 2
    c.setFont("Times-Bold", 11)
    c.drawString(16 * mm, y * mm, "Two tiny demonstrations")
    y -= 5.4
    y = para(c, "Ordinary turn: roll 8, walk eight circles to a star, roll one die - "
                "a 5 - and take a Prestige. Done.", 19, y, PW - 38, size=9.4) - 1.4
    y = para(c, "Claim response: a rival proclaims at the Peristyle. On your turn, "
                f"move next to them, put {cf} Prestige aside (the fee), then each roll "
                "one die and add your one best item bonus. Higher total wins; on a "
                f"tie the lone pugio holder wins, else the {tie}.",
             19, y, PW - 38, size=9.4) - 1.4
    y = para(c, "Answer everything else when it comes up. Rare cases live in the "
                "rulebook, not in the introduction.", 19, y, PW - 38, size=9.4,
             font="Times-Italic")
    doc_footer(c, page, 1)
    c.showPage()
    c.save()


def playtest_form_pdf(path, rules):
    c = new_doc(path, f"{PRODUCT} - playtest form")
    win = printed_values(rules)["window"]
    version = rules["game"]["rules_version"]
    for page in (1, 2):
        doc_header(c, "PLAYTEST RECORD", "observations only - no invented results")
        y = PH - 36
        date_line = (f"Date ______________    Game version V{version}    "
                     "Played before? yes / no")
        c.setFont("Times-Roman", 9)
        c.drawString(18 * mm, y * mm, date_line)
        y -= 6
        if page == 1:
            blocks = [
                ("GROUP", ["Players: ____    Ages: ______ ______ ______ ______",
                           "Group type: family with children / adult non-gamers / "
                           "strategy players / older first-timers",
                           "Minutes to explain the rules: ______    Total game "
                           "duration (minutes): ______"]),
                ("UNDERSTANDING (ask each player alone)", [
                    "Who could explain how someone wins, without help?  P1 / P2 / P3 / P4",
                    "Why does collecting equipment help later? ______________________",
                    "Name one treasure and what it does: ___________________________",
                    "What is Prestige for? Name two ways to get it. __________________",
                    "A rival just proclaimed a claim. What can you do? ______________"]),
                ("CLARITY", ["Rules clarifications needed (count): ______  Most asked:",
                             "(3 blank lines)", "Confusing spaces or symbols:",
                             "(3 blank lines)"]),
            ]
        else:
            blocks = [
                ("TWO BOARDS", ["Was the change from the palace map to the succession "
                                "map clear? yes / partly / no",
                                "Did the return to the gates feel fair to every seat? "
                                "yes / mostly / no   Which gate felt worst: ______",
                                "Did anyone cross the middle for B, E or the inner "
                                "stars (palace map)? yes / hardly / no",
                                "Did the two start-revealed treasures change first "
                                "moves? yes / no",
                                "Faction cards: searches before the first support: ____  "
                                "Did a far card go unused? yes / no"]),
                ("THE CLAIM", ["Claims proclaimed: ____  Challenged: ____  "
                               "Canceled: ____  Crowned: ____",
                               f"Did the {count_word(win)}-round claim window feel tense or empty? "
                               "______________________",
                               "First completed set - prize or burden? ________ "
                               "Best treasure: ____  Worst: ____"]),
                ("ENGAGEMENT", ["Did a player fall behind but stay involved? "
                                "yes / partly / no   Who: ______",
                                "Waiting between turns: where and how long? "
                                "____________________"]),
                ("AGAIN?", ["Want to play again? P1 yes/maybe/no  P2 ____  P3 ____  P4 ____",
                            "What would they try differently next time?",
                            "(2 blank lines)",
                            "One thing to change: ___________________________________"]),
            ]
        for title, rows in blocks:
            c.setFont("Times-Bold", 10.5)
            c.drawString(16 * mm, y * mm, title)
            y -= 3
            c.setLineWidth(0.5)
            c.line(16 * mm, y * mm, (PW - 16) * mm, y * mm)
            y -= 5.4
            for row in rows:
                if row == "(2 blank lines)":
                    for _ in range(2):
                        c.setLineWidth(0.4)
                        c.line(16 * mm, y * mm, (PW - 16) * mm, y * mm)
                        y -= 7.5
                elif row == "(3 blank lines)":
                    for _ in range(3):
                        c.setLineWidth(0.4)
                        c.line(16 * mm, y * mm, (PW - 16) * mm, y * mm)
                        y -= 7.5
                else:
                    y = para(c, row, 18, y, PW - 36, size=9.2, leading=12.7) - 1.6
            y -= 4
        c.setFont("Times-Italic", 7.6)
        c.drawString(16 * mm, 18 * mm,
                     "Record with this form: gate assignment, rounds played, and any "
                     "rules you improvised. Do not fill in anything that did not happen.")
        doc_footer(c, page, 2)
        c.showPage()
    c.save()


def print_instructions_pdf(path):
    c = new_doc(path, f"{PRODUCT} - print and assembly instructions")
    doc_header(c, "PRINT AND ASSEMBLE", "everything prints on plain A4, black ink, 100% scale")

    # Page 1: printing, scale check, cutting.
    y = PH - 36
    c.setFont("Times-Bold", 11)
    c.drawString(16 * mm, y * mm, "1. Print")
    y -= 5.4
    for line in ("Board file 'imperial-rivals-305ad-board-4xA4': four pages, A4 LANDSCAPE, "
                 "scale 100% (Actual size). Do not tick 'fit to page'.",
                 "Succession map 'imperial-rivals-305ad-succession-map': four pages, A4 "
                 "LANDSCAPE, 100%. It assembles exactly like the board.",
                 "Every other file: A4 portrait, 100%.",
                 "Any black-and-white printer works. Single-sided printing is fine.",
                 "Paper is enough. Card stock makes the cards nicer, but is not "
                 "required.",
                 "In the complete kit, these instructions come right before the "
                 "pages you cut: the palace board, the succession map, then the "
                 "cards and tokens."):
        y = bullet(c, line, 19, y, PW - 38, size=9.4)
    y -= 3
    c.setFont("Times-Bold", 11)
    c.drawString(16 * mm, y * mm, "2. Check the scale")
    y -= 5.4
    y = para(c, "Measure the ruler below with any ruler before you print the whole "
                "kit. If it does not measure exactly 100 mm, set the print scale "
                "to 100% and try again.", 19, y, PW - 38, size=9.4)
    ruler100(c, 45.0, y - 8)
    y -= 24
    c.setFont("Times-Bold", 11)
    c.drawString(16 * mm, y * mm, "3. Cut")
    y -= 5.4
    for line in ("Cut out the six treasure cards, the six faction cards, their "
                 "backs, and every token on the tokens page.",
                 "Fold each pawn in half on the middle line and tape or glue it so "
                 "it stands up. A coin works just as well.",
                 "Leave the eight board pages uncut for now - they are trimmed "
                 "during assembly (next page)."):
        y = bullet(c, line, 19, y, PW - 38, size=9.4)
    doc_footer(c, 1)
    c.showPage()

    # Page 2: board assembly with diagram.
    doc_header(c, "PRINT AND ASSEMBLE", "tape four pages into each board (about 58 x 41 cm)")
    y = PH - 36
    c.setFont("Times-Bold", 11)
    c.drawString(16 * mm, y * mm, "4. Assemble the board")
    y -= 5.4
    for line in ("Cut each board page along BOTH dashed lines - one upright, "
                 "one across. Cut exactly on the dashes. Each page becomes one "
                 "quadrant of the board; two thin strips fall away.",
                 "Lay the quadrants in a 2 x 2 square: page 1 top left, page 2 "
                 "top right, page 3 bottom left, page 4 bottom right (diagram "
                 "below).",
                 "Butt the cut edges together. The printed circles, letters and "
                 "lines must continue across each join without a step, and the "
                 "small circle-crosses near each join must sit level with their "
                 "neighbours on the next page.",
                 "Tape every join from the back with any tape.",
                 "Assemble the succession map the same way; its pages say "
                 "SUCCESSION MAP.",
                 "Optional: tape or glue the two boards back to back, both north "
                 "edges at the top, to make one board that turns over."):
        y = bullet(c, line, 19, y, PW - 38, size=9.4)

    y -= 5
    c.setFont("Times-Bold", 11)
    c.drawString(16 * mm, y * mm, "Arrangement (north at the top)")
    y -= 6
    cw, ch = 56.0, 40.0
    dx, dy = 34.0, y - 2 * ch - 8.0
    labels = ((1, "top left", dx, dy + ch + 4), (2, "top right", dx + cw + 6, dy + ch + 4),
              (3, "bottom left", dx, dy - 2), (4, "bottom right", dx + cw + 6, dy - 2))
    for number, where, lx, ly in labels:
        c.setLineWidth(1.1)
        c.rect(lx * mm, ly * mm, cw * mm, ch * mm)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString((lx + cw / 2.0) * mm, (ly + ch / 2.0 - 3) * mm, str(number))
        c.setFont("Helvetica", 6)
        c.drawCentredString((lx + cw / 2.0) * mm, (ly + ch / 2.0 - 10) * mm, where)
    c.setLineWidth(0.5)
    c.setDash(2, 2)
    c.line((dx + cw + 3) * mm, (dy - 7) * mm, (dx + cw + 3) * mm, (dy + 2 * ch + 12) * mm)
    c.line((dx - 7) * mm, (dy + ch + 2) * mm, (dx + 2 * cw + 13) * mm, (dy + ch + 2) * mm)
    c.setDash()
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString((dx + cw + 3) * mm, (dy + 2 * ch + 15) * mm, "N")
    c.setFont("Times-Italic", 7.6)
    c.drawString((dx + 2 * cw + 18) * mm, (dy + ch + 2) * mm, "dashed = trim + join")
    c.setFont("Times-Roman", 7.8)
    c.drawString((dx + 2 * cw + 18) * mm, (dy + ch - 6) * mm, "Assembled board:")
    c.drawString((dx + 2 * cw + 18) * mm, (dy + ch - 11.5) * mm, "about 58 x 41 cm")
    c.drawString((dx + 2 * cw + 18) * mm, (dy + ch - 17) * mm, "(A2 size).")
    c.setFont("Times-Italic", 8)
    c.drawCentredString(PW / 2.0 * mm, 19 * mm,
                        "No printer at hand? Any print shop can print these PDFs from "
                        "a USB stick - nothing here needs an account.")
    doc_footer(c, 2)
    c.showPage()
    c.save()


# ---------------------------------------------------------------------------


def combine(paths, out):
    from pypdf import PdfWriter
    w = PdfWriter()
    for p in paths:
        w.append(p)
    with open(out, "wb") as fh:
        w.write(fh)


# Rule numbers in the printed prose flow from the rules JSON through
# printed_values() and twin_geometry(); main() validates both before it
# draws any page. This table stays fixed because the prose describes one
# specific ability line per item.
PRINTED_ABILITIES = {
    "pugio": ("win_ties", 1),
    "pilum": ("attack_vs_claimant", 1),
    "galea": ("reveal_district", 1),
    "scutum": ("defense_bonus", 1),
    "gladius": ("attack_bonus", 1),
    "lorica_segmentata": ("prevent_displacement", 1),
}

# The big-board prose assumes this exact succession map: the palace
# board's size, gates "9 steps from the Peristyle", six faction card
# spaces dealt blind (one for each of the six blocks), and four guard
# posts on the endgame map.
# "Its Peristyle is three steps east of the palace crossing."
PRINTED_PALACE_CHECKPOINT = [6, 6]
PRINTED_TWIN = {
    "width": 19,
    "height": 13,
    "gates": {"north": [6, 0], "east": [18, 6], "south": [12, 12], "west": [0, 6]},
    "checkpoint": [9, 6],
    "guard_posts": [[0, 2], [18, 10], [2, 0], [16, 12]],
    "card_spaces": [[3, 0], [15, 12], [3, 6], [15, 6], [7, 6], [11, 6]],
}


def main():
    rules_file = (sys.argv[sys.argv.index("--rules") + 1]
                  if "--rules" in sys.argv else RULES_FILE)
    rules = engine.load_rules(rules_file)
    validate_six_block_layout(rules)
    if rules["game"]["name"] != "Imperial Rivals: 305 AD":
        raise SystemExit("this kit needs the Imperial Rivals ruleset")
    for key in ("allow_early_stop", "pass_through_pawns"):
        if not rules["movement"][key]:
            raise SystemExit(f"printed text assumes movement.{key}; "
                             "update the kit prose")
    if not rules["turns"]["rotate_first_player_each_round"]:
        raise SystemExit("printed text assumes "
                         "turns.rotate_first_player_each_round; "
                         "update the kit prose")
    if rules["treasures"]["bonus_per_side"] != "best":
        raise SystemExit('printed text assumes '
                         'treasures.bonus_per_side == "best"; '
                         "update the kit prose")
    if rules["game"]["players"] != 4:
        raise SystemExit("printed text builds four mats, four pawns and a "
                         "four-seat faction sentence; update the kit prose")
    # Phrase every printed rule number once up front, so a rules change
    # the prose cannot express stops the build before any PDF is drawn.
    printed_values(rules)
    twin_geometry(rules)
    abilities = rules["treasures"]["abilities"]
    if abilities != {name: {"type": kind, "value": value}
                     for name, (kind, value) in PRINTED_ABILITIES.items()}:
        raise SystemExit("printed text assumes the six one-line item "
                         "abilities in PRINTED_ABILITIES; update the kit prose")
    twin = rules["succession"]["map"]
    if rules["palace"]["map"]["checkpoint"] != PRINTED_PALACE_CHECKPOINT:
        raise SystemExit("printed text assumes the palace Peristyle at "
                         f"{PRINTED_PALACE_CHECKPOINT} (three steps west of the "
                         "succession Peristyle); update the kit prose")
    for key, value in PRINTED_TWIN.items():
        actual = twin.get(key)
        if actual != value:
            raise SystemExit(
                f"printed text assumes succession.map {key} == {value}, "
                f"rules say {actual}; update the kit prose")
    build_art = "--art" in sys.argv
    build_color = "--color" in sys.argv
    L = build_layout(rules)
    os.makedirs(BW_DIR, exist_ok=True)
    out = lambda name: os.path.join(OUT_DIR, name)
    bw = lambda name: os.path.join(BW_DIR, name)
    files = {
        "board": bw("imperial-rivals-305ad-board-4xA4-BW.pdf"),
        "succession": bw("imperial-rivals-305ad-succession-map-A4-BW.pdf"),
        "sheets": bw("imperial-rivals-305ad-player-sheets-A4-BW.pdf"),
        "cards": bw("imperial-rivals-305ad-cards-tokens-A4-BW.pdf"),
        "rulebook": bw("imperial-rivals-305ad-rulebook-A4-BW.pdf"),
        "quick": bw("imperial-rivals-305ad-quick-reference-A4-BW.pdf"),
        "teaching": bw("imperial-rivals-305ad-teaching-guide-A4-BW.pdf"),
        "form": bw("imperial-rivals-305ad-playtest-form-A4-BW.pdf"),
        "instructions": bw("imperial-rivals-305ad-print-instructions-A4-BW.pdf"),
    }
    board_pdf(files["board"], L)
    succession_map_pdf(files["succession"], rules)
    player_sheets_pdf(files["sheets"], rules)
    cards_tokens_pdf(files["cards"], rules)
    rulebook_pdf(files["rulebook"], rules)
    quick_reference_pdf(files["quick"], rules)
    teaching_guide_pdf(files["teaching"], rules)
    playtest_form_pdf(files["form"], rules)
    print_instructions_pdf(files["instructions"])
    # The rules first; then the print instructions, right before the
    # pages they explain: the boards, then the cards and tokens. The
    # playtest form prints on its own.
    combine([files["rulebook"], files["quick"], files["teaching"], files["sheets"],
             files["instructions"], files["board"], files["succession"], files["cards"]],
            bw("imperial-rivals-305ad-complete-print-kit-A4-BW.pdf"))
    if build_art:
        art_files = {
            "art_board": out("imperial-rivals-305ad-board-4xA4-ART.pdf"),
            "art_succession": out("imperial-rivals-305ad-succession-map-ART.pdf"),
            "art_cards": out("imperial-rivals-305ad-cards-tokens-ART.pdf"),
        }
        art_board_pdf(art_files["art_board"], L)
        art_succession_pdf(art_files["art_succession"], build_succession_layout(rules))
        art_cards_tokens_pdf(art_files["art_cards"])
        combine([files["rulebook"], files["quick"], files["teaching"], files["sheets"],
                 files["instructions"], art_files["art_board"],
                 art_files["art_succession"], art_files["art_cards"]],
                out("imperial-rivals-305ad-complete-print-kit-A4-ART.pdf"))
        files.update(art_files)
    if build_color:
        os.makedirs(COLOR_DIR, exist_ok=True)
        col = lambda name: os.path.join(COLOR_DIR, name)
        color_files = {
            "color_board": col("imperial-rivals-305ad-board-4xA4-COLOR.pdf"),
            "color_succession": col("imperial-rivals-305ad-succession-map-COLOR.pdf"),
            "color_cards": col("imperial-rivals-305ad-cards-tokens-COLOR.pdf"),
        }
        label = "full colour"
        art_board_pdf(color_files["color_board"], L, COLOR_ART_DIR, label)
        art_succession_pdf(color_files["color_succession"], build_succession_layout(rules),
                           COLOR_ART_DIR, label)
        art_cards_tokens_pdf(color_files["color_cards"], COLOR_ART_DIR, label)
        combine([files["rulebook"], files["quick"], files["teaching"], files["sheets"],
                 files["instructions"], color_files["color_board"],
                 color_files["color_succession"], color_files["color_cards"]],
                col("imperial-rivals-305ad-complete-print-kit-A4-COLOR.pdf"))
        files.update(color_files)
    b = L["board"]
    S = build_succession_layout(rules)
    manifest = {
        "version": KIT_VERSION,
        "rules_file": rules_file,
        "rules_hash": engine.rules_hash(rules),
        "counts": {"street_spaces": len(L["spaces"]), "blocked": len(b.blocked),
                   "buildings": len(rules["palace"]["map"]["buildings"]),
                   "gates": len(b.gates), "districts": len(b.districts),
                   "guard_posts": len(b.guard_posts)},
        "counts_succession": {
            "street_spaces": len(S["spaces"]), "blocked": len(S["board"].blocked),
            "gates": len(S["board"].gates), "blocks": len(S["blocks"]),
            "card_spaces": len(S["card_spaces"]),
            "guard_posts": len(S["board"].guard_posts)},
        "layout": {
            "cell_mm": CELL, "overlap_mm": OVERLAP, "safe_mm": SAFE,
            "page_mm": [PAGE_W, PAGE_H],
            "art_bounds_mm": list(L["art"]),
            "cut_lines_mm": {"x": L["cut"]["x"], "y": L["cut"]["y"]},
            "reg_marks_mm": [list(p) for p in L["reg_marks"]],
            "tiles": {k: [v[0], v[1], v[2]] for k, v in L["tiles"].items()},
            "space_positions_mm": {f"{x},{y}": [round(px, 2), round(py, 2)]
                                   for (x, y), (px, py) in L["spaces"]},
            "specials_mm": {
                "gates": {pid: [round(v, 2) for v in L["pos"](tuple(cell))]
                          for pid, cell in b.gates.items()},
                "districts": {name: [round(v, 2) for v in L["pos"](tuple(cell))]
                              for name, cell in b.districts.items()},
                "checkpoint": [round(v, 2) for v in L["pos"](tuple(b.checkpoint))],
                "guard_posts": [list(map(round, L["pos"](tuple(cell)))) for cell in b.guard_posts],
            },
            "succession_map_mm": {
                "cell_mm": CELL, "grid_mm": [S["grid_w"], S["grid_h"]],
                "art_bounds_mm": list(S["art"]),
                "reg_marks_mm": [list(p) for p in S["reg_marks"]],
                "specials_mm": {
                    "gates": {pid: [round(v, 2) for v in S["pos"](tuple(cell))]
                              for pid, cell in S["board"].gates.items()},
                    "checkpoint": [round(v, 2) for v in S["pos"](tuple(S["board"].checkpoint))],
                    "card_spaces": [[round(v, 2) for v in S["pos"](cell)]
                                    for cell in S["card_spaces"]],
                    "guard_posts": [[round(v, 2) for v in S["pos"](tuple(cell))]
                                    for cell in S["board"].guard_posts],
                },
                "blocks": [list(block) for block in S["blocks"]],
            },
        },
        "files": files,
    }
    with open(out("kit-manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print(f"wrote {len(files) + 1} PDFs into {BW_DIR}/" + (" and the art kit into " + OUT_DIR + "/" if build_art else "")
          + (" and the colour kit into " + COLOR_DIR + "/" if build_color else "")
          + f", plus {OUT_DIR}/kit-manifest.json")
    for name, path in files.items():
        print(f"  {name}: {path} ({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    main()
