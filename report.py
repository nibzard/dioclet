"""Batch runner, per-game CSV rows, and aggregate reports (SPEC §11–12)."""

import csv
import json
import math
import os
import random
import statistics
import time

import engine
import policies


# ---------------------------------------------------------------------------
# Game runner
# ---------------------------------------------------------------------------

def play_game(rules, seed, game_id, policies_map, check=True):
    """Play one full game with built-in policies; returns the final state."""
    state = engine.new_game(rules, seed, game_id, policies_map)
    prng = random.Random(f"policy:{game_id}:{seed}")
    guard = 0
    while not engine.is_finished(state):
        guard += 1
        if guard > 4 * (rules["level1"]["max_rounds"]
                        + rules["level1"]["grace_full_rounds"]
                        + rules["level2"]["max_rounds"]) + 8:
            raise RuntimeError(f"game {game_id} exceeded its turn limit")
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act(
            policies_map[state["active_player"]], obs, prng)
        engine.apply_action(state, state["active_player"], obs["turn_id"],
                            action_id, reason)
    if check:
        engine.check_invariants(state)
    return state


# ---------------------------------------------------------------------------
# Experiment schedule (SPEC §13)
# ---------------------------------------------------------------------------

SEATS = ("P0", "P1", "P2", "P3")


def schedule_for(index, games=1000):
    """Policy assignment for batch game `index` (0-based within the batch).

    The batch is split in four equal blocks (SPEC §13, written for 1,000
    games; boundaries scale proportionally for other multiples of 4):

    block 1  balanced x4
    block 2  one aggressive rotating through seats, others balanced
    block 3  one greedy rotating through seats, others balanced
    block 4  random,greedy,aggressive,balanced cycled through all 24
             seat permutations
    """
    q = games // 4
    if index < q:
        return {p: "balanced" for p in SEATS}
    if index < 2 * q:
        seat = (index - q) % 4
        return {p: "aggressive" if i == seat else "balanced"
                for i, p in enumerate(SEATS)}
    if index < 3 * q:
        seat = (index - 2 * q) % 4
        return {p: "greedy" if i == seat else "balanced"
                for i, p in enumerate(SEATS)}
    perms = sorted(_permutations(("random", "greedy", "aggressive", "balanced")))
    perm = perms[(index - 3 * q) % len(perms)]
    return {p: perm[i] for i, p in enumerate(SEATS)}


def _permutations(items):
    if len(items) <= 1:
        return [tuple(items)]
    out = []
    for i, first in enumerate(items):
        rest = items[:i] + items[i + 1:]
        for tail in _permutations(rest):
            out.append((first,) + tail)
    return out


# ---------------------------------------------------------------------------
# CSV row
# ---------------------------------------------------------------------------

def game_row(res):
    """Flatten one result dict into a single CSV row."""
    row = {
        "game_id": res["game_id"], "seed": res["seed"],
        "outcome": res["outcome"], "winner": res["winner"] or "",
        "winner_policy": (res["policies"].get(res["winner"], "")
                          if res["winner"] else ""),
        "winner_turn_pos": (res["turn_order"].index(res["winner"]) + 1
                            if res["winner"] else ""),
        "first_challenger_pos": (res["turn_order"].index(res["first_challenger"])
                                 + 1 if res["first_challenger"] else ""),
        "end_reason": res["end_reason"],
        "first_challenger": res["first_challenger"] or "",
        "fc_policy": (res["policies"].get(res["first_challenger"], "")
                      if res["first_challenger"] else ""),
        "fc_won": int(bool(res["first_challenger_won"])),
        "comeback_win": int(bool(res["comeback_win"])),
        "phase1_timeout": int(res["phase1_timeout"]),
        "phase2_timeout": int(res["phase2_timeout"]),
        "rounds_l1": res["rounds_level1"], "rounds_l2": res["rounds_level2"],
        "total_rounds": res["total_rounds"],
        "turns_l1": res["turns_level1"], "turns_l2": res["turns_level2"],
        "total_turns": res["total_turns"],
    }
    for pid in SEATS:
        m = res["players"][pid]
        prefix = f"{pid}_"
        row[prefix + "policy"] = res["policies"].get(pid, "")
        row[prefix + "turns"] = m["turns"]
        row[prefix + "glory_final"] = m["glory_final"]
        row[prefix + "glory_earned"] = m["glory_earned"]
        row[prefix + "glory_spent"] = m["glory_spent"]
        row[prefix + "glory_wasted"] = m["glory_wasted_at_cap"]
        row[prefix + "eq_collected"] = m["equipment_collected"]
        row[prefix + "eq_auto"] = m["auto_granted"]
        row[prefix + "explores"] = m["explores"]
        row[prefix + "explored_3plus"] = int(m["districts_explored"] >= 3)
        row[prefix + "guard_tries"] = m["guard_post_attempts"]
        row[prefix + "guard_ok"] = m["guard_post_successes"]
        row[prefix + "duels_init"] = m["duels_initiated"]
        row[prefix + "duels_won_att"] = m["duels_won_attacker"]
        row[prefix + "duels_won_def"] = m["duels_won_defender"]
        row[prefix + "duels_defended"] = m["duels_defended"]
        row[prefix + "glory_stolen"] = m["glory_stolen"]
        row[prefix + "glory_lost_theft"] = m["glory_lost_theft"]
        row[prefix + "displaced"] = m["times_displaced"]
        row[prefix + "turns_skipped"] = m["turns_skipped"]
        row[prefix + "chamber_evictions"] = m["chamber_evictions"]
        row[prefix + "seals"] = "|".join(m["seals"])
        row[prefix + "seal_tries"] = m["seal_attempts"]
        for site in ("cellars", "guard_barracks", "peristyle"):
            row[prefix + f"seal_tries_{site}"] = m["seal_attempts_by_site"][site]
            row[prefix + f"seal_ok_{site}"] = int(site in m["seals"])
        row[prefix + "emperor_tries"] = m["emperor_attempts"]
        row[prefix + "emperor_hits"] = m["emperor_hits"]
        row[prefix + "glory_peristyle"] = m["glory_spent_peristyle"]
        row[prefix + "glory_emperor"] = m["glory_spent_emperor"]
        row[prefix + "won"] = int(res["winner"] == pid)
    return row


CSV_FIELDS = None  # filled by write_batch


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def wilson(successes, n, z=1.96):
    """Wilson score interval for a proportion."""
    if n == 0:
        return {"lo": 0.0, "hi": 0.0}
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"lo": round(max(0.0, center - half), 4),
            "hi": round(min(1.0, center + half), 4)}


def _pct(sorted_values, q):
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return round(sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac, 2)


def duration_stats(values):
    if not values:
        return {"count": 0}
    s = sorted(values)
    return {
        "count": len(s),
        "mean": round(statistics.mean(s), 2),
        "median": round(statistics.median(s), 2),
        "p90": _pct(s, 0.90),
        "p95": _pct(s, 0.95),
        "max": max(s),
        "min": min(s),
    }


def _rate_block(counter):
    """{key: {'games', 'wins', 'rate', 'ci95'}} from a wins/games counter."""
    out = {}
    for key in sorted(counter):
        games, wins = counter[key]
        rate = round(wins / games, 4) if games else 0.0
        out[key] = {"games": games, "wins": wins, "rate": rate,
                    "ci95": wilson(wins, games)}
    return out


# ---------------------------------------------------------------------------
# Batch summary
# ---------------------------------------------------------------------------

def summarize(rows, state_action_counts=None):
    """Aggregate CSV rows (and optional action-kind counts) into summary.json."""
    n = len(rows)
    wins = sum(r["outcome"] == "win" for r in rows)
    draws = n - wins
    p2_timeouts = sum(r["phase2_timeout"] for r in rows)
    p1_timeouts = sum(r["phase1_timeout"] for r in rows)

    by_policy, by_gate = {}, {}
    # One player sits at each turn position in every game.
    by_turn_pos = {f"pos{i}": [n, 0] for i in (1, 2, 3, 4)}
    for r in rows:
        for pid in SEATS:
            pol = r[f"{pid}_policy"]
            by_policy.setdefault(pol, [0, 0])
            by_policy[pol][0] += 1
            by_policy[pol][1] += r[f"{pid}_won"]
            by_gate.setdefault(pid, [0, 0])
            by_gate[pid][0] += 1
            by_gate[pid][1] += r[f"{pid}_won"]
        if r["winner_turn_pos"] != "":
            by_turn_pos[f"pos{r['winner_turn_pos']}"][1] += 1

    fc_games = sum(1 for r in rows if r["first_challenger"])
    fc_wins = sum(r["fc_won"] for r in rows)
    comebacks = sum(r["comeback_win"] for r in rows)

    def col(name):
        return [r[name] for r in rows]

    def player_cols(name):
        return [r[f"{pid}_{name}"] for r in rows for pid in SEATS]

    duel_total = sum(player_cols("duels_init"))
    duels_att_won = sum(player_cols("duels_won_att"))
    duels_def_won = sum(player_cols("duels_won_def"))
    total_turns = sum(col("total_turns"))

    seal_sites = {}
    for site in ("cellars", "guard_barracks", "peristyle"):
        tries = sum(r[f"{pid}_seal_tries_{site}"] for r in rows for pid in SEATS)
        ok = sum(r[f"{pid}_seal_ok_{site}"] for r in rows for pid in SEATS)
        seal_sites[site] = {
            "attempts": tries, "acquired": ok,
            "acquire_rate": round(ok / tries, 4) if tries else None,
        }
    emperor_tries = sum(player_cols("emperor_tries"))
    emperor_hits = sum(player_cols("emperor_hits"))
    stolen = sum(player_cols("glory_stolen"))
    lost_theft = sum(player_cols("glory_lost_theft"))
    displaced = sum(player_cols("displaced"))
    skipped = sum(player_cols("turns_skipped"))
    evictions = sum(player_cols("chamber_evictions"))

    summary = {
        "games": n,
        "wins": wins,
        "draws": draws,
        "phase1_timeouts": p1_timeouts,
        "phase2_timeouts": p2_timeouts,
        "win_rate": {"rate": round(wins / n, 4) if n else 0.0,
                     "ci95": wilson(wins, n)},
        "win_rate_by_policy": _rate_block(by_policy),
        "win_rate_by_gate": _rate_block(by_gate),
        "win_rate_by_turn_position": _rate_block(by_turn_pos),
        "first_challenger": {
            "games_with_challenger": fc_games,
            "challenger_win_rate": (round(fc_wins / fc_games, 4)
                                    if fc_games else None),
            "challenger_win_ci95": wilson(fc_wins, fc_games) if fc_games else None,
            "comeback_wins": comebacks,
            "comeback_share_of_wins": (round(comebacks / wins, 4)
                                       if wins else None),
        },
        "durations": {
            "total_rounds": duration_stats(col("total_rounds")),
            "total_turns": duration_stats(col("total_turns")),
            "rounds_level1": duration_stats(col("rounds_l1")),
            "turns_level1": duration_stats(col("turns_l1")),
            "rounds_level2": duration_stats(col("rounds_l2")),
            "turns_level2": duration_stats(col("turns_l2")),
        },
        "equipment": {
            "collected_per_player": duration_stats(player_cols("eq_collected")),
            "auto_granted_per_player": duration_stats(player_cols("eq_auto")),
            "players_exploring_3plus_share": round(
                sum(player_cols("explored_3plus")) / (4 * n), 4) if n else 0,
            "players_with_zero_collected": sum(
                v == 0 for v in player_cols("eq_collected")),
            "guard_post_attempts": sum(player_cols("guard_tries")),
            "guard_post_successes": sum(player_cols("guard_ok")),
        },
        "duels": {
            "total": duel_total,
            "per_game_mean": round(duel_total / n, 2) if n else 0,
            "games_with_2plus": sum(
                sum(r[f"{pid}_duels_init"] for pid in SEATS) >= 2 for r in rows),
            "attacker_wins": duels_att_won,
            "defender_wins": duels_def_won,
            "attacker_win_rate": round(duels_att_won / duel_total, 4)
            if duel_total else None,
            "defender_win_rate": round(duels_def_won / duel_total, 4)
            if duel_total else None,
            "duel_free_turn_share": round(1 - duel_total / total_turns, 4)
            if total_turns else None,
        },
        "duel_consequences": {
            "glory_stolen": stolen,
            "glory_lost_to_theft": lost_theft,
            "displacements": displaced,
            "displacements_per_game": round(displaced / n, 2) if n else 0,
            "chamber_evictions": evictions,
            "turns_skipped": skipped,
            "turns_skipped_per_game": round(skipped / n, 2) if n else 0,
        },
        "glory": {
            "earned_per_player": duration_stats(player_cols("glory_earned")),
            "spent_per_player": duration_stats(player_cols("glory_spent")),
            "wasted_at_cap_per_player": duration_stats(
                player_cols("glory_wasted")),
            "spent_on_peristyle": sum(player_cols("glory_peristyle")),
            "spent_on_emperor": sum(player_cols("glory_emperor")),
        },
        "seals": {
            "attempts_per_player": duration_stats(player_cols("seal_tries")),
            "by_site": seal_sites,
            "peristyle_glory_purchases": sum(
                v > 0 for v in player_cols("glory_peristyle")),
        },
        "emperor": {
            "attempts": emperor_tries,
            "hits": emperor_hits,
            "hit_rate": round(emperor_hits / emperor_tries, 4)
            if emperor_tries else None,
            "attempts_per_player": duration_stats(player_cols("emperor_tries")),
        },
    }
    if state_action_counts:
        total_actions = sum(state_action_counts.values())
        summary["action_categories"] = {
            k: {"count": v,
                "share": round(v / total_actions, 4) if total_actions else 0}
            for k, v in sorted(state_action_counts.items())
        }
    return summary


def count_actions(states):
    counts = {}
    for state in states:
        for record in state["events"]:
            kind = record["action"]["kind"]
            counts[kind] = counts.get(kind, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Batch directory writer
# ---------------------------------------------------------------------------

def write_run_dir(run_dir, state):
    """Persist a finished game directory (without state.json for samples)."""
    os.makedirs(run_dir, exist_ok=True)
    engine.write_run(run_dir, state)


def run_batch(rules, out_dir, games, seed_base, schedule, rules_file,
              progress_every=200):
    """Play `games` games; write results; return (rows, summary, states)."""
    os.makedirs(out_dir, exist_ok=True)
    sample_n = rules["logging"]["sample_games_per_batch"]
    save_anomalous = rules["logging"]["save_anomalous_game_logs"]
    rows, states = [], []
    action_counts = {}
    started = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"
    for i in range(games):
        seed = seed_base + i
        pol = schedule(i, games)
        game_id = f"g{seed:06d}"
        state = play_game(rules, seed, game_id, pol)
        res = engine.result(state)
        rows.append(game_row(res))
        states.append(state)
        for record in state["events"]:
            kind = record["action"]["kind"]
            action_counts[kind] = action_counts.get(kind, 0) + 1
        keep = i < sample_n or (save_anomalous and (
            res["outcome"] == "draw" or res["total_turns"] > 150))
        if rules["logging"]["save_full_batch_logs"] or keep:
            write_run_dir(os.path.join(out_dir, "sample_games", game_id), state)
        if progress_every and (i + 1) % progress_every == 0:
            print(f"  ... {i + 1}/{games} games", flush=True)

    fields = list(rows[0].keys()) if rows else []
    with open(os.path.join(out_dir, "games.csv"), "w", newline="",
              encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize(rows, action_counts)
    summary["engine_version"] = engine.ENGINE_VERSION
    experiment = {
        "rules_file": rules_file,
        "rules_hash": engine.rules_hash(rules),
        "seed_base": seed_base,
        "games": games,
        "engine_version": engine.ENGINE_VERSION,
        "started": started,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
        "schedule": schedule.__name__,
        "policies_used": sorted({r[f"{pid}_policy"] for r in rows
                                 for pid in SEATS}),
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "experiment.json"), "w",
              encoding="utf-8") as fh:
        json.dump(experiment, fh, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "rules.snapshot.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rules, fh, indent=2, sort_keys=True)
    return rows, summary, states
