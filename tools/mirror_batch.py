#!/usr/bin/env python3
"""Run mirror batches with policies that need rules (e.g. tactical).

Batch runner support (V0.6.1): runs N games with one policy in all
four seats, fixed seeds, and writes a compact fairness summary:
win rates by gate and by turn position, durations, draws.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine
import tactical_policy


def wilson(w, n):
    if not n:
        return {"lo": None, "hi": None}
    z = 1.96
    p = w / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return {"lo": round(c - h, 4), "hi": round(c + h, 4)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--policy", default="tactical")
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import random
    rules = engine.load_rules(args.rules)
    gate_wins = {p: 0 for p in ("P0", "P1", "P2", "P3")}
    pos_wins = {i: 0 for i in range(1, 5)}
    rounds = []
    draws = 0
    for i in range(args.games):
        seed = args.seed_base + i
        pols = {p: args.policy for p in ("P0", "P1", "P2", "P3")}
        state = engine.new_game(rules, seed, f"m{i+1:04d}", pols)
        prng = random.Random(f"policy:{state['game_id']}:{seed}")
        guard = 0
        while not engine.is_finished(state):
            guard += 1
            if guard > 4000:
                break
            ap_player = state["active_player"]
            obs = engine.observe(state, ap_player)
            aid, reason = tactical_policy.choose(obs, rules)
            engine.apply_action(state, ap_player, obs["turn_id"], aid, reason)
        res = engine.result(state)
        if res["outcome"] == "draw":
            draws += 1
        else:
            gate_wins[res["winner"]] += 1
            order = res["turn_order"]
            pos_wins[order.index(res["winner"]) + 1] += 1
        rounds.append(res["total_rounds"])
    rounds.sort()
    n_win = args.games - draws
    summary = {
        "policy": args.policy,
        "games": args.games,
        "draws": draws,
        "win_rate_by_gate": {
            g: {"wins": w, "rate": round(w / args.games, 4),
                "ci95": wilson(w, args.games)}
            for g, w in gate_wins.items()},
        "win_rate_by_turn_position": {
            i: {"wins": w, "rate": round(w / max(n_win, 1), 4),
                "ci95": wilson(w, args.games)}
            for i, w in pos_wins.items()},
        "durations": {
            "rounds_median": rounds[len(rounds) // 2],
            "rounds_p90": rounds[int(0.9 * (len(rounds) - 1))],
            "rounds_max": rounds[-1] if rounds else None},
        "policy_version": tactical_policy.TACTICAL_VERSION,
    }
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    print(json.dumps(summary["win_rate_by_gate"], indent=0))


if __name__ == "__main__":
    main()
