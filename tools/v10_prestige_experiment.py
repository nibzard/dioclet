#!/usr/bin/env python3
"""V0.10 Prestige experiment: guard posts on the succession map.

Question (2026-11-14): in the four-seat Haiku game and in human session
001, every rival held 0 Prestige when a claim was proclaimed, so nobody
could pay the contest fee. Does a Prestige source on the succession map
fix this without the draw explosion that cheaper or longer contests
cause (screen: free contests 39% draws, no duel-loser cost 19%,
three-round window 30%)?

Arms (every other rule is 0.10.0-bigboard):
  base    rules_v010_bigboard.json
  posts   rules_v10_l2posts.json - four guard posts on the succession map
          at (0,3), (18,9), (3,0), (15,12): half-turn symmetric, every
          gate sees them at 3, 9, 21, 21 steps, each 12 from the Peristyle.

Players:
  probes  the four frozen probe profiles (D24), as in D51.
  spender the same profiles, wrapped: while a rival's claim stands, a
          seat that still needs support buys it whenever it can instead
          of saving the contest fee. This copies the mistake the Haiku
          seats made (P0 earned 1 Prestige in the window and spent it
          on support). The frozen policies are not changed.

Extra measures, recorded at the moment each phase-2 claim is proclaimed:
the share of claims that no rival can afford to contest, and the mean
number of rivals who can. Also the share of phase-2 turns taken at 0
Prestige. Bot profiles only - these numbers say nothing about human fun.
"""
import argparse
import concurrent.futures
import json
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import engine  # noqa: E402
import policies  # noqa: E402
from v09_hillclimb import schedule  # noqa: E402
from v10_level2_experiment import summarize  # noqa: E402

ARMS = {"base": "rules_v010_bigboard.json", "posts": "rules_v10_l2posts.json"}
PLAYERS = ("probes", "spender")
SEED_BASE = 1060000


def spender_act(profile, obs, rng):
    """The probe profile, except it spends on support during a rival's claim."""
    pending = obs.get("pending_claim")
    me = obs["players"][obs["viewer"]]
    needs = len(me["support"]) < obs["progress"]["required_support"]
    if obs["phase"] == 2 and pending and pending["player"] != obs["viewer"] and needs:
        buys = [a for a in obs["legal_actions"] if a["kind"] == "gain_support"]
        if buys:
            return buys[0]["action_id"], "spender: buy support during a rival's claim"
    return policies.act(profile, obs, rng)


def play_one(args):
    arm, players, index, seed_base = args
    rules = engine.load_rules(os.path.join(ROOT, ARMS[arm]))
    gate_order, assignment = schedule(index)
    rules["succession"]["gate_assignment"] = "manual"
    rules["succession"]["gate_order"] = list(gate_order)
    seed = seed_base + index
    state = engine.new_game(rules, seed, f"g{seed}", assignment)
    rng = random.Random(f"probe:{seed}")
    fee = max(1, rules["succession"].get("contest_cost", 0))
    able, last_claim, broke, turns2 = [], None, 0, 0
    for _ in range(4 * (rules["level1"]["max_rounds"] + rules["level2"]["max_rounds"] + 3)):
        if engine.is_finished(state):
            break
        pid = state["active_player"]
        if state["phase"] == 2:
            turns2 += 1
            broke += state["players"][pid]["prestige"] == 0
        obs = engine.observe(state, pid)
        if players == "spender":
            action_id, reason = spender_act(assignment[pid], obs, rng)
        else:
            action_id, reason = policies.act(assignment[pid], obs, rng)
        engine.apply_action(state, pid, obs["turn_id"], action_id, reason)
        claim = state.get("pending_claim")
        if state["phase"] == 2 and claim and claim.get("claim_id") != last_claim:
            last_claim = claim.get("claim_id")
            able.append(sum(1 for q, p in state["players"].items()
                            if q != claim["player"] and p["prestige"] >= fee))
    if not engine.is_finished(state):
        raise RuntimeError(f"g{seed} exceeded its turn bound")
    engine.check_invariants(state)
    result = engine.result(state)
    gate_of = {p: v["gate_id"] for p, v in result["players"].items()}
    support_rounds, searches = {p: [] for p in gate_of}, 0
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
        "support_rounds_by_gate": {gate_of[p]: r for p, r in support_rounds.items()},
        "searches": searches,
        "claim_able": able, "broke_turns": broke, "phase2_turns": turns2,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=1536)
    ap.add_argument("--seed-base", type=int, default=SEED_BASE)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "v10-prestige", "holdout.json"))
    args = ap.parse_args()
    summary = {"seed_base": args.seed_base, "games": args.games, "arms": {}}
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for players in PLAYERS:
            for arm in ARMS:
                jobs = [(arm, players, i, args.seed_base) for i in range(args.games)]
                games = list(pool.map(play_one, jobs, chunksize=8))
                s = summarize(f"{arm}/{players}", games)
                able = [a for g in games for a in g["claim_able"]]
                s["claims_seen"] = len(able)
                s["claims_no_rival_can_contest"] = round(sum(a == 0 for a in able) / len(able), 4)
                s["mean_rivals_able_to_contest"] = round(statistics.mean(able), 3)
                s["phase2_turns_at_zero_prestige"] = round(
                    sum(g["broke_turns"] for g in games) / sum(g["phase2_turns"] for g in games), 4)
                summary["arms"][f"{arm}/{players}"] = s
                print(json.dumps(s), flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
