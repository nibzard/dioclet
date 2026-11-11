#!/usr/bin/env python3
"""V0.9 design experiment: matched-seed A/B/C comparison.

Arms (notes/v09-experiment-plan.md):
  a-baseline   rules_v08_succession.json  (unchanged V0.8.1)
  b-reveal2    rules_v09_reveal2.json     (two districts public at start)
  c-abilities  rules_v09_abilities.json   (reveal2 + six item abilities,
                                           count-based combat tiers zeroed)

Every arm plays the same 480 seeds (base 300000) with the same seat schedule
as the V0.8 suites: 24 gate permutations cycle, probe profiles rotate after
each full block. Games are paired by index across arms.
"""
import collections
import concurrent.futures
import copy
import itertools
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import engine  # noqa: E402
import policies  # noqa: E402
import succession  # noqa: E402

IDS = succession.IDS
PROFILES = ("collector", "early_support", "prestige_farmer", "counterleader")
GAMES_PER_ARM = 480
SEED_BASE = 300000
OUT_ROOT = os.path.join(ROOT, "results", "v09-design-003")
ARMS = (
    ("a-baseline", "rules_v08_succession.json"),
    ("c-abilities", "rules_v09_abilities.json"),
    ("d-checkpoint3", "rules_v09_checkpoint3.json"),
)
ITEMS = ("gladius", "scutum", "pilum", "pugio", "galea", "lorica_segmentata")


def schedule(index):
    """Same pairing as tools/succession_experiments.py: for a fixed index,
    every arm gets the same gate permutation and policy assignment."""
    gate_permutations = tuple(itertools.permutations(IDS))
    gate_order = gate_permutations[index % len(gate_permutations)]
    policy_rotation = (index // len(gate_permutations)) % len(IDS)
    assignment = {pid: PROFILES[(i + policy_rotation) % len(PROFILES)]
                  for i, pid in enumerate(IDS)}
    return gate_order, assignment


def play_game(rules, seed, game_id, assignment):
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
    return state


def first_explore_districts(state):
    """District each player explored first, in seat order."""
    out = {}
    for pid in IDS:
        for record in state["events"]:
            if record["player"] != pid:
                continue
            for event in record["events"]:
                if event["type"] in ("district_revealed", "equipment_collected", "explore_no_gain"):
                    out[pid] = event["district"]
                    break
            if pid in out:
                break
    return out


def wilson(wins, games, z=1.96):
    if not games:
        return [0.0, 0.0]
    p = wins / games
    denom = 1 + z * z / games
    center = (p + z * z / (2 * games)) / denom
    half = z * math.sqrt(p * (1 - p) / games + z * z / (4 * games * games)) / denom
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def game_row(state):
    result = engine.result(state)
    firsts = first_explore_districts(state)
    setup_reveals = set(result["setup_reveals"])
    winner = result["winner"]
    row = {
        "game_id": result["game_id"], "seed": result["seed"],
        "outcome": result["outcome"], "winner": winner,
        "winner_gate": result["players"][winner]["gate_id"] if winner else None,
        "winner_profile": state["policies"][winner] if winner else None,
        "end_reason": result["end_reason"],
        "rounds_level1": result["rounds_level1"],
        "total_rounds": result["total_rounds"], "total_turns": result["total_turns"],
        "first_challenger": result["first_challenger"],
        "first_challenger_won": result["first_challenger_won"],
        "setup_reveals": sorted(setup_reveals),
        "first_explore": firsts,
        "first_explore_revealed": {pid: (d in setup_reveals) for pid, d in firsts.items()},
        "distinct_first_explores": len(set(firsts.values())),
        "players": {pid: {
            "gate_id": result["players"][pid]["gate_id"],
            "profile": state["policies"][pid],
            "won": winner == pid,
            "equipment": result["players"][pid]["equipment_final"],
            "attack_bonus_uses": result["players"][pid]["attack_bonus_uses"],
            "defense_bonus_uses": result["players"][pid]["defense_bonus_uses"],
            "pilum_uses": result["players"][pid]["pilum_uses"],
            "pugio_tiebreaks": result["players"][pid]["pugio_tiebreaks"],
            "galea_reveals": result["players"][pid]["galea_reveals"],
            "lorica_saves": result["players"][pid]["lorica_saves"],
            "set_completion_awards": result["players"][pid]["set_completion_awards"],
            "duels_initiated": result["players"][pid]["duels_initiated"],
            "claims_made": result["players"][pid]["claims_made"],
            "claims_cancelled": result["players"][pid]["claims_cancelled"],
            "claims_survived": result["players"][pid]["claims_survived"],
            "times_displaced": result["players"][pid]["times_displaced"],
            "equipment_count": len(result["players"][pid]["equipment_final"]),
            "prestige_earned": result["players"][pid]["prestige_earned"],
            "districts_explored": result["players"][pid]["districts_explored"],
        } for pid in IDS},
    }
    return row


def summarize(rows):
    games = len(rows)
    wins = sum(1 for r in rows if r["outcome"] == "win")
    gate = collections.Counter()
    gate_games = collections.Counter()
    strategy = collections.Counter()
    strategy_games = collections.Counter()
    first_reveal_walks = collections.Counter()
    first_reveal_total = 0
    explore_counts = collections.Counter()
    ability_games = {name: 0 for name in
                     ("attack", "defense", "pilum", "pugio", "galea", "lorica")}
    ability_total = {name: 0 for name in ability_games}
    item_hold = {item: {"wins": 0, "losses": 0} for item in ITEMS}
    seat_wins = seat_losses = 0
    rounds = sorted(r["total_rounds"] for r in rows)
    for row in rows:
        for pid, p in row["players"].items():
            gate_games[p["gate_id"]] += 1
            strategy_games[p["profile"]] += 1
            if p["won"]:
                gate[p["gate_id"]] += 1
                strategy[p["profile"]] += 1
                seat_wins += 1
            else:
                seat_losses += 1
            for item in p["equipment"]:
                bucket = item_hold[item]
                if p["won"]:
                    bucket["wins"] += 1
                else:
                    bucket["losses"] += 1
        if row["winner"]:
            pass
        for pid, flag in row["first_explore_revealed"].items():
            first_reveal_total += 1
            if flag:
                first_reveal_walks[pid] += 1
        explore_counts[row["distinct_first_explores"]] += 1
        for name, keys in (("attack", ("attack_bonus_uses",)), ("defense", ("defense_bonus_uses",)),
                           ("pilum", ("pilum_uses",)), ("pugio", ("pugio_tiebreaks",)),
                           ("galea", ("galea_reveals",)), ("lorica", ("lorica_saves",))):
            total = sum(sum(p[k] for k in keys) for p in row["players"].values())
            if total:
                ability_games[name] += 1
                ability_total[name] += total
    median = rounds[games // 2] if games else None
    return {
        "schema": "v09-design-experiment-1",
        "games": games, "wins": wins, "draws": games - wins,
        "median_rounds": median,
        "gate_rates": {g: {"games": gate_games[g], "wins": gate[g],
                           "rate": round(gate[g] / gate_games[g], 4) if gate_games[g] else None,
                           "wilson_95": wilson(gate[g], gate_games[g])}
                       for g in IDS},
        "strategy_rates": {s: {"games": strategy_games[s], "wins": strategy[s],
                               "rate": round(strategy[s] / strategy_games[s], 4) if strategy_games[s] else None,
                               "wilson_95": wilson(strategy[s], strategy_games[s])}
                           for s in PROFILES},
        "first_explore_to_start_reveal_share": (round(sum(first_reveal_walks.values()) / first_reveal_total, 4)
                                                if first_reveal_total else None),
        "distinct_first_explore_distribution": dict(sorted(explore_counts.items())),
        "ability_games": ability_games, "ability_total_uses": ability_total,
        "item_hold_rates": {item: {
            "winners": round(b["wins"] / seat_wins, 4) if seat_wins else None,
            "losers": round(b["losses"] / seat_losses, 4) if seat_losses else None}
            for item, b in item_hold.items()},
        "seat_wins": seat_wins, "seat_losses": seat_losses,
        "engine_version": succession.VERSION, "policy_version": succession.POLICY_VERSION,
    }


def run_arm(name, rules_file):
    with open(os.path.join(ROOT, rules_file), encoding="utf-8") as handle:
        base_rules = json.load(handle)
    out_dir = os.path.join(OUT_ROOT, name)
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for index in range(GAMES_PER_ARM):
        seed = SEED_BASE + index
        gate_order, assignment = schedule(index)
        rules = copy.deepcopy(base_rules)
        rules["succession"]["gate_assignment"] = "manual"
        rules["succession"]["gate_order"] = list(gate_order)
        state = play_game(rules, seed, f"{name}-{seed}", assignment)
        rows.append(game_row(state))
        if (index + 1) % 96 == 0:
            print(f"  {name}: {index + 1}/{GAMES_PER_ARM} games", flush=True)
    with open(os.path.join(out_dir, "games.jsonl"), "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    summary = summarize(rows)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return name, summary


def main():
    print(f"V0.9 design experiment: {GAMES_PER_ARM} games per arm, seed base {SEED_BASE}")
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_arm, name, rules_file) for name, rules_file in ARMS]
        results = {}
        for future in concurrent.futures.as_completed(futures):
            name, summary = future.result()
            results[name] = summary
    comparison = {name: results[name] for name, _ in ARMS}
    with open(os.path.join(OUT_ROOT, "comparison.json"), "w", encoding="utf-8") as handle:
        json.dump({"seed_base": SEED_BASE, "games_per_arm": GAMES_PER_ARM,
                   "arms": comparison}, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("wrote", os.path.join(OUT_ROOT, "comparison.json"))


if __name__ == "__main__":
    main()
