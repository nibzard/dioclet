#!/usr/bin/env python3
"""Generate the V0.9.3 black-and-white A4 print-and-play kit.

Everything prints on ordinary A4 paper with black ink only. The board
is one complete vector drawing of the current succession board (19x13
cells, 97 street spaces, six intact blocks), divided at print time
into four overlapping A4 landscape tiles that assemble into one
large board (about A2). All other documents are A4 portrait.

Outputs into print/:
  dioclet-board-4xA4-BW.pdf        four tiled board pages (landscape)
  dioclet-player-sheets-A4-BW.pdf  four player mats (two per page)
  dioclet-cards-tokens-A4-BW.pdf   treasure cards, backs, tokens
  dioclet-rulebook-A4-BW.pdf       family rulebook
  dioclet-quick-reference-A4-BW.pdf
  dioclet-teaching-guide-A4-BW.pdf
  dioclet-playtest-form-A4-BW.pdf
  dioclet-print-instructions-A4-BW.pdf
  dioclet-complete-print-kit-A4-BW.pdf (all of the above, board first)
  kit-manifest.json (layout facts used by the tests)

Run: python3 tools/make_a4_print_kit.py [--rules RULES_FILE]
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

RULES_FILE = "rules_v093_succession.json"
OUT_DIR = "print"
KIT_VERSION = "V0.9.3 print kit (V0.9.3 crossflow rules)"

# Faction meeting-place badges sit beside each faction's cell. Army
# and elites share a cell with rim treasure entries, where the
# north-east offset lands on building hatch. The officials meet on
# the decumanus one circle east of the Peristyle; the same offset
# would collide with the next street circle, so their badge rises
# straight north instead, clear of the PERISTYLE label.
FACTION_BADGE_OFFSET = {"army": (13.2, 11.8), "elites": (13.2, 11.8),
                        "officials": (0.0, 15.5)}

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


def build_layout(rules):
    """All geometric facts, computed once and shared by every page."""
    b = Board(rules)
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
    _centered(c, (art[0] + art[2]) / 2.0, art[3] - 15.0, "DIOCLETIAN'S PALACE",
              "Times-Bold", 30)
    _centered(c, (art[0] + art[2]) / 2.0, art[3] - 23.0,
              "THE SUCCESSION  ·  SIX TREASURES", "Times-Roman", 12.5)
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
    for bld in rules["board"]["buildings"]:
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
    special = ({tuple(g) for g in b.glory_posts}
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
    for cell in b.glory_posts:
        x, y = pos(tuple(cell))
        c.setLineWidth(1.3)
        _star(c, x * mm, (y + 1.4) * mm, 9.6 * mm)
        _centered(c, x, y - 6.6, "4+", "Helvetica-Bold", 6.5)

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

    # Peristyle: octagon at the crossing. The officials no longer meet
    # here (their badge marks their own circle east of the crossing),
    # so the octagon carries only the crossing mark.
    px, py = pos(tuple(b.checkpoint))
    c.setLineWidth(2.0)
    _octagon(c, px * mm, py * mm, 11.2 * mm)
    c.setLineWidth(0.8)
    _octagon(c, px * mm, py * mm, 8.2 * mm)
    _centered(c, px, py - 1.6, "X", "Times-Bold", 10)
    # Label above the octagon: below it, the text top would sit 0.4 mm
    # from the horizontal cut line and a wandering cut would shave it.
    _centered(c, px, py + 13.4, "PERISTYLE", "Helvetica-Bold", 6.8)

    # Faction meeting badges beside each meeting-place cell: army at
    # treasure entry F, city elites at entry A, officials one circle
    # east of the Peristyle. The legend names each symbol; no tiny
    # text labels on the board.
    for faction, cell in sorted(rules["succession"]["factions"].items()):
        x, y = pos(tuple(cell))
        dx, dy = FACTION_BADGE_OFFSET[faction]
        bx, by = x + dx, y + dy
        c.setLineWidth(0.9)
        c.circle(bx * mm, by * mm, 5.8 * mm, stroke=1, fill=0)
        if faction == "army":
            _shield(c, bx * mm, (by - 0.3) * mm, 4.2 * mm)
        elif faction == "officials":
            _column(c, bx * mm, (by + 0.2) * mm, 3.8 * mm)
        else:
            _laurel(c, bx * mm, (by + 0.4) * mm, 4.2 * mm)

    # (The cardo and decumanus street names live in the legend caption;
    # the board itself stays symbol-only.)

    # Legend band below the grid, two rows so every label keeps air.
    row_defs = [
        (by0 + 15.4, [("circle", "street space"),
                      ("double", "treasure entry (take equipment)"),
                      ("arch", "gate / start"),
                      ("octagon", "Peristyle - proclaim here"),
                      ("star", "guard post: roll 4+ for 1 Prestige")]),
        (by0 + 7.2, [("shield", "Army meeting place"),
                     ("column", "Officials meeting place"),
                     ("laurel", "City elites meeting place"),
                     ("hatch", "building - no entry")]),
    ]
    legend_positions = ((25, 115, 245, 355, 450), (25, 130, 310, 440))
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
    note = f"PAGE {page_no} OF 4 - PRINT AT 100%"
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
    c.setTitle("Diocletian's Palace - board (4 x A4, black and white)")
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
# Text helpers for the portrait documents.

PW, PH = 210.0, 297.0


def new_doc(path, title, landscape_pages=False):
    c = pdfcanvas.Canvas(path, pagesize=A4)
    c.setTitle(title)
    c.setAuthor("Diocletian's Palace print kit")
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
                        f"Diocletian's Palace - {KIT_VERSION} - page {page}"
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

def player_mat(c, x, y, w, h, numeral):
    c.setLineWidth(1.3)
    c.rect(x * mm, y * mm, w * mm, h * mm)
    c.setFont("Times-Bold", 13)
    c.drawString((x + 4) * mm, (y + h - 8) * mm, f"PLAYER {numeral}")
    c.setFont("Times-Roman", 9)
    c.drawString((x + w * 0.42) * mm, (y + h - 8) * mm, "Name ______________________")
    c.drawString((x + w * 0.42) * mm, (y + h - 13.5) * mm, "Gate ______________________")

    col1 = x + 4.0
    col2 = x + w * 0.44
    colw = w * 0.40

    ty = y + h - 22
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(col1 * mm, ty * mm, "EQUIPMENT (mark each item you collect)")
    ty -= 6.2
    items = [("Pugio", "wins tied duels"), ("Pilum", "+1 vs the claimant"),
             ("Galea", "once: reveal a district"), ("Scutum", "+1 defense"),
             ("Gladius", "+1 attack"), ("Lorica segmentata", "once: stay when beaten")]
    for name, hint in items:
        checkbox(c, col1, ty)
        c.setFont("Times-Bold", 9.5)
        c.drawString((col1 + 6.5) * mm, (ty + 0.7) * mm, name)
        c.setFont("Times-Italic", 7)
        c.drawString((col1 + 6.5 + c.stringWidth(name, "Times-Bold", 9.5) / mm + 2.5) * mm,
                     (ty + 0.9) * mm, hint)
        ty -= 7.2
    ty -= 1.4
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(col1 * mm, ty * mm, "EQUIPMENT IN DUELS")
    ty -= 5.4
    c.setFont("Times-Roman", 8.8)
    c.drawString(col1 * mm, ty * mm, "Add your one best item bonus - never a sum.")

    ty = y + h - 22
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(col2 * mm, ty * mm, "PRESTIGE (hold at most 3 - extra is lost)")
    ty -= 8.4
    for i in range(3):
        cx = col2 + 4.5 + i * 11.5
        c.setLineWidth(1.0)
        c.circle(cx * mm, (ty + 2.2) * mm, 4.2 * mm)
        _centered(c, cx, ty + 0.9, str(i + 1), "Times-Bold", 9)
    c.setFont("Times-Italic", 7)
    c.drawString((col2 + 41) * mm, (ty + 1.2) * mm, "place one counter per point")

    ty -= 9.5
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(col2 * mm, ty * mm, "FACTION SUPPORT (2 different groups to proclaim)")
    ty -= 6.4
    for name, sym in (("Army", "shield"), ("Imperial officials", "column"), ("City elites", "laurel")):
        checkbox(c, col2, ty)
        c.setFont("Times-Bold", 9.5)
        c.drawString((col2 + 6.5) * mm, (ty + 0.7) * mm, name)
        sx = col2 + 6.5 + c.stringWidth(name, "Times-Bold", 9.5) / mm + 3.0
        c.setLineWidth(0.8)
        if sym == "shield":
            _shield(c, sx * mm, (ty + 2.2) * mm, 2.6 * mm)
        elif sym == "column":
            _column(c, sx * mm, (ty + 2.4) * mm, 2.4 * mm)
        else:
            _laurel(c, sx * mm, (ty + 2.4) * mm, 2.8 * mm)
        ty -= 7.2

    ty -= 1.2
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(col2 * mm, ty * mm, "SUCCESSION REMINDERS")
    ty -= 5.4
    for line in ("Support: visit the meeting place, pay 1 Prestige.",
                 "Proclaim: at the Peristyle with 2 different backers.",
                 "Claim window: a claim that stands 2 full rounds wins.",
                 "Contest a claim: pay the 1 Prestige fee, then duel.",
                 "Duel loser: pay 1 Prestige to the bank (shame).",
                 "Setup: two treasure districts start revealed."):
        ty = para(c, line, col2, ty, w - (col2 - x) - 4, size=8.3, leading=4.9)


def player_sheets_pdf(path):
    c = new_doc(path, "Diocletian's Palace - player sheets")
    for page in range(2):
        doc_header(c, "PLAYER SHEETS", "one mat per player - mark with pencil or counters")
        w, h = PW - 32.0, 114.0
        y0 = PH - 40 - h
        for i, numeral in enumerate(("I", "II") if page == 0 else ("III", "IV")):
            player_mat(c, 16.0, y0 - i * (h + 8), w, h, numeral)
        doc_footer(c, page + 1, 2)
        c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Cards and tokens.

CARD_W, CARD_H = 55.0, 75.0
CARDS = [
    ("Pugio", "dagger", "Wins tied duels."),
    ("Pilum", "pilum", "+1 attack vs the claimant."),
    ("Galea", "helmet", "Once a game: reveal any district."),
    ("Scutum", "scutum", "+1 to your defense."),
    ("Gladius", "gladius", "+1 to your attack."),
    ("Lorica Segmentata", "armor", "Once: a beaten claimant stays put."),
]


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


def cards_tokens_pdf(path):
    c = new_doc(path, "Diocletian's Palace - cards and tokens")

    # Page 1: the six treasure location cards.
    doc_header(c, "TREASURE LOCATION CARDS", "cut on the outer border - identical backs on the next page")
    x0, y0 = 16.0, PH - 32.5 - CARD_H
    for i, (name, icon, flavor) in enumerate(CARDS):
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
        _centered(c, cx + CARD_W / 2.0, cy + 13.5, flavor, "Times-Italic", 7.0)
        _centered(c, cx + CARD_W / 2.0, cy + 5.5, "PALACE TREASURE - LOCATION CARD",
                  "Helvetica", 5.2)
    y = y0 - (CARD_H + 5.0) - 9.0
    para(c, "Shuffle face down and deal one card to each treasure entry A-F. Then turn "
            "two of the six face up at random - everyone sees those two treasures from "
            "the start. Each card states its ability; in a duel count one best bonus "
            "per side, never a sum.", 16, y, PW - 32, size=8.4)
    doc_footer(c, 1)
    c.showPage()

    # Page 2: six identical card backs (print single-sided, then fold or glue).
    doc_header(c, "CARD BACKS", "six identical tiles - glue or fold behind each card")
    for i in range(6):
        cx = x0 + (i % 3) * (CARD_W + 5.5)
        cy = y0 - (i // 3) * (CARD_H + 5.0)
        c.setLineWidth(1.2)
        c.rect(cx * mm, cy * mm, CARD_W * mm, CARD_H * mm)
        c.setLineWidth(0.5)
        c.rect((cx + 2.6) * mm, (cy + 2.6) * mm, (CARD_W - 5.2) * mm, (CARD_H - 5.2) * mm)
        c.setLineWidth(0.9)
        _laurel(c, (cx + CARD_W / 2.0) * mm, (cy + CARD_H / 2.0 + 3.5) * mm, 12.5 * mm)
        _centered(c, cx + CARD_W / 2.0, cy + CARD_H / 2.0 - 10.5,
                  "DIOCLETIAN'S", "Times-Bold", 9.5)
        _centered(c, cx + CARD_W / 2.0, cy + CARD_H / 2.0 - 15.5,
                  "PALACE", "Times-Bold", 9.5)
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
    kinds = (("ARMY", "shield"), ("OFFICIALS", "column"), ("ELITES", "laurel"))
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
    c.drawString(16 * mm, y * mm, "City phase (max 24 rounds):")
    for i in range(24):
        box(c, 58.0 + i * 5.6, y - 1.6, 4.6, 5.2, lw=0.7)
        if (i + 1) % 6 == 0:
            c.setFont("Helvetica", 4.6)
            c.drawCentredString((60.3 + i * 5.6) * mm, (y - 5.4) * mm, str(i + 1))
    y -= 10
    c.setFont("Times-Roman", 8)
    c.drawString(16 * mm, y * mm, "Succession phase (max 24 rounds):")
    for i in range(24):
        box(c, 58.0 + i * 5.6, y - 1.6, 4.6, 5.2, lw=0.7)
    y -= 8
    c.setFont("Times-Italic", 7.4)
    c.drawString(16 * mm, y * mm,
                 "The city phase ends 1 full round after the first checkpoint claim (or at round 24). "
                 "Track rounds only if you use the 24-round limits.")
    doc_footer(c, 3)
    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Rulebook.

RULEBOOK_PAGES = [
    ("The goal", [
        ("h", "What you are trying to do"),
        ("p", "Diocletian has retired. Four rivals prepare a claim to the throne. "
              "Collect equipment to become strong, earn Prestige to pay for help, and "
              "win the support of two of the three factions in the city. Then stand at "
              "the Peristyle, the great crossing of the palace, and proclaim your claim. "
              "If none of your three rivals can stop it, the throne is yours."),
        ("h", "What you need"),
        ("b", "This printed kit: the board (four taped pages), six treasure cards, "
              "the tokens, and one player sheet per person."),
        ("b", "Two ordinary six-sided dice for movement, and one six-sided die for "
              "fights (any die works for both - you just need three dice in total)."),
        ("b", "A small pawn per player. Coins or buttons work. The paper pawns in "
              "this kit also work."),
        ("b", "About 45 to 75 minutes for four players learning the game."),
        ("h", "How to set up"),
        ("n", "Assemble the board (see the assembly sheet). Each player picks a pawn "
              "and a player sheet, and writes their name on it."),
        ("n", "Shuffle the six treasure cards face down. Place one on each treasure "
              "entry, the double circles marked A to F. Then turn two of the six "
              "face up at random - everyone sees those two treasures from the start."),
        ("n", "Give each player a random gate: Golden (north), Silver (east), Bronze "
              "(south), or Iron (west). Put your pawn on your gate."),
        ("n", "Choose a starting player at random. The start moves one seat clockwise "
              "at the beginning of every round."),
    ]),
    ("Your turn", [
        ("h", "One turn, three steps"),
        ("n", "Roll two dice. The total is the maximum number of steps you may take."),
        ("n", "Move your pawn along the street circles, one circle per step, north, "
              "south, east or west. You may stop before using the whole roll and you "
              "may pass through circles occupied by other pawns."),
        ("n", "Do one action where you stand - or do nothing. Taking treasure, "
              "standing guard, duelling, gaining support, proclaiming and "
              "revealing a district (with the galea) are all actions. You never "
              "do two of these on the same turn."),
        ("h", "What counts as movement"),
        ("p", "The white circles are streets. The hatched blocks are buildings: "
              "nobody walks through them. All movement and all distances are counted "
              "along street circles, not across buildings."),
        ("p", "Guard duty and duels are actions of a moving turn: you must move at "
              "least one circle first. Taking treasure, gaining support, claiming the "
              "checkpoint and proclaiming may be done without moving."),
        ("h", "Rounds and turns"),
        ("p", "A round is one turn for every player, in clockwise order from the "
              "starting player. After the last player, a new round begins and the "
              "start moves one seat clockwise, so nobody always plays first."),
    ]),
    ("Treasure and equipment", [
        ("h", "The six treasures"),
        ("p", "Each treasure entry (double circle, A to F) holds one face-down card: "
              "pugio, pilum, galea, scutum, gladius, or lorica segmentata. Two of "
              "the six start face up. End your move on an entry to take that "
              "card's action: reveal the card to everyone and mark the item on "
              "your player sheet."),
        ("p", "Every player can collect every item once. The cards stay on the board "
              "face up once revealed; they are never taken away, stolen, or lost. If "
              "you are the first to stop at an entry, you learn for everyone what "
              "waits there."),
        ("h", "What each item does"),
        ("p", "Every item carries one ability that lasts the whole game:"),
        ("t", [["Item", "Mark", "Ability"],
               ["Gladius", "sword", "+1 to your attack in any duel you start"],
               ["Scutum", "shield", "+1 to your defense in any duel"],
               ["Pilum", "javelin", "+1 to your attack against the standing claimant"],
               ["Pugio", "dagger", "you win tied duels"],
               ["Galea", "helmet", "once per game, as your action: reveal any one "
                "face-down treasure card, wherever it is"],
               ["Lorica segmentata", "armor", "once per game: when your claim is "
                "beaten, keep your square instead of returning to your gate"]]),
        ("p", "In a duel each side adds at most one item bonus - the best one that "
              "applies, never a sum. If you hold both the gladius and the pilum and "
              "attack the claimant, you still add only +1. Cross an item out on "
              "your sheet when its once-per-game ability is used."),
        ("p", "You can keep collecting missing items during the succession phase. "
              "Nothing is ever granted for free - if you want it, walk and get it."),
    ]),
    ("Prestige", [
        ("h", "Earning Prestige"),
        ("b", "Guard post (star): end a move there and roll one die. A 4, 5 or 6 "
              "earns 1 Prestige."),
        ("b", "Win a duel: the winner of any duel earns 1 Prestige."),
        ("p", "You can hold at most 3 Prestige. Any reward above three is lost - "
              "spend it or waste it."),
        ("h", "Duels"),
        ("p", "End your move within two street circles of a rival and you may duel "
              "them as your action. The attacker and the defender each roll one die "
              "and add their best item bonus for that side. The higher total wins; "
              "on a tie the attacker wins - unless exactly one side holds the "
              "pugio, whose holder then wins the tie. The winner earns 1 Prestige. "
              "The loser pays 1 Prestige to the bank as shame, as much as they "
              "hold. Nobody loses equipment or support."),
        ("h", "Spending Prestige"),
        ("b", "1 Prestige: one faction's support (next page)."),
        ("b", "1 Prestige: the mandatory fee to contest a proclaimed claim (next page)."),
    ]),
    ("Factions and the claim", [
        ("h", "The three factions"),
        ("p", "Three groups in the city can back your claim. Their meeting places "
              "are marked on the board with badges:"),
        ("t", [["Faction", "Badge", "Meeting place"], ["Army", "shield", "Treasure entry F"],
               ["Imperial officials", "column", "one circle east of the Peristyle"],
               ["City elites", "laurel", "Treasure entry A"]]),
        ("p", "Visit a meeting place and spend 1 Prestige to gain that faction's "
              "support. There is no roll. Every faction can support every player, but "
              "each faction supports each player only once. Support lasts the whole "
              "game. You may gain support in either phase of the game."),
        ("h", "From the city to the succession"),
        ("p", "The game has two phases. In the city phase everyone collects "
              "equipment and Prestige. The first player who owns all six items may "
              "stand at the Peristyle and claim the checkpoint as their action. "
              "Finish that round, then one more full round, and the "
              "succession phase begins. If nobody claims by the end of round 24, the "
              "succession begins anyway."),
        ("p", "At the change, every pawn stays where it stands and keeps everything "
              "it owns. Missing equipment is not granted - you can still walk and "
              "collect it."),
        ("h", "Proclaiming a claim"),
        ("n", "During the succession phase, stand at the Peristyle with support from "
              "two different factions."),
        ("n", "Use your action to proclaim your claim. Place the CLAIM marker on the "
              "Peristyle. Only one claim can stand at a time."),
        ("n", "Your claim now stands inside a two-round window. Rivals may cancel it "
              "only by winning a challenge duel (next page). Turns that pass "
              "without a challenge no longer crown anyone by themselves."),
        ("n", "If your turn comes while your claim stands and you are still at the "
              "Peristyle, you may maintain the claim as your action and stay put. "
              "Leaving the Peristyle by your own move cancels your claim."),
        ("n", "If no rival cancels your claim before two full rounds have passed, "
              "you are emperor and the game ends."),
    ]),
    ("Contesting a claim", [
        ("h", "How to contest"),
        ("p", "A rival can stop a claim by winning a challenge duel against the "
              "claimant. To do it, end your move within two street "
              "circles of the claimant and duel them. Challenging a standing claim "
              "costs a mandatory fee of 1 Prestige, paid before you roll - even if "
              "you lose. Without at least 1 Prestige you cannot contest at all."),
        ("p", "The challenge itself is a normal duel: one die each, add your best "
              "item bonus, the pugio wins ties. A full challenge costs only the "
              "1 Prestige fee."),
        ("h", "What happens on each result"),
        ("b", "You win: the claim is canceled. The claimant's pawn returns to their "
              "gate - unless they have not used the lorica segmentata, which once "
              "per game lets a beaten claimant keep their square (the claim still "
              "dies). They keep all equipment, Prestige and support either way. "
              "The next claim may be proclaimed at any time."),
        ("b", "You lose: the claim stands. Your Prestige is spent either way, and "
              "as in any duel the loser pays 1 Prestige shame to the bank."),
        ("h", "An example challenge"),
        ("p", "Livia has proclaimed at the Peristyle with the Army and the elites "
              "behind her. Marcus, holding 2 Prestige, the gladius and the pilum, "
              "moves next to the crossing. He pays the 1 Prestige fee and duels. "
              "His best item bonus is +1 - the pilum also applies against a "
              "claimant, but one bonus only counts. He rolls 5 + 1 = 6. Livia "
              "holds the scutum and rolls 4 + 1 = 5. Marcus wins; the claim dies "
              "and Livia pays 1 Prestige shame. She has kept the lorica segmentata "
              "unused, so she stays at the crossing instead of walking back to her "
              "gate. Marcus earns 1 Prestige for the duel win, leaving him with 2."),
        ("h", "If nobody wins"),
        ("p", "If no claim survives by the end of round 24 of the succession phase, "
              "the game ends in a draw - the throne stays empty. This is rare."),
        ("h", "Remember"),
        ("b", "An ordinary duel is free. Challenging a claim always costs the "
              "1 Prestige fee."),
        ("b", "Everything is public: positions, items, Prestige, support, and who "
              "has claimed what. Only the four face-down cards and the next dice "
              "roll are hidden."),
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
              "the attacker wins."),
        ("q", "Does the galea let me name an item? No. You name a district, not an "
              "item - the reveal turns up whatever card sits there."),
        ("q", "What if I have 3 Prestige and win a guard roll? Nothing happens - the cap is "
              "3. Spend some first."),
        ("q", "Can a faction support two different players? Yes - every faction can "
              "back every player once."),
        ("q", "Can I proclaim twice? Yes, if your first claim is canceled, walk "
              "back and proclaim again. Support is never lost."),
        ("q", "Can a claim be canceled after the window closes? No. Two full rounds "
              "unchallenged and the game is over."),
        ("q", "Do treasures run out? No. Every player can mark each of the six items."),
        ("q", "What if two players reach six items on the same round? The first to "
              "claim at the Peristyle in turn order is the first challenger."),
    ]),
]


def rulebook_pdf(path):
    c = new_doc(path, "Diocletian's Palace - rulebook")
    page = 1
    doc_header(c, "DIOCLETIAN'S PALACE", "The Succession - rules for four players")

    y = PH - 36
    c.setFont("Times-Italic", 9.5)
    y = para(c, "Read pages 1 to 3 before the first turn. Use pages 4 to 6 for "
                "the succession phase and common questions.", 22, y, PW - 44)
    y -= 3

    def new_page():
        nonlocal page, y
        doc_footer(c, page)
        c.showPage()
        page += 1
        doc_header(c, "DIOCLETIAN'S PALACE - RULES", "The Succession")
        y = PH - 36

    for section_index, (section_title, blocks) in enumerate(RULEBOOK_PAGES):
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

def quick_reference_pdf(path):
    c = new_doc(path, "Diocletian's Palace - quick reference")
    doc_header(c, "QUICK REFERENCE", "keep this beside the board")
    y = PH - 36
    blocks = [
        ("YOUR TURN", ["1. Roll two dice.", "2. Move up to the total; stop early if you like.",
                       "3. Do ONE action (or none): take treasure · guard duty · duel · "
                       "gain support · claim the checkpoint · proclaim · maintain your claim."]),
        ("ROLLS", ["Movement: two dice summed.", "Guard post: one die - 4+ earns 1 Prestige.",
                   "Duel: one die each + your one best item bonus; the pugio wins ties."]),
        ("EQUIPMENT (one best bonus per side)", [
            "Gladius +1 attack · Scutum +1 defense · Pilum +1 vs the claimant.",
            "Pugio wins ties · Galea once: reveal a district · Lorica once: stay "
            "when beaten."]),
        ("PRESTIGE (cap 3)", ["Earn: guard post 4+ · any duel win.",
                              "Spend: 1 = faction support · 1 = fee to contest a claim.",
                              "Lose: 1 to the bank whenever you lose a duel."]),
        ("FACTIONS", ["Army (shield) at F · officials (column) one circle east of the "
                      "Peristyle · elites (laurel) at A.", "1 Prestige each, no roll, any "
                      "phase. Two different factions needed to proclaim."]),
        ("PROCLAIM", ["Succession phase, stand at the Peristyle, 2 supporters, "
                      "no other claim standing."]),
        ("CONTEST A CLAIM", ["Move within 2 circles of the claimant and duel them, "
                             "any turn inside the window.", "Mandatory fee: 1 Prestige "
                             "before you roll.", "Win: claim "
                             "canceled, claimant returns to their gate (lorica: stay put "
                             "once), keeps everything."]),
        ("WINNING", ["A claim that stands two full rounds = emperor.",
                     "No claim standing by succession round 24 = draw."]),
    ]
    for title, lines in blocks:
        wrapped = [wrap_lines(c, line, 168.0, size=9.0, font="Helvetica") for line in lines]
        body_h = 5.6 * sum(len(group) for group in wrapped) + 4.0
        c.setLineWidth(1.1)
        c.rect(16 * mm, (y - 6.2) * mm, (PW - 32) * mm, 6.2 * mm)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(18.5 * mm, (y - 4.4) * mm, title)
        y -= 6.2
        c.setLineWidth(0.4)
        c.rect(16 * mm, (y - body_h) * mm, (PW - 32) * mm, body_h * mm)
        yy = y - 4.2
        c.setFont("Helvetica", 9.0)
        for group in wrapped:
            for line in group:
                c.drawString(19.5 * mm, yy * mm, line)
                yy -= 5.6
        y = y - body_h - 5.2
    doc_footer(c, 1)
    c.showPage()
    c.save()


def teaching_guide_pdf(path):
    c = new_doc(path, "Diocletian's Palace - five-minute teaching guide")
    page = 1
    doc_header(c, "TEACH IN FIVE MINUTES",
               "read aloud - seven steps, then two short demonstrations")
    y = PH - 36
    steps = [
        ("The goal (30 seconds)", "Diocletian has retired and the throne is empty. "
         "You will collect gear, win friends, and try to crown yourself. The claim "
         "your three rivals fail to stop inside two rounds wins the game."),
        ("Moving (30 seconds)", "On your turn, roll two dice and move up to the "
         "total along the white circles. Streets only - the hatched blocks are "
         "buildings. Stop anywhere. Then do one thing. That is a whole turn."),
        ("Equipment (45 seconds)", "The double circles A to F each hold one piece "
         "of gear - two start face up. Stop on one and mark it on your sheet. Each "
         "piece does one thing forever: the sword adds +1 to attacks, the shield "
         "+1 to defense, the javelin +1 against a claimant, the dagger wins ties, "
         "the helmet reveals a district once, the armor saves you once. In a duel "
         "you count your one best bonus - never a sum."),
        ("Prestige (60 seconds)", "This coin symbol is Prestige - political clout. "
         "Earn it at a star space: stop there, roll one die, 4 or higher pays 1. "
         "Win a duel: also 1. Lose a duel: pay 1 back to the bank. You can hold "
         "three. You will spend it on friends and on challenges."),
        ("Factions (45 seconds)", "Three groups can back you: the Army at F, the "
         "officials one circle east of the crossing, the elites at A. Walk to their "
         "meeting place and pay 1 Prestige - that faction now supports you for the "
         "rest of the game. Get two different factions behind you."),
        ("The endgame (60 seconds)", "When someone holds all six items they claim "
         "at the crossing - the Peristyle - and the succession begins: one more "
         "round, then the race to the throne. Stand at the Peristyle with two "
         "supporters and proclaim. Your rivals now have two full rounds to stop "
         "you: move next to you, pay 1 Prestige, and duel. Win the duel and the "
         "claim dies. Nobody does it in time and you are emperor."),
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
                "move next to them, put 1 Prestige aside (the fee), then each roll "
                "one die and add your one best item bonus. Higher total wins; the "
                "pugio wins ties.",
             19, y, PW - 38, size=9.4) - 1.4
    y = para(c, "Answer everything else when it comes up. Rare cases live in the "
                "rulebook, not in the introduction.", 19, y, PW - 38, size=9.4,
             font="Times-Italic")
    doc_footer(c, page, 1)
    c.showPage()
    c.save()


def playtest_form_pdf(path):
    c = new_doc(path, "Diocletian's Palace - playtest form")
    for page in (1, 2):
        doc_header(c, "PLAYTEST RECORD", "observations only - no invented results")
        y = PH - 36
        lines = [("", 8), ("Date ______________    Game version V0.9.2    "
                           "Played before? yes / no", 9)]
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
                ("THE NEW BOARD", ["Did anyone cross the middle for B, E or the inner "
                                   "stars? yes / hardly / no",
                                   "Did the two start-revealed treasures change first "
                                   "moves? yes / no",
                                   "Gate distances felt fair? P0 ____ P1 ____ P2 ____ "
                                   "P3 ____"]),
                ("THE CLAIM", ["Claims proclaimed: ____  Challenged: ____  "
                               "Canceled: ____  Crowned: ____",
                               "Did the two-round claim window feel tense or empty? "
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
    c = new_doc(path, "Diocletian's Palace - print and assembly instructions")
    doc_header(c, "PRINT AND ASSEMBLE", "everything prints on plain A4, black ink, 100% scale")

    # Page 1: printing, scale check, cutting.
    y = PH - 36
    c.setFont("Times-Bold", 11)
    c.drawString(16 * mm, y * mm, "1. Print")
    y -= 5.4
    for line in ("Board file 'dioclet-board-4xA4': four pages, A4 LANDSCAPE, "
                 "scale 100% (Actual size). Do not tick 'fit to page'.",
                 "Every other file: A4 portrait, 100%.",
                 "Any black-and-white printer works. Single-sided printing is fine.",
                 "Paper is enough. Card stock makes the cards nicer, but is not "
                 "required."):
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
    for line in ("Cut out the six treasure cards, the six card backs, and every "
                 "token on the tokens page.",
                 "Fold each pawn in half on the middle line and tape or glue it so "
                 "it stands up. A coin works just as well.",
                 "Leave the four board pages uncut for now - they are trimmed "
                 "during assembly (next page)."):
        y = bullet(c, line, 19, y, PW - 38, size=9.4)
    doc_footer(c, 1)
    c.showPage()

    # Page 2: board assembly with diagram.
    doc_header(c, "PRINT AND ASSEMBLE", "tape four pages into one board (about 58 x 41 cm)")
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
                 "Optional: glue the finished board onto a folder or thin "
                 "cardboard. Not required for play."):
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


# The rulebook, sheets, and reference hard-code these numbers in prose.
# If the released rules ever move, stop and rewrite the text rather than
# print a kit that teaches the wrong game. Tests re-check every pair
# against the rules file so drift fails loudly.
PRINTED_RULES_VALUES = {
    ("succession", "contest_cost"): 1,
    ("succession", "challenge_cost"): 1,
    ("succession", "challenge_bonus"): 0,
    ("succession", "claim_window_rounds"): 2,
    ("succession", "duel_loser_cost"): 1,
    ("succession", "proclaim_cost"): 0,
    ("succession", "required_support"): 2,
    ("succession", "support_cost"): 1,
    ("glory", "cap"): 3,
    ("glory", "guard_post_success_min_roll"): 4,
    ("glory", "guard_post_reward"): 1,
    ("glory", "duel_win_reward"): 1,
    ("glory", "first_challenger_reward"): 0,
    ("movement", "dice_count"): 2,
    ("movement", "die_sides"): 6,
    ("movement", "duel_range"): 2,
    ("level1", "max_rounds"): 24,
    ("level1", "grace_full_rounds"): 1,
    ("level2", "max_rounds"): 24,
    ("combat", "tie_goes_to_defender"): False,
}

# Prose facts that do not fit the (section, key) shape above.
PRINTED_TOP_LEVEL = {
    "start_reveals": 2,
}
PRINTED_ABILITIES = {
    "pugio": ("win_ties", 1),
    "pilum": ("attack_vs_claimant", 1),
    "galea": ("reveal_district", 1),
    "scutum": ("defense_bonus", 1),
    "gladius": ("attack_bonus", 1),
    "lorica_segmentata": ("prevent_displacement", 1),
}


def main():
    rules_file = (sys.argv[sys.argv.index("--rules") + 1]
                  if "--rules" in sys.argv else RULES_FILE)
    rules = engine.load_rules(rules_file)
    validate_six_block_layout(rules)
    if rules.get("gameplay_mode") != "succession-v1":
        raise SystemExit("this kit needs the succession-v1 ruleset")
    for (section, key), value in PRINTED_RULES_VALUES.items():
        actual = rules[section].get(key)
        if actual is None and value == 0:
            actual = 0   # the engine reads absent cost keys as free
        if actual != value:
            raise SystemExit(
                f"printed text assumes {section}.{key} == {value}, "
                f"rules say {rules[section].get(key)}; update the kit prose")
    for key, value in PRINTED_TOP_LEVEL.items():
        if rules.get(key) != value:
            raise SystemExit(
                f"printed text assumes {key} == {value}, "
                f"rules say {rules.get(key)}; update the kit prose")
    abilities = rules["combat"].get("abilities")
    if abilities != {name: {"type": kind, "value": value}
                     for name, (kind, value) in PRINTED_ABILITIES.items()}:
        raise SystemExit("printed text assumes the six one-line item "
                         "abilities in PRINTED_ABILITIES; update the kit prose")
    L = build_layout(rules)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = lambda name: os.path.join(OUT_DIR, name)
    files = {
        "board": out("dioclet-board-4xA4-BW.pdf"),
        "sheets": out("dioclet-player-sheets-A4-BW.pdf"),
        "cards": out("dioclet-cards-tokens-A4-BW.pdf"),
        "rulebook": out("dioclet-rulebook-A4-BW.pdf"),
        "quick": out("dioclet-quick-reference-A4-BW.pdf"),
        "teaching": out("dioclet-teaching-guide-A4-BW.pdf"),
        "form": out("dioclet-playtest-form-A4-BW.pdf"),
        "instructions": out("dioclet-print-instructions-A4-BW.pdf"),
    }
    board_pdf(files["board"], L)
    player_sheets_pdf(files["sheets"])
    cards_tokens_pdf(files["cards"])
    rulebook_pdf(files["rulebook"])
    quick_reference_pdf(files["quick"])
    teaching_guide_pdf(files["teaching"])
    playtest_form_pdf(files["form"])
    print_instructions_pdf(files["instructions"])
    combine([files["board"], files["instructions"], files["rulebook"], files["quick"],
             files["teaching"], files["sheets"], files["cards"], files["form"]],
            out("dioclet-complete-print-kit-A4-BW.pdf"))
    b = L["board"]
    manifest = {
        "version": KIT_VERSION,
        "rules_file": rules_file,
        "rules_hash": engine.rules_hash(rules),
        "counts": {"street_spaces": len(L["spaces"]), "blocked": len(b.blocked),
                   "buildings": len(rules["board"]["buildings"]),
                   "gates": len(b.gates), "districts": len(b.districts),
                   "glory_posts": len(b.glory_posts)},
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
                "glory_posts": [list(map(round, L["pos"](tuple(cell)))) for cell in b.glory_posts],
                "factions": {name: [round(v, 2) for v in L["pos"](tuple(cell))]
                             for name, cell in rules["succession"]["factions"].items()},
            },
        },
        "files": files,
    }
    with open(out("kit-manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print(f"wrote {len(files) + 1} PDFs + kit-manifest.json into {OUT_DIR}/")
    for name, path in files.items():
        print(f"  {name}: {path} ({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    main()
