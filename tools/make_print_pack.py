#!/usr/bin/env python3
# ABOUTME: Generate the printable succession playtest pack
# ABOUTME: (playtest/playtest-pack.html) from the adopted rules file.
"""Generate the printable succession playtest pack (playtest/playtest-pack.html).

Renders the palace board (all 97 street spaces and the six building
blocks), the equipment cards, player trackers, the rulebook, and a
feedback form. Print with a browser at 100% scale; every section is
one page.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine  # noqa: E402
from board import Board, validate_six_block_layout  # noqa: E402

RULES_FILE = "rules/imperial-rivals-v0.10.2.json"
OUT_FILE = "playtest/playtest-pack.html"

CELL = 44
PAD = 34


def board_svg(rules):
    b = Board(rules)
    w = PAD * 2 + b.width * CELL
    h = PAD * 2 + b.height * CELL

    def cx(x):
        return PAD + x * CELL + CELL / 2

    def cy(y):
        return PAD + y * CELL + CELL / 2

    parts = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Game board">']
    parts.append(f'<rect width="{w}" height="{h}" fill="#f6efe2"/>')
    parts.append(f'<rect x="10" y="10" width="{w-20}" height="{h-20}" rx="0" '
                 f'fill="none" stroke="#9c8a64" stroke-width="5"/>')
    # Every footprint is fully blocked. No street cuts through it.
    for bld in rules["palace"]["map"]["buildings"]:
        px, py = PAD + bld["x0"] * CELL, PAD + bld["y0"] * CELL
        pw = (bld["x1"] - bld["x0"] + 1) * CELL
        ph = (bld["y1"] - bld["y0"] + 1) * CELL
        parts.append(
            f'<rect x="{px+2}" y="{py+2}" width="{pw-4}" height="{ph-4}" '
            f'rx="0" fill="#c96b4f" stroke="#9c4a33" stroke-width="1.5"/>')
    # street circles
    for x in range(b.width):
        for y in range(b.height):
            if (x, y) not in b.blocked:
                parts.append(
                    f'<circle cx="{cx(x)}" cy="{cy(y)}" r="13" fill="#fffdf6" '
                    f'stroke="#b7a77f" stroke-width="2"/>')
    # specials
    def chip(x, y, fill, text, tsize=15, ring="#00000022"):
        return (f'<circle cx="{cx(x)}" cy="{cy(y)}" r="16.5" fill="{fill}" '
                f'stroke="#3a2d20" stroke-width="2.5"/>' +
                f'<text x="{cx(x)}" y="{cy(y)+tsize/2-1}" text-anchor="middle" '
                f'font-family="Georgia, serif" font-size="{tsize}" font-weight="bold" '
                f'fill="#fffdf6">{text}</text>')
    s = []
    for pid, (x, y) in b.gates.items():
        side = {"P0": "N", "P1": "E", "P2": "S", "P3": "W"}[pid]
        s.append(chip(x, y, "#5a3d6b", side))
    for name, (x, y) in b.districts.items():
        s.append(chip(x, y, "#3f6f9e", name, 16))
    s.append(chip(*b.checkpoint, "#c9972b", "X", 16))
    for (x, y) in b.guard_posts:
        s.append(chip(x, y, "#5f7a4a", "*", 18))
    for faction, (x, y) in engine._faction_cells(rules).items():
        label = {"army": "A", "officials": "O", "elites": "C"}[faction]
        s.append(f'<rect x="{cx(x)+10}" y="{cy(y)-25}" width="18" height="16" fill="#203d35"/>')
        s.append(f'<text x="{cx(x)+19}" y="{cy(y)-13}" text-anchor="middle" font-size="9" fill="#fffdf6">{label}</text>')
    parts.extend(s)
    # The main axes use existing streets; no extra street splits a block.
    for tx, ty, label in ((cx(6), 24, "CARDO · N–S"),
                          (cx(10), cy(6) - 15, "DECUMANUS · E–W")):
        parts.append(f'<text x="{tx}" y="{ty}" text-anchor="middle" '
                     f'font-family="Verdana, sans-serif" font-size="8" '
                     f'fill="#7a6a4d">{label}</text>')
    # compass
    parts.append(
        f'<text x="{w-58}" y="{PAD-12}" text-anchor="middle" '
        f'font-family="Georgia, serif" font-size="13" fill="#7a6a4d">N O R T H</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def equipment_cards(rules):
    names = rules["treasures"]["items"]
    flavor = {
        "pugio": "A short dagger, easy to carry.",
        "pilum": "A throwing javelin.",
        "galea": "A legionary helmet.",
        "scutum": "A tall curved shield.",
        "gladius": "The Roman short sword.",
        "lorica_segmentata": "Banded plate armor.",
    }
    cards = "".join(
        f'<div class="eqcard"><div class="eqname">{n.replace("_", " ")}</div>'
        f'<div class="eqflavor">{flavor.get(n, "")}</div>'
        f'<div class="eqfoot">Treasure of the city</div></div>'
        for n in names)
    return f'<div class="eqgrid">{cards}</div>'


def main():
    rules_path = sys.argv[sys.argv.index("--rules") + 1] if "--rules" in sys.argv else RULES_FILE
    rules = engine.load_rules(rules_path)
    validate_six_block_layout(rules)
    from tools.succession_content import printable_pack
    html = printable_pack(rules, board_svg(rules), equipment_cards(rules))
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT_FILE
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {out} ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
