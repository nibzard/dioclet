#!/usr/bin/env python3
"""V0.9 hill-climb: greedy coordinate screens over the human redesign knobs.

Incumbent starts at E0 (rules_v09e_court.json). Each step changes exactly
one knob value, screens it against the incumbent on matched seeds (same
gate/policy schedule), applies the frozen promotion gates from
programme.md (draws, median rounds, winning profiles, claim health), and
promotes on pass. Confirmation runs 384 fresh games for the finalist
against V0.8.1 and C2.

Seeds: screens 700000+, holdout/confirmation 800000+ (nothing burned).
"""
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
OUT_ROOT = os.path.join(ROOT, "results", "v09-climb")
GAMES_PER_SCREEN = 96
CONFIRM_GAMES = 384
SCREEN_BASE = 700000
CONFIRM_BASE = 800000

# Frozen promotion gates (programme.md section 7 plus claim-health gates
# predeclared here before any measurement).
GATES = {
    "max_draw_increase": 0.02,       # absolute vs incumbent
    "max_median_round_increase": 4,  # absolute vs incumbent
    "min_winning_profiles": 2,
    "claims_per_game_range": (1.0, 15.0),   # no recycling loop, no dead claims
    "first_claimant_win_range": (0.20, 0.60),
    "min_window_or_contest_wins": 0.75,     # share of games decided by claim play
}


def schedule(index):
    gate_permutations = tuple(itertools.permutations(IDS))
    gate_order = gate_permutations[index % len(gate_permutations)]
    policy_rotation = (index // len(gate_permutations)) % len(IDS)
    assignment = {pid: PROFILES[(i + policy_rotation) % len(PROFILES)]
                  for i, pid in enumerate(IDS)}
    return gate_order, assignment


def play(rules, seed, game_id, assignment):
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
    return engine.result(state)


def metrics(rules, seed_base, games):
    results = []
    for index in range(games):
        gate_order, assignment = schedule(index)
        game_rules = copy.deepcopy(rules)
        game_rules["succession"]["gate_assignment"] = "manual"
        game_rules["succession"]["gate_order"] = list(gate_order)
        results.append(play(game_rules, seed_base + index, f"g{seed_base + index}", assignment))
    wins = sum(1 for r in results if r["outcome"] == "win")
    rounds = sorted(r["total_rounds"] for r in results)
    strategy_wins = {}
    strategy_games = {}
    claimant_wins = claimant_games = 0
    claims = 0.0
    decided_by_claim = 0
    for r in results:
        claims += sum(p["claims_made"] for p in r["players"].values())
        if r["end_reason"] in ("survived_window", "acclamation"):
            decided_by_claim += 1
        if r["first_challenger"]:
            claimant_games += 1
            claimant_wins += 1 if r["first_challenger_won"] else 0
        for pid, p in r["players"].items():
            profile = r["policies"][pid]
            strategy_games[profile] = strategy_games.get(profile, 0) + 1
            if r["winner"] == pid:
                strategy_wins[profile] = strategy_wins.get(profile, 0) + 1
    return {
        "games": games, "draws": games - wins, "draw_rate": round((games - wins) / games, 4),
        "median_rounds": rounds[games // 2],
        "strategy_rates": {p: round(strategy_wins.get(p, 0) / strategy_games[p], 4) for p in PROFILES},
        "claims_per_game": round(claims / games, 3),
        "first_claimant_win_rate": round(claimant_wins / claimant_games, 4) if claimant_games else None,
        "decided_by_claim_rate": round(decided_by_claim / games, 4),
    }


def check_gates(inc, cand):
    """Return (passed, reasons). cand must not violate any gate vs inc."""
    reasons = []
    if cand["draw_rate"] > inc["draw_rate"] + GATES["max_draw_increase"]:
        reasons.append(f"draw rate {cand['draw_rate']} > incumbent {inc['draw_rate']} + 0.02")
    if cand["median_rounds"] > inc["median_rounds"] + GATES["max_median_round_increase"]:
        reasons.append(f"median rounds {cand['median_rounds']} > incumbent {inc['median_rounds']} + 4")
    winners = [p for p, r in cand["strategy_rates"].items() if r >= 0.08]
    if len(winners) < GATES["min_winning_profiles"]:
        reasons.append(f"only {len(winners)} profiles can win")
    lo, hi = GATES["claims_per_game_range"]
    if not lo <= cand["claims_per_game"] <= hi:
        reasons.append(f"claims/game {cand['claims_per_game']} outside [{lo}, {hi}]")
    if cand["first_claimant_win_rate"] is not None:
        lo, hi = GATES["first_claimant_win_range"]
        if not lo <= cand["first_claimant_win_rate"] <= hi:
            reasons.append(f"first-claimant win {cand['first_claimant_win_rate']} outside [{lo}, {hi}]")
    if cand["decided_by_claim_rate"] < GATES["min_window_or_contest_wins"]:
        reasons.append(f"only {cand['decided_by_claim_rate']} of games decided by claim play")
    return (not reasons), reasons


def run_arm(name, rules, seed_base, games):
    m = metrics(rules, seed_base, games)
    m["arm"] = name
    print(json.dumps(m), flush=True)
    return name, m


# One knob per step: (label, json mutation applied to a deep copy)
# radius values >= duel_range (2) never bind: duel legality already requires
# standing within duel_range of the target. radius1 is the only binding arm.
LADDER = [
    ("window1", {"succession": {"claim_window_rounds": 1}}),
    ("window3", {"succession": {"claim_window_rounds": 3}}),
    ("radius1", {"succession": {"challenge_radius": 1}}),
    ("losercost1", {"succession": {"duel_loser_cost": 1}}),
    ("proclaimcost1", {"succession": {"proclaim_cost": 1}}),
    ("noblind", {"succession": {"blind_support": False}}),
]


def apply_knob(base, patch):
    rules = copy.deepcopy(base)
    for section, values in patch.items():
        if section in rules and isinstance(rules[section], dict):
            rules[section].update(values)
        else:
            rules[section] = values
    return rules


def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    incumbent_rules = engine.load_rules(os.path.join(ROOT, "rules_v09e_court.json"))
    cycle = 0
    log = []
    while cycle < 3:
        cycle += 1
        print(f"=== cycle {cycle}: screening incumbent + {len(LADDER)} candidates on "
              f"{GAMES_PER_SCREEN} matched seeds", flush=True)
        arms = {"incumbent": incumbent_rules}
        for label, patch in LADDER:
            candidate = apply_knob(incumbent_rules, patch)
            engine.validate_rules(candidate)
            arms[label] = candidate
        with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(run_arm, label, rules, SCREEN_BASE, GAMES_PER_SCREEN)
                       for label, rules in arms.items()]
            results = {}
            for future in concurrent.futures.as_completed(futures):
                label, m = future.result()
                results[label] = m
        inc = results["incumbent"]
        best_label, best_m, best_reasons = None, None, None
        for label, m in results.items():
            if label == "incumbent":
                continue
            passed, reasons = check_gates(inc, m)
            print(f"  {label}: {'PASS' if passed else 'FAIL'} {'; '.join(reasons)}", flush=True)
            log.append({"cycle": cycle, "candidate": label, "metrics": m,
                        "passed": passed, "reasons": reasons})
            if passed:
                draw_gain = inc["draw_rate"] - m["draw_rate"]
                rounds_gain = inc["median_rounds"] - m["median_rounds"]
                score = draw_gain * 100 + rounds_gain * 0.5 + (m["decided_by_claim_rate"] - inc["decided_by_claim_rate"])
                if best_m is None or score > best_m.get("_score", -1e9):
                    m["_score"] = score
                    best_label, best_m = label, m
        if best_label is None:
            print(f"=== cycle {cycle}: no candidate passed; keeping incumbent", flush=True)
            break
        print(f"=== cycle {cycle}: promoting {best_label}", flush=True)
        incumbent_rules = apply_knob(incumbent_rules, dict(LADDER_DICT[best_label]))
        log.append({"cycle": cycle, "promoted": best_label})
    # Confirmation: finalist vs V0.8.1 and C2 on fresh seeds.
    finals = {
        "finalist": incumbent_rules,
        "v081": engine.load_rules(os.path.join(ROOT, "rules_v08_succession.json")),
        "c2": engine.load_rules(os.path.join(ROOT, "rules_v09_abilities.json")),
    }
    print(f"=== confirmation: {CONFIRM_GAMES} fresh games per arm", flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_arm, label, rules, CONFIRM_BASE, CONFIRM_GAMES)
                   for label, rules in finals.items()]
        confirmation = {}
        for future in concurrent.futures.as_completed(futures):
            label, m = future.result()
            confirmation[label] = m
    payload = {"gates": GATES, "log": log, "confirmation": confirmation,
               "final_rules": incumbent_rules, "seed_bases": {"screen": SCREEN_BASE, "confirm": CONFIRM_BASE}}
    with open(os.path.join(OUT_ROOT, "hillclimb.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("wrote", os.path.join(OUT_ROOT, "hillclimb.json"), flush=True)


LADDER_DICT = dict(LADDER)

if __name__ == "__main__":
    main()
