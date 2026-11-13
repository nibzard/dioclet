#!/usr/bin/env python3
"""V0.9 geometry sweep: the playtest's board-shape questions.

The 2026-11-12 session asked for more geometries: nobody crosses the
middle, and seats near the Peristyle hold unreachable claims. Screens
cell placements on matched seeds (same gate/policy schedule as the
climb): an equidistant crossing, interior treasures, spread guard
posts, and their combinations. Adds the geometry metrics the climb
lacks: per-gate win rates, a street-class traffic profile, and
per-district exploration balance.

Seeds: screens 940000+, confirmation 950000+ (nothing burned).
"""
import concurrent.futures
import copy
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import engine  # noqa: E402
import policies  # noqa: E402
from v09_hillclimb import GATES, check_gates, metrics, schedule  # noqa: E402

OUT_ROOT = os.path.join(ROOT, "results", "v09-geometry")
GAMES_PER_SCREEN = 96
CONFIRM_GAMES = 384
SCREEN_BASE = 940000
CONFIRM_BASE = 950000

# Predeclared geometry gate: with 96 games and uniform gate assignment
# each gate wins about 24 (binomial sigma ~4.2); 0.13-0.37 is ~3 sigma.
GATE_WIN_RANGE = (0.13, 0.37)

# Symmetry note: the map is symmetric under (x, y) -> (18-x, 12-y),
# which pairs gates P0<->P2, P3<->P1 and districts A<->F, B<->E, C<->D.
# validate_six_block_layout pins gates to the ends of the cardo and
# decumanus and the checkpoint to their crossing, so a moved crossing
# requires moved gates, and an equidistant crossing requires a centered
# cardo, which requires re-blocking the map.
CARDO12 = {
    "board": {"gates": {"P0": [12, 0], "P1": [18, 6], "P2": [12, 12], "P3": [0, 6]},
              "checkpoint": [12, 6],
              "streets": {"cardo": {"axis": "north-south", "coordinate": 12},
                          "decumanus": {"axis": "east-west", "coordinate": 6},
                          "secondary": {"axis": "north-south", "coordinate": 6}},
              "level2_sites": {"cellars": [3, 0], "guard_barracks": [15, 12],
                               "peristyle": [12, 6], "emperor": [6, 12],
                               "retreat": [6, 11]}},
    "succession": {"factions": {"army": [15, 12], "officials": [13, 6],
                                "elites": [3, 0]}},
}
POSTS = {"board": {"glory_posts": [[6, 2], [12, 2], [6, 10], [12, 10]]}}
MIDPAIR = {"board": {"districts": {"A": [3, 0], "B": [12, 3], "C": [15, 0],
                                   "D": [3, 12], "E": [6, 9], "F": [15, 12]}}}


def centered_board():
    """A six-block map with the cardo centered (coordinate 9): every
    gate sits 9 steps from the crossing by construction, and the whole
    map keeps the (x, y) -> (18-x, 12-y) symmetry. Two extra gap
    streets (column 4 north, column 14 south) cut through the wide
    blocks so interior routes pay off."""
    width, height = 19, 13
    open_cells = set()
    for y in (0, 6, 12):                      # rim rows and the decumanus
        open_cells.update((x, y) for x in range(width))
    for x in (0, 18):                         # side streets
        open_cells.update((x, y) for y in range(height))
    for y in range(1, 6):                     # cardo north of the crossing
        open_cells.add((9, y))
    for y in range(7, 12):                    # cardo south of the crossing
        open_cells.add((9, y))
    for y in range(1, 6):                     # north gap street
        open_cells.add((4, y))
    for y in range(7, 12):                    # south gap street
        open_cells.add((14, y))
    blocked = sorted([x, y] for x in range(width) for y in range(height)
                     if (x, y) not in open_cells)
    return {
        "width": width, "height": height,
        "gates": {"P0": [9, 0], "P1": [18, 6], "P2": [9, 12], "P3": [0, 6]},
        "checkpoint": [9, 6],
        "districts": {"A": [2, 0], "B": [6, 0], "C": [14, 0],
                      "D": [4, 12], "E": [12, 12], "F": [16, 12]},
        "glory_posts": [[0, 3], [4, 3], [14, 9], [18, 9]],
        "level2_sites": {"cellars": [3, 0], "guard_barracks": [15, 12],
                         "peristyle": [9, 6], "emperor": [5, 0], "retreat": [13, 12]},
        "blocked": blocked,
        "buildings": [
            {"name": "northwest", "x0": 1, "y0": 1, "x1": 3, "y1": 5, "district": "A"},
            {"name": "north-cardo-west", "x0": 5, "y0": 1, "x1": 8, "y1": 5, "district": "B"},
            {"name": "northeast", "x0": 10, "y0": 1, "x1": 17, "y1": 5, "district": "C"},
            {"name": "southwest", "x0": 1, "y0": 7, "x1": 8, "y1": 11, "district": "D"},
            {"name": "south-cardo-east", "x0": 10, "y0": 7, "x1": 13, "y1": 11, "district": "E"},
            {"name": "southeast", "x0": 15, "y0": 7, "x1": 17, "y1": 11, "district": "F"},
        ],
        "streets": {"cardo": {"axis": "north-south", "coordinate": 9},
                    "decumanus": {"axis": "east-west", "coordinate": 6},
                    "secondary": {"axis": "north-south", "coordinate": 4}},
    }


CENTERED = {"board": centered_board(),
            "succession": {"factions": {"army": [16, 12], "officials": [10, 6],
                                        "elites": [2, 0]}}}


def apply_patch(base, *patches):
    rules = copy.deepcopy(base)
    for patch in patches:
        for section, values in patch.items():
            if isinstance(rules.get(section), dict) and isinstance(values, dict):
                rules[section].update(values)
            else:
                rules[section] = values
    return rules


def street_class(cell):
    """Classify one street cell: rim, the two interior columns, the
    interior row, or another interior street cell (there are none on
    this grid, so the fallback only guards future maps)."""
    x, y = cell
    if y in (0, 12) or x in (0, 18):
        return "rim"
    if x == 6:
        return "col6"
    if x == 12:
        return "col12"
    if y == 6:
        return "row6"
    return "other"


def records_of(state):
    events = state["events"]
    if isinstance(events, dict):
        for round_records in events.values():
            yield from round_records
    else:
        yield from events


def play_geo(rules, seed, game_id, assignment):
    """Identical driver to v09_hillclimb.play, but also returns the
    movement traffic and district exploration data."""
    state = engine.new_game(rules, seed, game_id, assignment)
    rng = random.Random(f"probe:{seed}")
    cap = 4 * (rules["level1"]["max_rounds"] + rules["level2"]["max_rounds"] + 3)
    for _ in range(cap):
        if engine.is_finished(state):
            break
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act(assignment[state["active_player"]], obs, rng)
        engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
    if not engine.is_finished(state):
        raise RuntimeError(f"{game_id} exceeded its turn bound")
    engine.check_invariants(state)
    result = engine.result(state)
    steps = {key: 0 for key in ("rim", "col6", "col12", "row6", "other")}
    cell_district = {tuple(cell): name for name, cell in rules["board"]["districts"].items()}
    explored = {name: 0 for name in sorted(rules["board"]["districts"])}
    for record in records_of(state):
        action = record.get("action", {})
        path = action.get("path")
        if path:
            for a, b in zip(path, path[1:]):
                steps[street_class([(a[0] + b[0]) // 2, (a[1] + b[1]) // 2])] += 1
        if action.get("kind") == "explore":
            name = cell_district.get(tuple(action["destination"]))
            if name:
                explored[name] += 1
    return result, steps, explored


def wilson(wins, games):
    if not games:
        return None
    z = 1.959963984540054
    rate = wins / games
    denominator = 1 + z * z / games
    center = (rate + z * z / (2 * games)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / games + z * z / (4 * games * games)) / denominator
    return [round(rate, 4), round(max(0.0, center - radius), 4), round(min(1.0, center + radius), 4)]


def geo_metrics(rules, seed_base, games):
    results, all_steps, all_explored = [], [], []
    for index in range(games):
        gate_order, assignment = schedule(index)
        game_rules = copy.deepcopy(rules)
        game_rules["succession"]["gate_assignment"] = "manual"
        game_rules["succession"]["gate_order"] = list(gate_order)
        result, steps, explored = play_geo(game_rules, seed_base + index,
                                           f"g{seed_base + index}", assignment)
        results.append(result)
        all_steps.append(steps)
        all_explored.append(explored)
    # Hill-climb fields (same formulas) plus the geometry metrics.
    wins = sum(1 for r in results if r["outcome"] == "win")
    rounds = sorted(r["total_rounds"] for r in results)
    strategy_wins, strategy_games = {}, {}
    claimant_wins = claimant_games = claims = decided = 0
    gate_wins = {pid: 0 for pid in sorted(results[0]["gate_assignments"])}
    for r in results:
        claims += sum(p["claims_made"] for p in r["players"].values())
        decided += r["end_reason"] in ("survived_window", "acclamation")
        if r["first_challenger"]:
            claimant_games += 1
            claimant_wins += 1 if r["first_challenger_won"] else 0
        for pid, p in r["players"].items():
            profile = r["policies"][pid]
            strategy_games[profile] = strategy_games.get(profile, 0) + 1
            if r["winner"] == pid:
                strategy_wins[profile] = strategy_wins.get(profile, 0) + 1
                gate_wins[p["gate_id"]] = gate_wins.get(p["gate_id"], 0) + 1
    totals = {key: 0 for key in ("rim", "col6", "col12", "row6", "other")}
    for steps in all_steps:
        for key, value in steps.items():
            totals[key] += value
    step_sum = sum(totals.values())
    districts = sorted(rules["board"]["districts"])
    explored_avg = {name: round(sum(e[name] for e in all_explored) / games, 3)
                    for name in districts}
    return {
        "games": games, "draws": games - wins, "draw_rate": round((games - wins) / games, 4),
        "median_rounds": rounds[games // 2],
        "strategy_rates": {p: round(strategy_wins.get(p, 0) / strategy_games[p], 4)
                           for p in strategy_games},
        "claims_per_game": round(claims / games, 3),
        "first_claimant_win_rate": round(claimant_wins / claimant_games, 4) if claimant_games else None,
        "decided_by_claim_rate": round(decided / games, 4),
        "gate_win_rates": {pid: wilson(wins_, games) for pid, wins_ in gate_wins.items()},
        "interior_share": (round((totals["col6"] + totals["col12"] + totals["row6"] + totals["other"])
                                 / step_sum, 4) if step_sum else None),
        "street_shares": {key: round(value / step_sum, 4) for key, value in totals.items()}
                         if step_sum else {},
        "explored_per_district": explored_avg,
    }


def geo_check(inc, cand):
    passed, reasons = check_gates(
        {k: inc[k] for k in ("draw_rate", "median_rounds", "strategy_rates",
                             "claims_per_game", "first_claimant_win_rate",
                             "decided_by_claim_rate")},
        cand)
    lo, hi = GATE_WIN_RANGE
    for pid, interval in cand["gate_win_rates"].items():
        if interval is None or not lo <= interval[0] <= hi:
            reasons.append(f"gate {pid} win rate {interval} outside [{lo}, {hi}]")
    return (not reasons), reasons


def run_arm(name, rules, seed_base, games):
    m = geo_metrics(rules, seed_base, games)
    m.pop("_base_marker", None)
    m["arm"] = name
    print(json.dumps(m), flush=True)
    return name, m


def confirm(arm_names, out_name="geometry_confirm.json"):
    """Reproduce the confirmation run with the committed code."""
    base = engine.load_rules(os.path.join(ROOT, "rules_v091_succession.json"))
    all_arms = {
        "inc": (),
        "midpair": (MIDPAIR,),
        "midpair_posts": (MIDPAIR, POSTS),
        "centered": (CENTERED,),
    }
    arms = {name: apply_patch(base, *all_arms[name]) for name in arm_names}
    for rules in arms.values():
        engine.validate_rules(rules)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(len(arms), 2)) as pool:
        futures = {name: pool.submit(run_arm, name, rules, CONFIRM_BASE, CONFIRM_GAMES)
                   for name, rules in arms.items()}
        results = {name: future.result()[1] for name, future in futures.items()}
    inc = results.get("inc")
    verdicts = {}
    for name, m in results.items():
        if name == "inc" or inc is None:
            continue
        passed, reasons = geo_check(inc, m)
        verdicts[name] = {"passed": passed, "reasons": reasons}
        print(f"{name}: {'PASS' if passed else 'FAIL'} {'; '.join(reasons)}", flush=True)
    payload = {"seed_base": CONFIRM_BASE, "games": CONFIRM_GAMES,
               "arms": results, "verdicts": verdicts,
               "arm_rules": {n: arms[n] for n in arms}}
    with open(os.path.join(OUT_ROOT, out_name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    print("wrote", os.path.join(OUT_ROOT, out_name), flush=True)


def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    base = engine.load_rules(os.path.join(ROOT, "rules_v091_succession.json"))
    all_arms = {
        "inc": (base,),
        "cardo12": (CARDO12,),
        "centered": (CENTERED,),
        "posts": (POSTS,),
        "midpair": (MIDPAIR,),
        "midpair_posts": (MIDPAIR, POSTS),
    }
    if "--confirm" in sys.argv[1:]:
        names = [n for n in sys.argv[1:] if n != "--confirm"]
        if "inc" not in names:
            names = ["inc"] + names
        return confirm(names)
    selected = sys.argv[1:] or list(all_arms)
    unknown = [name for name in selected if name not in all_arms]
    if unknown:
        raise SystemExit(f"unknown arms: {unknown}; choose from {sorted(all_arms)}")
    arms = {name: apply_patch(base, *all_arms[name]) for name in selected}
    for name, rules in arms.items():
        engine.validate_rules(rules)
    print(f"=== geometry screen: {len(arms)} arms x {GAMES_PER_SCREEN} matched seeds",
          flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(len(arms), 2)) as pool:
        futures = [pool.submit(run_arm, name, rules, SCREEN_BASE, GAMES_PER_SCREEN)
                   for name, rules in arms.items()]
        results = {}
        for future in concurrent.futures.as_completed(futures):
            name, m = future.result()
            results[name] = m
    inc = results.get("inc")
    verdicts = {}
    for name, m in results.items():
        if name == "inc" or inc is None:
            continue
        passed, reasons = geo_check(inc, m)
        verdicts[name] = {"passed": passed, "reasons": reasons}
        print(f"  {name}: {'PASS' if passed else 'FAIL'} {'; '.join(reasons)}", flush=True)
    payload = {"gates": GATES, "gate_win_range": GATE_WIN_RANGE,
               "screen": results, "verdicts": verdicts,
               "seed_base": SCREEN_BASE,
               "arms": {name: rules for name, rules in arms.items()}}
    with open(os.path.join(OUT_ROOT, "geometry_sweep.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    handle_path = os.path.join(OUT_ROOT, "geometry_sweep.json")
    print("wrote", handle_path, flush=True)


if __name__ == "__main__":
    main()
