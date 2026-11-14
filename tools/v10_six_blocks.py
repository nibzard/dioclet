#!/usr/bin/env python3
"""V0.10 six-block succession map: geometry search, arm files, and screen.

Question (2026-11-14, from the designer): the succession map has four
blocks but six faction cards. Can it use the palace's six blocks (3 x 2),
one card per block, and stay fair?

The six-block map is the palace street grid: streets on rows 0, 6, 12
and columns 0, 6, 12, 18 (97 street spaces). The 0.10.1 gates stay as
they are: P0 (6,0), P1 (18,6), P2 (12,12), P3 (0,6). The Peristyle is
(9,6), the centre of the middle street, so every gate is 9 steps from it.

    python3 tools/v10_six_blocks.py search
        List every fair card set and the post sets for each arm.
    python3 tools/v10_six_blocks.py write
        Write rules_v10_six_<arm>.json for the arms in ARMS.
    python3 tools/v10_six_blocks.py screen [--games 768] [--seed-base 1070000]
        Play the four frozen probe profiles on 0.10.1 and on every arm.

A card set is fair when it looks the same after a half-turn, every
block gets exactly one card, and every gate sees the same sorted street
distances to the six cards. A post set is fair under the same
conditions, with all four posts the same distance from the Peristyle.
Bot profiles only - these numbers say nothing about human fun.
"""
import argparse
import collections
import concurrent.futures
import itertools
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools")]

import engine  # noqa: E402
import v10_prestige_experiment as px  # noqa: E402
from v10_level2_experiment import summarize  # noqa: E402

W, H = 19, 13
STREET_COLS, STREET_ROWS = (0, 6, 12, 18), (0, 6, 12)
BLOCK_COLS, BLOCK_ROWS = ((1, 5), (7, 11), (13, 17)), ((1, 5), (7, 11))
GATES = {"P0": (6, 0), "P1": (18, 6), "P2": (12, 12), "P3": (0, 6)}
CHECKPOINT = (9, 6)
BASE_FILE = "rules_v0101_bigboard.json"

# Three card spreads from the search, far to near (Peristyle distances
# in brackets). Each is listed with its faction-placeholder cells first.
ARMS = {
    "spread": [(3, 0), (15, 12), (3, 6), (15, 6), (7, 6), (11, 6)],   # 2,2,6,6,12,12
    "ring": [(6, 1), (12, 11), (1, 6), (17, 6), (7, 6), (11, 6)],     # 2,2,8,8,8,8
    "near": [(6, 4), (12, 8), (4, 6), (14, 6), (8, 6), (10, 6)],      # 1,1,5,5,5,5
}

STREET = {(x, y) for x in range(W) for y in range(H) if x in STREET_COLS or y in STREET_ROWS}


def rot(c):
    return (W - 1 - c[0], H - 1 - c[1])


def distances(start):
    d, queue = {start: 0}, collections.deque([start])
    while queue:
        cur = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in STREET and nxt not in d:
                d[nxt] = d[cur] + 1
                queue.append(nxt)
    return d


GATE_DIST = {pid: distances(c) for pid, c in GATES.items()}
CP_DIST = distances(CHECKPOINT)
BLOCKS = [(i, j) for i in range(3) for j in range(2)]


def blocks_touching(cell):
    out = set()
    for i, (x0, x1) in enumerate(BLOCK_COLS):
        for j, (y0, y1) in enumerate(BLOCK_ROWS):
            if any(x0 <= cell[0] + dx <= x1 and y0 <= cell[1] + dy <= y1
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out.add((i, j))
    return out


def one_per_block(sites):
    return any(all(b in blocks_touching(s) for s, b in zip(sites, perm))
               for perm in itertools.permutations(BLOCKS))


def gate_profile(cells):
    profiles = {pid: tuple(sorted(GATE_DIST[pid][c] for c in cells)) for pid in GATES}
    return profiles["P0"] if len(set(profiles.values())) == 1 else None


def fair_card_sets():
    banned = set(GATES.values()) | {CHECKPOINT}
    cells = sorted(c for c in STREET if c not in banned and blocks_touching(c) and c < rot(c))
    found = []
    for trio in itertools.combinations(cells, 3):
        sites = list(trio) + [rot(c) for c in trio]
        if len(set(sites)) == 6 and one_per_block(sites) and gate_profile(sites):
            found.append(sorted(sites))
    return found


def fair_post_sets(sites):
    """Half-turn pairs, equal gate profiles, all posts equally far from the Peristyle."""
    banned = set(GATES.values()) | {CHECKPOINT} | set(sites)
    cells = sorted(c for c in STREET if c not in banned and c < rot(c))
    found = []
    for a, b in itertools.combinations(cells, 2):
        posts = [a, rot(a), b, rot(b)]
        if len({CP_DIST[p] for p in posts}) == 1 and gate_profile(posts):
            near = min(abs(p[0] - s[0]) + abs(p[1] - s[1]) for p in posts for s in sites)
            found.append((posts, CP_DIST[a], near))
    return found


def pick_posts(sites):
    """Prefer 0.10.1's 12 steps from the Peristyle, then posts far from the cards."""
    options = fair_post_sets(sites)
    if not options:
        raise SystemExit(f"no fair post set for {sites}")
    return min(options, key=lambda o: (abs(o[1] - 12), -o[2], o[0]))[0]


def arm_rules(name):
    rules = engine.load_rules(os.path.join(ROOT, BASE_FILE))
    sites = ARMS[name]
    twin = rules["board_level2"]
    twin["blocked"] = [[x, y] for y in range(H) for x in range(W) if (x, y) not in STREET]
    twin["support_sites"] = [list(c) for c in sites]
    twin["glory_posts"] = [list(c) for c in pick_posts(sites)]
    for faction, cell in zip(sorted(rules["succession"]["factions"]), sites):
        rules["succession"]["factions"][faction] = list(cell)
    rules["rules_version"] = f"0.10.1-exp-six-{name}"
    rules["game_name"] = ("Diocletian's Palace: Six Treasures "
                          f"(V0.10.1 experiment: six-block succession map, {name} cards)")
    return rules


def rules_file(name):
    return f"rules_v10_six_{name}.json"


def cmd_search(_args):
    sets = fair_card_sets()
    print(f"street spaces {len(STREET)}; gate to Peristyle "
          f"{ {pid: GATE_DIST[pid][CHECKPOINT] for pid in GATES} }")
    print(f"{len(sets)} fair card sets (one card per block):")
    for sites in sorted(sets, key=lambda s: sorted(CP_DIST[c] for c in s)):
        print(f"  {sites}  gates see {gate_profile(sites)}  "
              f"Peristyle {sorted(CP_DIST[c] for c in sites)}")
    for name, sites in ARMS.items():
        assert sorted(sites) in sets, name
        print(f"{name}: posts {pick_posts(sites)}")


def cmd_write(_args):
    for name in ARMS:
        rules = arm_rules(name)
        engine.validate_rules(rules)
        with open(os.path.join(ROOT, rules_file(name)), "w") as fh:
            json.dump(rules, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("wrote", rules_file(name), "posts", rules["board_level2"]["glory_posts"])


def cmd_screen(args):
    px.ARMS.clear()
    px.ARMS["base"] = BASE_FILE
    px.ARMS.update({f"six_{n}": rules_file(n) for n in ARMS})
    summary = {"seed_base": args.seed_base, "games": args.games, "arms": {}}
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for arm in px.ARMS:
            jobs = [(arm, "probes", i, args.seed_base) for i in range(args.games)]
            games = list(pool.map(px.play_one, jobs, chunksize=8))
            s = summarize(arm, games)
            able = [a for g in games for a in g["claim_able"]]
            s["claims_no_rival_can_contest"] = round(sum(a == 0 for a in able) / len(able), 4)
            s["mean_rivals_able_to_contest"] = round(statistics.mean(able), 3)
            s["phase2_turns_at_zero_prestige"] = round(
                sum(g["broke_turns"] for g in games) / sum(g["phase2_turns"] for g in games), 4)
            s["searches_per_game"] = round(statistics.mean(g["searches"] for g in games), 2)
            summary["arms"][arm] = s
            g, l2 = s["gate_win_rates"], s["level2_rounds"]
            print(f"{arm:12} draws {s['draw_rate']:.3f} L2 {l2['p10']}/{l2['median']}/{l2['p90']} "
                  f"gates {'/'.join(f'{g[p][0]:.3f}' for p in ('P0', 'P1', 'P2', 'P3'))} "
                  f"p {s['gate_uniformity_p']} claims {s['claims_per_game']} "
                  f"searches {s['searches_per_game']} farmer {s['winning_profiles'].get('prestige_farmer')}",
                  flush=True)
    out = args.out or os.path.join(ROOT, "results", "v10-six-blocks",
                                   f"screen-{args.seed_base}-{args.games}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(summary, fh, indent=2)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("search")
    sub.add_parser("write")
    sc = sub.add_parser("screen")
    sc.add_argument("--games", type=int, default=768)
    sc.add_argument("--seed-base", type=int, default=1070000)
    sc.add_argument("--out")
    args = ap.parse_args()
    {"search": cmd_search, "write": cmd_write, "screen": cmd_screen}[args.cmd](args)


if __name__ == "__main__":
    main()
