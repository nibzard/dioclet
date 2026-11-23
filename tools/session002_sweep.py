#!/usr/bin/env python3
"""Matched-seed simulation sweep for human-session-002 mechanical candidates.

Tests candidate fixes against the post-D56 V0.10.2 baseline without mutating
engine.py or rules/imperial-rivals-v0.10.2.json:
  - pilum_plus2:          Javelin gives +2 attacking the standing claimant
  - guard_roll_3plus:     Guard posts pay on 3+ instead of 4+
  - fee1_window1:         1-round claim window, contest fee 1
  - fee0_window1:         1-round claim window, contest fee 0 (joint sweep)
  - transition_stipend_1: Players entering Level 2 with 0 Prestige receive +1
  - proclaim_floor_1:     On proclamation, rivals with 0 Prestige receive +1
  - pilum2_floor1:        pilum_plus2 + proclaim_floor_1 combined
  - galea_l2_public:      Unused Helmet can publicly reveal 1 faction card in L2
  - table_misplay:        Reproduces Session-002 misplays (loser->winner coin
                          transfer + guard post 5+) to quantify their impact

Also measures Lorica (Armor) Peristyle pile-up (immediate re-claim after a
Lorica save), Pilum strict-advantage rate, zero-Prestige lockout rate, and a
spender-stress pass where rivals spend Prestige on support during a claim.

Usage:
  python3 tools/session002_sweep.py [--games 384] [--seed-base 1200000]
"""

import argparse
import copy
import json
import math
import os
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import engine  # noqa: E402
import policies  # noqa: E402
import report  # noqa: E402

RULES_PATH = ROOT / "rules" / "imperial-rivals-v0.10.2.json"
SEATS = ("P0", "P1", "P2", "P3")


def chi2_p_df3(counts):
    """Exact survival function for chi-square with df=3 (4 uniform gates)."""
    total = sum(counts)
    if total == 0:
        return 1.0
    exp = total / 4.0
    x = sum((c - exp) ** 2 / exp for c in counts)
    # For df=3: P(X >= x) = erfc(sqrt(x/2)) + sqrt(2*x/pi)*exp(-x/2)
    return round(math.erfc(math.sqrt(x / 2.0))
                 + math.sqrt(2.0 * x / math.pi) * math.exp(-x / 2.0), 4)


def _spender_choose(policy_name, obs, prng):
    """Copy of the spender stress seat: buys support even during a rival claim."""
    pending = obs.get("pending_claim")
    if pending and pending["player"] != obs["active_player"]:
        support_actions = [a for a in obs["legal_actions"] if a["kind"] == "gain_support"]
        if support_actions:
            return support_actions[0]["action_id"], "spender buys support during claim"
    return policies.act(policy_name, obs, prng)


def _apply_l2_galea(state, player):
    """Publicly reveal one unrevealed faction card using an unused Helmet."""
    me = state["players"][player]
    hidden = [k for k in sorted(state["faction_sites"])
              if k not in state["faction_sites_revealed"]]
    if not hidden:
        return False
    # Choose the hidden card space closest to the player's current position.
    px, py = me["pos"]
    key = min(hidden, key=lambda k: abs(int(k.split(",")[0]) - px)
              + abs(int(k.split(",")[1]) - py))
    faction = state["faction_sites"][key]
    state["faction_sites_revealed"][key] = faction
    me["abilities_used"]["reveal_district"] = "galea"
    me["stats"]["galea_reveals"] += 1
    # Advance turn index / round using engine's exact step convention.
    state["turn_index"] += 1
    if state["turn_index"] >= len(state["turn_order"]):
        state["turn_index"] = 0
        state["round"] += 1
        if state["rotate_first"]:
            state["round_start"] = (state["round_start"] + 1) % len(state["turn_order"])
        # Check claim window expiry and succession timeout at end of round.
        cfg = state["rules"]["succession"]
        pending = state["pending_claim"]
        if pending and cfg["claim_window_rounds"] and (
                state["round"] - pending["round"] > cfg["claim_window_rounds"]):
            claimant = pending["player"]
            state["winner"] = claimant
            state["status"] = "finished"
            state["end_reason"] = "survived_window"
            state["players"][claimant]["stats"]["claims_survived"] += 1
        elif state["round"] > cfg["max_rounds"]:
            state["status"] = "finished"
            state["end_reason"] = "succession_timeout"
            state["succession_timeout"] = True
    if state["status"] == "in_progress":
        engine._start_turn(state)
    return True


def play_arm_game(base_rules, arm, seed, game_id, policies_map, spender=False):
    rules = copy.deepcopy(base_rules)
    if arm in ("pilum_plus2", "pilum2_floor1", "pilum2_window1"):
        rules["treasures"]["abilities"]["pilum"]["value"] = 2
    if arm in ("fee1_window1", "pilum2_window1"):
        rules["succession"]["claim_window_rounds"] = 1
    elif arm == "guard_roll_3plus":
        rules["prestige"]["guard_post_min_roll"] = 3
    elif arm == "fee0_window1":
        rules["succession"]["claim_window_rounds"] = 1
        rules["succession"]["contest_fee"] = 0
    elif arm == "table_misplay":
        rules["prestige"]["guard_post_min_roll"] = 5

    state = engine.new_game(rules, seed, game_id, policies_map)
    prng = random.Random(f"policy:{game_id}:{seed}")
    guard = 0
    max_turns = 4 * (rules["palace"]["max_rounds"]
                     + rules["palace"]["rounds_after_checkpoint"]
                     + rules["succession"]["max_rounds"]) + 16

    # Session-002 telemetry counters.
    l2_turns = 0
    l2_zero_prestige_turns = 0
    claims_proclaimed = 0
    claims_no_rival_can_contest = 0
    contests_total = 0
    pilum_strict_advantage = 0
    lorica_saves = 0
    lorica_reclaims = 0
    lorica_pending_reclaim = {}  # pid -> True if saved on last beaten claim
    galea_l2_uses = 0

    prev_phase = 1
    while not engine.is_finished(state):
        guard += 1
        if guard > max_turns:
            raise RuntimeError(f"{arm} {game_id} exceeded turn limit")

        pid = state["active_player"]
        me = state["players"][pid]

        if state["phase"] == 2:
            l2_turns += 1
            if me["prestige"] == 0:
                l2_zero_prestige_turns += 1

        # Optional L2 Galea arm: if holding unused galea in L2, still need a
        # faction not currently revealed, and no rival claim needs urgent contest.
        if (arm == "galea_l2_public" and state["phase"] == 2
                and "galea" in me["equipment"]
                and "reveal_district" not in me["abilities_used"]
                and len(me["support"]) < rules["succession"]["factions_to_proclaim"]
                and not state["pending_claim"]):
            known_needed = [f for f in state["faction_sites_revealed"].values()
                            if f and f not in me["support"]]
            hidden = [k for k in state["faction_sites"]
                      if k not in state["faction_sites_revealed"]]
            if not known_needed and hidden:
                _apply_l2_galea(state, pid)
                galea_l2_uses += 1
                continue

        obs = engine.observe(state, pid)
        if spender:
            action_id, reason = _spender_choose(policies_map[pid], obs, prng)
        else:
            action_id, reason = policies.act(policies_map[pid], obs, prng)

        # In galea_l2_public, hold galea in Palace so we measure its L2 impact.
        if arm == "galea_l2_public" and state["phase"] == 1:
            chosen = next(a for a in obs["legal_actions"] if a["action_id"] == action_id)
            if chosen["kind"] == "inspect":
                non_inspect = [a for a in obs["legal_actions"] if a["kind"] != "inspect"]
                if non_inspect:
                    alt_obs = dict(obs)
                    alt_obs["legal_actions"] = non_inspect
                    action_id, reason = policies.act(policies_map[pid], alt_obs, prng)

        pre_pending = copy.deepcopy(state["pending_claim"])
        pre_prestige = {p: state["players"][p]["prestige"] for p in SEATS}
        chosen_action = next(a for a in obs["legal_actions"] if a["action_id"] == action_id)

        # Track immediate re-claim after a Lorica save.
        if lorica_pending_reclaim.get(pid):
            if chosen_action["kind"] == "proclaim":
                lorica_reclaims += 1
            lorica_pending_reclaim[pid] = False

        # Track whether Pilum strictly increased attacker bonus on a contest.
        if (chosen_action["kind"] == "duel" and pre_pending
                and pre_pending["player"] == chosen_action["target"]):
            contests_total += 1
            abil = rules["treasures"]["abilities"]
            has_gladius = "gladius" in me["equipment"]
            has_pilum = "pilum" in me["equipment"]
            g_val = abil["gladius"]["value"] if has_gladius else 0
            p_val = abil["pilum"]["value"] if has_pilum else 0
            if p_val > g_val:
                pilum_strict_advantage += 1

        rec = engine.apply_action(state, pid, obs["turn_id"], action_id, reason)

        # Table-misplay arm: undo bank-funded duel reward when loser had 0 coins
        # (direct loser->winner transfer instead of bank-in/bank-out).
        if arm == "table_misplay":
            for ev in rec["events"]:
                if ev["type"] == "duel":
                    winner = ev["winner"]
                    loser = ev["defender"] if winner == ev["attacker"] else ev["attacker"]
                    loser_before = pre_prestige[loser]
                    # If contest duel, challenger already spent 1 fee before duel roll.
                    if loser == pid and chosen_action.get("contest_cost"):
                        loser_before = max(0, loser_before - chosen_action["contest_cost"])
                    if loser_before == 0 and state["players"][winner]["prestige"] > 0:
                        state["players"][winner]["prestige"] -= 1

        # Track Lorica saves and claims proclaimed.
        for ev in rec["events"]:
            if ev["type"] == "ability_used" and ev["ability"] == "lorica_segmentata":
                lorica_saves += 1
                lorica_pending_reclaim[ev["player"]] = True
            elif ev["type"] == "claim_proclaimed":
                claims_proclaimed += 1
                claimant = ev["player"]
                if arm in ("proclaim_floor_1", "pilum2_floor1"):
                    for other in SEATS:
                        if other != claimant and state["players"][other]["prestige"] == 0:
                            state["players"][other]["prestige"] = 1
                fee = rules["succession"]["contest_fee"]
                able = sum(1 for other in SEATS
                           if other != claimant and state["players"][other]["prestige"] >= fee)
                if able == 0:
                    claims_no_rival_can_contest += 1

        # Transition stipend arm: anyone entering Level 2 with 0 Prestige gets 1.
        if prev_phase == 1 and state["phase"] == 2:
            if arm == "transition_stipend_1":
                for p in SEATS:
                    if state["players"][p]["prestige"] == 0:
                        state["players"][p]["prestige"] = 1
        prev_phase = state["phase"]

    res = engine.result(state)
    return {
        "res": res,
        "l2_turns": l2_turns,
        "l2_zero_prestige_turns": l2_zero_prestige_turns,
        "claims_proclaimed": claims_proclaimed,
        "claims_no_rival_can_contest": claims_no_rival_can_contest,
        "contests_total": contests_total,
        "pilum_strict_advantage": pilum_strict_advantage,
        "lorica_saves": lorica_saves,
        "lorica_reclaims": lorica_reclaims,
        "galea_l2_uses": galea_l2_uses,
    }


def run_arm(base_rules, arm, games, seed_base, spender=False):
    wins = 0
    draws = 0
    gates = {p: 0 for p in SEATS}
    l2_rounds = []
    tot_rounds = []
    fc_wins = 0
    fc_games = 0
    comebacks = 0
    claims = 0
    no_contest = 0
    l2_turns = 0
    l2_zero = 0
    contests = 0
    pilum_adv = 0
    lorica_saves = 0
    lorica_reclaims = 0
    galea_l2 = 0
    galea_l1 = 0

    for i in range(games):
        seed = seed_base + i
        pols = report.schedule_for(i, games)
        out = play_arm_game(base_rules, arm, seed, f"{arm}-{i}", pols, spender=spender)
        res = out["res"]
        if res["outcome"] == "win":
            wins += 1
            gates[res["winner"]] += 1
        else:
            draws += 1
        l2_rounds.append(res["rounds_succession"])
        tot_rounds.append(res["total_rounds"])
        if res["first_challenger"]:
            fc_games += 1
            if res["first_challenger_won"]:
                fc_wins += 1
        if res["comeback_win"]:
            comebacks += 1
        claims += out["claims_proclaimed"]
        no_contest += out["claims_no_rival_can_contest"]
        l2_turns += out["l2_turns"]
        l2_zero += out["l2_zero_prestige_turns"]
        contests += out["contests_total"]
        pilum_adv += out["pilum_strict_advantage"]
        lorica_saves += out["lorica_saves"]
        lorica_reclaims += out["lorica_reclaims"]
        galea_l2 += out["galea_l2_uses"]
        galea_l1 += sum(res["players"][p]["galea_reveals"] for p in SEATS) - out["galea_l2_uses"]

    l2_sorted = sorted(l2_rounds)
    return {
        "arm": arm,
        "spender": spender,
        "games": games,
        "draw_pct": round(100.0 * draws / games, 2),
        "l2_p10": report._pct(l2_sorted, 0.10),
        "l2_med": round(statistics.median(l2_sorted), 1),
        "l2_p90": report._pct(l2_sorted, 0.90),
        "total_med": round(statistics.median(tot_rounds), 1),
        "gate_rates": {p: round(gates[p] / games, 3) for p in SEATS},
        "gate_p": chi2_p_df3([gates[p] for p in SEATS]),
        "claims_per_game": round(claims / games, 2),
        "no_rival_contest_pct": round(100.0 * no_contest / claims, 2) if claims else 0.0,
        "l2_zero_prestige_pct": round(100.0 * l2_zero / l2_turns, 1) if l2_turns else 0.0,
        "fc_win_pct": round(100.0 * fc_wins / fc_games, 1) if fc_games else 0.0,
        "comeback_pct": round(100.0 * comebacks / wins, 1) if wins else 0.0,
        "contests_per_game": round(contests / games, 2),
        "pilum_adv_pct": round(100.0 * pilum_adv / contests, 1) if contests else 0.0,
        "lorica_saves_per_game": round(lorica_saves / games, 2),
        "lorica_reclaim_pct": round(100.0 * lorica_reclaims / lorica_saves, 1) if lorica_saves else 0.0,
        "galea_l1_per_game": round(galea_l1 / games, 2),
        "galea_l2_per_game": round(galea_l2 / games, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=384)
    ap.add_argument("--spender-games", type=int, default=192)
    ap.add_argument("--seed-base", type=int, default=1200000)
    ap.add_argument("--out", default=str(ROOT / "results" / "session002-sweep.json"))
    args = ap.parse_args()

    base_rules = engine.load_rules(str(RULES_PATH))
    arms = [
        "baseline",
        "pilum_plus2",
        "galea_l2_public",
        "guard_roll_3plus",
        "transition_stipend_1",
        "proclaim_floor_1",
        "pilum2_floor1",
        "fee1_window1",
        "pilum2_window1",
        "fee0_window1",
        "table_misplay",
    ]

    results = {"meta": {"games": args.games, "spender_games": args.spender_games,
                        "seed_base": args.seed_base, "rules": str(RULES_PATH.name)},
               "standard": [], "spender": []}

    print(f"Running {len(arms)} arms x {args.games} games (seed {args.seed_base}+)...")
    for arm in arms:
        row = run_arm(base_rules, arm, args.games, args.seed_base, spender=False)
        results["standard"].append(row)
        print(f"  {arm:22s} draws={row['draw_pct']:5.1f}% L2={row['l2_p10']:.0f}/{row['l2_med']:.0f}/{row['l2_p90']:.0f} "
              f"claims={row['claims_per_game']:4.2f} no-contest={row['no_rival_contest_pct']:4.1f}% "
              f"0P={row['l2_zero_prestige_pct']:4.1f}% gate_p={row['gate_p']:.2f} "
              f"pilum_adv={row['pilum_adv_pct']:4.1f}% lorica_reclaim={row['lorica_reclaim_pct']:4.1f}%")

    spender_arms = ["baseline", "guard_roll_3plus", "transition_stipend_1",
                    "proclaim_floor_1", "pilum2_floor1", "table_misplay"]
    print(f"\nRunning spender stress ({len(spender_arms)} arms x {args.spender_games} games)...")
    for arm in spender_arms:
        row = run_arm(base_rules, arm, args.spender_games, args.seed_base + 50000, spender=True)
        results["spender"].append(row)
        print(f"  {arm:22s} draws={row['draw_pct']:5.1f}% L2={row['l2_p10']:.0f}/{row['l2_med']:.0f}/{row['l2_p90']:.0f} "
              f"claims={row['claims_per_game']:4.2f} no-contest={row['no_rival_contest_pct']:4.1f}% "
              f"0P={row['l2_zero_prestige_pct']:4.1f}% gate_p={row['gate_p']:.2f}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
