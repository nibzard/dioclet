"""Export the print-kit geometry for the JavaScript art renderer.

The color art must place every street space, gate, and meeting place
exactly where the black-and-white kit prints them. This script asks
the kit's own layout functions for those positions and writes them to
art/build/layout.json. The renderer never computes board geometry on
its own.

Coordinates in the output are millimetres with the origin at the
top-left corner of each artwork and y growing downward (canvas
convention). The kit's PDF layout uses a bottom-left origin.

Usage: python3 art/export_layout.py [--rules rules_v094_twinboard.json]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import engine  # noqa: E402
import make_a4_print_kit as kit  # noqa: E402


def palace(rules):
    L = kit.build_layout(rules)
    b = L["board"]
    ax0, ay0, ax1, ay1 = L["art"]

    def flip(x, y):
        return [round(x - ax0, 3), round(ay1 - y, 3)]

    def at(cell):
        return flip(*L["pos"](tuple(cell)))

    cell = kit.CELL
    buildings = []
    for bld in rules["board"]["buildings"]:
        x0 = kit.ML + bld["x0"] * cell
        top = kit.MB + (L["rows"] - bld["y0"]) * cell
        w = (bld["x1"] - bld["x0"] + 1) * cell
        h = (bld["y1"] - bld["y0"] + 1) * cell
        buildings.append({"district": bld["district"], "name": bld["name"],
                          "rect": flip(x0, top) + [w, h]})
    gx0, gy0, gw, gh = L["grid"]
    return {
        "size_mm": [ax1 - ax0, ay1 - ay0],
        "cell_mm": cell,
        "grid_mm": flip(gx0, gy0 + gh) + [gw, gh],
        # The kit's decorative border, kept clear of page-edge trims.
        "border_mm": flip(19.0, ay1 - 7.0) + [(ax1 - 6.0) - 19.0, (ay1 - 7.0) - 16.0],
        "cut_mm": {"x": round(L["cut"]["x"] - ax0, 3), "y": round(ay1 - L["cut"]["y"], 3)},
        "reg_marks_mm": [flip(x, y) for x, y in L["reg_marks"]],
        "spaces": [{"cell": list(c), "mm": flip(x, y)} for c, (x, y) in L["spaces"]],
        "buildings": buildings,
        "districts": {k: at(v) for k, v in b.districts.items()},
        "gates": {k: at(v) for k, v in b.gates.items()},
        "gate_names": kit.GATE_NAMES,
        "glory_posts": [at(c) for c in b.glory_posts],
        "checkpoint": at(b.checkpoint),
        "streets": rules["board"]["streets"],
        "rows": L["rows"], "cols": L["cols"],
    }


def succession(rules):
    S = kit.build_succession_layout(rules)
    b = S["board"]
    ph = kit.PAGE_H

    def flip(x, y):
        return [round(x, 3), round(ph - y, 3)]

    def at(cell):
        return flip(*S["pos"](tuple(cell)))

    cell = kit.SCELL
    blocks = []
    for x0, y0, x1, y1 in S["blocks"]:
        left = kit.SML + x0 * cell
        top = kit.SMB + (S["rows"] - y0) * cell
        blocks.append(flip(left, top) + [(x1 - x0 + 1) * cell, (y1 - y0 + 1) * cell])
    return {
        "size_mm": [kit.PAGE_W, kit.PAGE_H],
        "cell_mm": cell,
        "grid_mm": flip(kit.SML, kit.SMB + S["grid_h"]) + [S["grid_w"], S["grid_h"]],
        "spaces": [{"cell": list(c), "mm": flip(x, y)} for c, (x, y) in S["spaces"]],
        "blocks": blocks,
        "gates": {k: at(v) for k, v in b.gates.items()},
        "checkpoint": at(b.checkpoint),
        "factions": {k: at(v) for k, v in rules["succession"]["factions"].items()},
        "rows": S["rows"], "cols": S["cols"],
    }


def main():
    rules_file = (sys.argv[sys.argv.index("--rules") + 1]
                  if "--rules" in sys.argv else kit.RULES_FILE)
    rules = engine.load_rules(os.path.join(ROOT, rules_file))
    abilities = rules["combat"]["abilities"]
    layout = {
        "rules_file": rules_file,
        "rules_version": rules["rules_version"],
        "rules_hash": engine.rules_hash(rules),
        "palace": palace(rules),
        "succession": succession(rules),
        "cards": {
            "size_mm": [kit.CARD_W, kit.CARD_H],
            "items": [{"name": name, "icon": icon, "text": text}
                      for name, icon, text in kit.CARDS],
            "abilities": abilities,
        },
    }
    out_dir = os.path.join(ROOT, "art", "build")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "layout.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(layout, fh, indent=1, sort_keys=True)
    print(f"wrote {os.path.relpath(path, ROOT)} for {rules['rules_version']}")


if __name__ == "__main__":
    main()
