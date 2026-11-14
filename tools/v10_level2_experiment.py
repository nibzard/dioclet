#!/usr/bin/env python3
"""V0.10 level 2 experiment: succession map size and faction cards.

Questions (2026-11-14 design review):
- Is the 13x9 succession map too small, so level 2 ends too quickly?
  Would a palace-size map (one board, flipped) play longer and fairer?
- Are the fixed faction meeting places fair across gates, and do
  faction cards (three factions and three blanks dealt face down onto
  six sites, as treasures are on level 1) even them out?

Arms (every other rule is 0.9.4):
  v094        rules_v094_twinboard.json - 13x9, public factions
  big_public  rules_v10_big_public.json - 19x13 four blocks, public
  big_blind   rules_v10_big_blind.json  - 19x13 four blocks, cards
  flip_blind  rules_v10_flip_blind.json - palace grid itself, cards
  small_pin_public / big_pin_public / big_pin_blind / small_pin_blind - "pinwheel"
              gates: every gate the same street distance from the
              Peristyle (6 small, 9 big); sites chosen by geometry so
              every gate sees the same distances to them.

Same driver, seat schedule, and policy profiles as the 0.9.4
confirmation (tools/v09_geometry_sweep.py); fresh seeds 1030000+.
Holdout for the finalists (D51):
  --seed-base 1040000 --arms v094,small_pin_blind,big_pin_blind
  --out results/v10-level2/holdout.json
Bot profiles only - these numbers say nothing about human fun.
"""
import argparse
import concurrent.futures
import copy
import json
import math
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import engine  # noqa: E402
import policies  # noqa: E402
from v09_geometry_sweep import wilson  # noqa: E402
from v09_hillclimb import schedule  # noqa: E402

ARMS = {
    "v094": "rules_v094_twinboard.json",
    "big_public": "rules_v10_big_public.json",
    "big_blind": "rules_v10_big_blind.json",
    "flip_blind": "rules_v10_flip_blind.json",
    "small_pin_public": "rules_v10_small_pin_public.json",
    "big_pin_public": "rules_v10_big_pin_public.json",
    "big_pin_blind": "rules_v10_big_pin_blind.json",
    "small_pin_blind": "rules_v10_small_pin_blind.json",
}
SEED_BASE = 1030000
QUICK_L2_ROUNDS = 4          # "won level 2 too quickly": at most this many rounds


def play_one(args):
    rules_file, index, seed_base = args
    rules = engine.load_rules(os.path.join(ROOT, rules_file))
    gate_order, assignment = schedule(index)
    rules = copy.deepcopy(rules)
    rules["succession"]["gate_assignment"] = "manual"
    rules["succession"]["gate_order"] = list(gate_order)
    seed = seed_base + index
    state = engine.new_game(rules, seed, f"g{seed}", assignment)
    rng = random.Random(f"probe:{seed}")
    cap = 4 * (rules["level1"]["max_rounds"] + rules["level2"]["max_rounds"] + 3)
    for _ in range(cap):
        if engine.is_finished(state):
            break
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act(assignment[state["active_player"]], obs, rng)
        engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
    if not engine.is_finished(state):
        raise RuntimeError(f"g{seed} exceeded its turn bound")
    engine.check_invariants(state)
    result = engine.result(state)
    gate_of = {pid: p["gate_id"] for pid, p in result["players"].items()}
    # Phase-2 support timing, per gate: the round of the first and the
    # second support, or None if never reached.
    support_rounds = {pid: [] for pid in gate_of}
    searches = 0
    for record in state["events"]:
        if record.get("phase") != 2:
            continue
        for e in record["events"]:
            if e.get("type") == "support_gained":
                support_rounds[e["player"]].append(record["round"])
            elif e.get("type") == "support_site_revealed":
                searches += 1
    return {
        "winner_gate": gate_of.get(result["winner"]) if result["winner"] else None,
        "end_reason": result["end_reason"],
        "rounds_level1": result["rounds_level1"],
        "rounds_level2": result["rounds_level2"],
        "total_rounds": result["total_rounds"],
        "claims": sum(p["claims_made"] for p in result["players"].values()),
        "first_challenger": result["first_challenger"],
        "first_challenger_won": result["first_challenger_won"],
        "winner_profile": result["policies"].get(result["winner"]) if result["winner"] else None,
        "support_rounds_by_gate": {gate_of[pid]: r for pid, r in support_rounds.items()},
        "searches": searches,
    }


def chi2_sf_df3(x):
    """Upper tail of chi-square with 3 degrees of freedom."""
    return math.erfc(math.sqrt(x / 2)) + math.sqrt(2 * x / math.pi) * math.exp(-x / 2)


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def summarize(name, games):
    n = len(games)
    l2 = [g["rounds_level2"] for g in games if g["rounds_level2"] is not None]
    wins = [g for g in games if g["winner_gate"]]
    gate_wins = {gid: sum(1 for g in wins if g["winner_gate"] == gid) for gid in ("P0", "P1", "P2", "P3")}
    expected = len(wins) / 4
    chi2 = sum((w - expected) ** 2 / expected for w in gate_wins.values()) if expected else 0.0
    support = {}
    for gid in ("P0", "P1", "P2", "P3"):
        firsts = [g["support_rounds_by_gate"][gid][0] for g in games if g["support_rounds_by_gate"].get(gid)]
        seconds = [g["support_rounds_by_gate"][gid][1] for g in games
                   if len(g["support_rounds_by_gate"].get(gid, [])) > 1]
        support[gid] = {
            "first_support_mean_round": round(statistics.mean(firsts), 2) if firsts else None,
            "second_support_mean_round": round(statistics.mean(seconds), 2) if seconds else None,
            "reached_two_supports": round(len(seconds) / n, 3),
        }
    profiles = {}
    for g in wins:
        profiles[g["winner_profile"]] = profiles.get(g["winner_profile"], 0) + 1
    claimant = [g for g in games if g["first_challenger"]]
    return {
        "arm": name, "games": n,
        "draw_rate": round(sum(1 for g in games if not g["winner_gate"]) / n, 4),
        "median_rounds": pct([g["total_rounds"] for g in games], 0.5),
        "median_rounds_level1": pct([g["rounds_level1"] for g in games if g["rounds_level1"]], 0.5),
        "level2_rounds": {"p10": pct(l2, 0.1), "p25": pct(l2, 0.25), "median": pct(l2, 0.5),
                          "p75": pct(l2, 0.75), "p90": pct(l2, 0.9), "mean": round(statistics.mean(l2), 2)},
        "quick_level2_share": round(sum(1 for r in l2 if r <= QUICK_L2_ROUNDS) / len(l2), 4),
        "gate_win_rates": {gid: wilson(w, n) for gid, w in gate_wins.items()},
        "gate_uniformity_p": round(chi2_sf_df3(chi2), 4),
        "gate_spread": round((max(gate_wins.values()) - min(gate_wins.values())) / n, 4),
        "support_by_gate": support,
        "claims_per_game": round(statistics.mean(g["claims"] for g in games), 3),
        "first_claimant_win_rate": round(sum(1 for g in claimant if g["first_challenger_won"]) / len(claimant), 4)
        if claimant else None,
        "searches_per_game": round(statistics.mean(g["searches"] for g in games), 2),
        "winning_profiles": {k: round(v / n, 4) for k, v in sorted(profiles.items())},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=384)
    ap.add_argument("--seed-base", type=int, default=SEED_BASE)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "v10-level2", "confirm.json"))
    args = ap.parse_args()
    arms = args.arms.split(",")
    summary = {"seed_base": args.seed_base, "games": args.games, "arms": {}}
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for name in arms:
            jobs = [(ARMS[name], i, args.seed_base) for i in range(args.games)]
            games = list(pool.map(play_one, jobs, chunksize=8))
            summary["arms"][name] = summarize(name, games)
            print(json.dumps(summary["arms"][name]), flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
