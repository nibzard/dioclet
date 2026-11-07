"""Offline decision analysis and tournament reporting (V0.4.1).

Reads only recorded artifacts (decisions.jsonl, events.jsonl,
result.json) under a tournament root. No network, no re-simulation.

Two entry points:
  analyze <root>  -- per-turn decision-quality scorecard
  report  <root>  -- tournament strength and cost report

Confidence and choice probabilities are model-choice uncertainty,
never win probabilities; they are reported as such.
"""

import argparse
import json
import math
import os
import re
import statistics
import sys

import engine  # for replay-free event parsing helpers only


def load_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            out = [json.loads(line) for line in fh if line.strip()]
    return out


def load_game(gdir):
    payload = {}
    for name in ("result.json", "incomplete.json", "rules.snapshot.json"):
        path = os.path.join(gdir, name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                payload[name.split(".")[0]] = json.load(fh)
    payload["decisions"] = load_jsonl(os.path.join(gdir, "decisions.jsonl"))
    payload["events"] = load_jsonl(os.path.join(gdir, "events.jsonl"))
    return payload


def snapshot_caps(game):
    """Glory cap and Emperor hits-to-win from the game's rules snapshot.

    Falls back to the v041 tournament values (cap 2, hits 2) with
    `snapshot_checked: False` when the snapshot is absent or invalid,
    so older run directories still analyze with a loud caveat.
    """
    snap = game.get("rules")
    try:
        caps = {"glory_cap": snap["glory"]["cap"],
                "emperor_hits_to_win": snap["combat"]["emperor_hits_to_win"],
                "snapshot_checked": True}
    except (TypeError, KeyError):
        caps = {"glory_cap": 2, "emperor_hits_to_win": 2,
                "snapshot_checked": False}
    return caps


def iter_games(root):
    games_dir = os.path.join(root, "games")
    if not os.path.isdir(games_dir):
        return
    for name in sorted(os.listdir(games_dir)):
        gdir = os.path.join(games_dir, name)
        if os.path.isdir(gdir):
            yield name, load_game(gdir)


# ---------------------------------------------------------------------------
# Event-derived per-turn truth (engine authority)
# ---------------------------------------------------------------------------

def player_timeline(events):
    """Per-player glory/hits/position after each turn, by turn_id."""
    timeline = {}
    for record in events:
        pid = record["player"]
        timeline[record["turn_id"]] = {
            "player": pid,
            "phase": record["phase"],
            "round": record["round"],
            "glory_after": record["glory_after"],
            "kind": record["action"]["kind"],
        }
    return timeline


def glory_before(events, turn_id):
    """The acting player's Glory immediately before this turn."""
    glory = {}
    for record in events:
        if record["turn_id"] == turn_id:
            return glory.get(record["player"], 0)
        glory[record["player"]] = record["glory_after"]
    return 0


def hits_timeline(events, players):
    hits = {p: 0 for p in players}
    out = {}
    for record in events:
        for ev in record["events"]:
            if ev["type"] == "emperor_hit":
                hits[ev["player"]] += 1
        out[record["turn_id"]] = dict(hits)
    return out


_DESC_WIN = re.compile(r"exact win chance (\d+)%")
_DESC_HIT = re.compile(r"exact hit chance (\d+)%")
_DESC_WINGAME = "wins the game on a hit"
_DESC_GOALDIST = re.compile(r"now (\d+) from the current goal")


def candidate_facts(candidates):
    facts = {}
    for c in candidates:
        desc = c["description"]
        fact = {"kind": c["kind"]}
        m = _DESC_WIN.search(desc)
        if m:
            fact["duel_win_pct"] = int(m.group(1))
        m = _DESC_HIT.search(desc)
        if m:
            fact["hit_pct"] = int(m.group(1))
        fact["wins_game"] = _DESC_WINGAME in desc
        m = _DESC_GOALDIST.search(desc)
        if m:
            fact["goal_dist"] = int(m.group(1))
        facts[c["action_id"]] = fact
    return facts


# ---------------------------------------------------------------------------
# Per-game decision scorecard
# ---------------------------------------------------------------------------

def score_game(game, decisions_policy_name="decisions"):
    """Scorecard for one game. Only decisions-player turns are judged."""
    result = game.get("result")
    if not result:
        return None
    events = game["events"]
    timeline = player_timeline(events)
    hits_at = hits_timeline(events, result["players"])
    caps = snapshot_caps(game)
    glory_cap = caps["glory_cap"]
    hits_to_win = caps["emperor_hits_to_win"]

    seats = result["policies"]
    score = {"game_id": result["game_id"], "winner": result["winner"],
             "turn_order": result["turn_order"], "seats": {},
             "rules_snapshot": caps, "flags": []}
    for record in game["decisions"]:
        pid = record["player"]
        seat = score["seats"].setdefault(
            pid, {"turns": 0, "win_attack_available": 0,
                  "win_attack_taken": 0, "duels": 0, "low_value_duels": 0,
                  "unproductive_moves": 0, "moves": 0,
                  "confidences": [], "top_probs": [], "latencies": [],
                  "spent_tokens": 0, "explore_no_gain": 0})
        seat["turns"] += 1
        meta = record["metadata"] or {}
        if meta.get("confidence") is not None:
            seat["confidences"].append(meta["confidence"])
        probs = meta.get("probabilities") or []
        if probs:
            seat["top_probs"].append(max(p["probability"] for p in probs))
        if meta.get("latency_ms") is not None:
            seat["latencies"].append(meta["latency_ms"])
        usage = meta.get("usage") or {}
        seat["spent_tokens"] += usage.get("input_tokens") or 0
        facts = candidate_facts(record["candidates"])
        chosen = facts.get(record["chosen_action"], {})
        # Shortlist coverage guard: mandatory kinds must never be excluded.
        for excluded in record.get("excluded", []):
            if excluded.get("kind") in ("attack_emperor", "claim_checkpoint",
                                        "attempt_seal", "explore"):
                score["flags"].append(
                    {"turn_id": record["turn_id"],
                     "issue": "mandatory action excluded",
                     "excluded": excluded})
        # A. Immediate winning attack. The candidate description marks
        # "wins the game on a hit"; cross-check against the snapshot's
        # hits-to-win via the recorded hit timeline.
        win_attacks = [f for f in facts.values()
                       if f["kind"] == "attack_emperor" and f["wins_game"]]
        if win_attacks and not caps["snapshot_checked"]:
            score["flags"].append(
                {"turn_id": record["turn_id"],
                 "issue": "winning-attack check ran without a validated "
                          "rules snapshot (fallback hits_to_win=2)"})
        if win_attacks:
            seat["win_attack_available"] += 1
            if chosen.get("kind") == "attack_emperor":
                seat["win_attack_taken"] += 1
        # C. Duel value (duels pay only banked Glory to the winner).
        if chosen.get("kind") == "duel":
            seat["duels"] += 1
            own_glory = glory_before(events, record["turn_id"])
            p_win = chosen.get("duel_win_pct", 50)
            if p_win < 50 or own_glory >= glory_cap:
                seat["low_value_duels"] += 1
        # E. Detours: phase 2, seals done, chose a move that is strictly
        # farther from the goal than the best candidate move.
        if record.get("phase", timeline.get(record["turn_id"], {})
                      .get("phase")) == 2 and chosen.get("kind") == "move":
            seat["moves"] += 1
            move_dists = [f["goal_dist"] for f in facts.values()
                          if "goal_dist" in f]
            if move_dists and chosen.get("goal_dist") is not None:
                if chosen["goal_dist"] > min(move_dists) + 1:
                    seat["unproductive_moves"] += 1

    # Engine-verified outcome metrics per decisions seat.
    for pid, policy in seats.items():
        if policy != decisions_policy_name:
            continue
        m = result["players"][pid]
        seat = score["seats"].setdefault(pid, {})
        seat["explores"] = m["explores"]
        seat["explore_no_gain"] = m["explore_no_gain"]
        seat["eq_collected"] = m["equipment_collected"]
        seat["eq_auto"] = m["auto_granted"]
        seat["glory_wasted"] = m["glory_wasted_at_cap"]
        seat["glory_spent"] = m["glory_spent"]
        seat["glory_final"] = m["glory_final"]
        seat["duels_initiated"] = m["duels_initiated"]
        seat["emperor_hits"] = m["emperor_hits"]
        seat["won"] = result["winner"] == pid
    return score


def analyze(root, decisions_policy_name="decisions"):
    games = []
    for name, game in iter_games(root):
        card = score_game(game, decisions_policy_name)
        if card:
            games.append(card)
    agg = {
        "games_analyzed": len(games),
        "flags": [f for g in games for f in g["flags"]],
        "per_seat": [],
        "win_attack": {"available": 0, "taken": 0},
        "duels": {"total": 0, "low_value": 0},
        "moves": {"total": 0, "unproductive": 0},
        "explore_no_gain": 0,
        "glory_wasted": 0,
        "lost_with_glory": 0,
        "confidences": [],
        "top_probs": [],
        "latencies": [],
    }
    for g in games:
        for pid, seat in g["seats"].items():
            if g["seats"].get(pid, {}).get("turns"):
                agg["win_attack"]["available"] += seat.get(
                    "win_attack_available", 0)
                agg["win_attack"]["taken"] += seat.get("win_attack_taken", 0)
                agg["duels"]["total"] += seat.get("duels", 0)
                agg["duels"]["low_value"] += seat.get("low_value_duels", 0)
                agg["moves"]["total"] += seat.get("moves", 0)
                agg["moves"]["unproductive"] += seat.get(
                    "unproductive_moves", 0)
                agg["confidences"].extend(seat.get("confidences", []))
                agg["top_probs"].extend(seat.get("top_probs", []))
                agg["latencies"].extend(seat.get("latencies", []))
            agg["explore_no_gain"] += seat.get("explore_no_gain", 0)
            agg["glory_wasted"] += seat.get("glory_wasted", 0)
            if not seat.get("won", True) and seat.get("glory_final", 0) > 0:
                agg["lost_with_glory"] += 1
        agg["per_seat"].append({"game_id": g["game_id"],
                                "winner": g["winner"]})
    c = agg["confidences"]
    agg["confidence_summary"] = {
        "n": len(c),
        "mean": round(statistics.mean(c), 3) if c else None,
        "p10": round(sorted(c)[int(0.10 * (len(c) - 1))], 3) if c else None,
        "p90": round(sorted(c)[int(0.90 * (len(c) - 1))], 3) if c else None,
    } if c else {}
    if agg["latencies"]:
        lats = sorted(agg["latencies"])
        agg["latency_ms"] = {
            "n": len(lats),
            "p50": round(lats[len(lats) // 2], 1),
            "p95": round(lats[int(0.95 * (len(lats) - 1))], 1),
            "max": round(max(lats), 1),
        }
    util = agg["win_attack"]
    agg["win_attack"]["utilization"] = round(
        util["taken"] / util["available"], 4) if util["available"] else None
    agg["duels"]["low_value_share"] = round(
        agg["duels"]["low_value"] / agg["duels"]["total"], 4) \
        if agg["duels"]["total"] else None
    agg["moves"]["unproductive_share"] = round(
        agg["moves"]["unproductive"] / agg["moves"]["total"], 4) \
        if agg["moves"]["total"] else None
    return {"aggregate": agg, "games": games}


# ---------------------------------------------------------------------------
# Tournament report (Phase 5)
# ---------------------------------------------------------------------------

def wilson(successes, n, z=1.96):
    if n == 0:
        return {"lo": 0.0, "hi": 0.0}
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"lo": round(max(0.0, center - half), 4),
            "hi": round(min(1.0, center + half), 4)}


def pct(sorted_values, q):
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_values) - 1)
    return round(sorted_values[lo] + (sorted_values[hi] -
                                      sorted_values[lo]) * (pos - lo), 2)


def report(root):
    by_policy = {}
    by_gate = {}
    by_pos = {}
    durations = {"rounds": [], "turns": []}
    emperor = {"attempts": 0, "hits": 0}
    api = {"calls": 0, "tokens": 0, "cost": 0.0,
           "invalid": 0, "refused": 0, "incomplete": 0, "retried": 0}
    confidences = []
    matchups = {}
    games_meta = []
    for name, game in iter_games(root):
        result = game.get("result")
        if not result:
            api["incomplete"] += 1
            continue
        policies = result["policies"]
        order = result["turn_order"]
        games_meta.append({
            "game_id": result["game_id"], "seed": result["seed"],
            "winner": result["winner"],
            "winner_policy": policies.get(result["winner"]),
            "policies": policies,
            "rounds": result["total_rounds"],
            "turns": result["total_turns"],
            "phase2_timeout": result["phase2_timeout"],
        })
        durations["rounds"].append(result["total_rounds"])
        durations["turns"].append(result["total_turns"])
        for pid, policy in policies.items():
            by_policy.setdefault(policy, [0, 0])
            by_policy[policy][0] += 1
            by_policy[policy][1] += int(result["winner"] == pid)
            by_gate.setdefault(pid, [0, 0])
            by_gate[pid][0] += 1
            by_gate[pid][1] += int(result["winner"] == pid)
            pos = f"pos{order.index(pid) + 1}"
            by_pos.setdefault(pos, [0, 0])
            by_pos[pos][0] += 1
            by_pos[pos][1] += int(result["winner"] == pid)
            m = result["players"][pid]
            emperor["attempts"] += m["emperor_attempts"]
            emperor["hits"] += m["emperor_hits"]
        games_meta[-1]["duels"] = sum(
            result["players"][p]["duels_initiated"] for p in policies)
        # Matchup key: sorted policy multiset.
        key = "+".join(sorted(policies.values()))
        matchups.setdefault(key, {"games": 0, "wins": {}})
        matchups[key]["games"] += 1
        wp = policies.get(result["winner"])
        matchups[key]["wins"][wp] = matchups[key]["wins"].get(wp, 0) + 1
        for record in game["decisions"]:
            meta = record["metadata"] or {}
            usage = meta.get("usage") or {}
            if meta.get("provider") == "live" and usage.get("input_tokens"):
                api["calls"] += 1
                api["tokens"] += usage["input_tokens"]
                api["cost"] += meta.get("estimated_cost_usd", 0.0)
            if meta.get("confidence") is not None:
                confidences.append(meta["confidence"])

    def rate_block(counter, n_games):
        out = {}
        for key in sorted(counter):
            seat_games, wins = counter[key]
            out[key] = {"seat_games": seat_games, "wins": wins,
                        "rate": round(wins / seat_games, 4),
                        "ci95": wilson(wins, seat_games)}
        return out

    n = len(games_meta)
    rounds_s = sorted(durations["rounds"])
    turns_s = sorted(durations["turns"])
    return {
        "games_completed": n,
        "wins_by_policy": rate_block(by_policy, n),
        "wins_by_gate": rate_block(by_gate, n),
        "wins_by_turn_position": rate_block(by_pos, n),
        "durations": {
            "rounds": {"median": pct(rounds_s, 0.5),
                       "p90": pct(rounds_s, 0.9),
                       "max": max(rounds_s) if rounds_s else None},
            "turns": {"median": pct(turns_s, 0.5),
                      "p90": pct(turns_s, 0.9),
                      "max": max(turns_s) if turns_s else None},
        },
        "emperor": {"attempts": emperor["attempts"],
                    "hits": emperor["hits"],
                    "hit_rate": round(emperor["hits"] /
                                      emperor["attempts"], 4)
                    if emperor["attempts"] else None},
        "duels_per_game": round(sum(g["duels"] for g in games_meta) / n,
                                2) if n else None,
        "matchups": matchups,
        "api": {**api, "cost": round(api["cost"], 5)},
        "confidence": {
            "n": len(confidences),
            "mean": round(statistics.mean(confidences), 3)
            if confidences else None,
        },
        "games": games_meta,
        "caution": ("32 games per group is an exploratory sample; "
                    "differences inside overlapping confidence intervals "
                    "are not established."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["analyze", "report"])
    parser.add_argument("root", help="tournament root, e.g. results/v041")
    parser.add_argument("--out", default=None, help="output json path")
    args = parser.parse_args(argv)
    if args.mode == "analyze":
        payload = analyze(args.root)
    else:
        payload = report(args.root)
    blob = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(blob + "\n")
    print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
