# ABOUTME: Metrics for Arena series: Wilson intervals, percentiles, missed
# ABOUTME: interventions, and the summary.json assembly from game logs.

import json
import math

WILSON_Z_95 = 1.959963984540054
SEATS = ("P0", "P1", "P2", "P3")


def player_label(provider, model):
    """The scoreboard name for one seat: provider/model, or bare provider."""
    if model in (None, "", "local"):
        return provider
    return f"{provider}/{model}"


def wilson_interval(successes, total, z=WILSON_Z_95):
    """The 95% Wilson score interval for a binomial proportion.

    Returns (low, high) rounded to 4 decimals, or None when total is 0.
    """
    if total <= 0:
        return None
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    spread = (z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total))
              / denom)
    low = max(0.0, center - spread)
    high = min(1.0, center + spread)
    return (round(low, 4), round(high, 4))


def percentile(values, q):
    """Linear-interpolation percentile of a list of numbers; None when empty."""
    if not values:
        return None
    data = sorted(values)
    if len(data) == 1:
        return data[0]
    pos = q * (len(data) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    frac = pos - low
    return data[low] + (data[high] - data[low]) * frac


def count_missed_interventions(decisions, result_line):
    """Count missed interventions per seat from one game's match.jsonl lines.

    A missed intervention is a turn where all of these hold:
    a) the observation has a pending claim owned by another seat,
    b) the legal actions contain a duel against that claimant,
    c) the seat selected a different action,
    d) the game ended with end_reason survived_window and that claimant
       as the winner, on the claim that was pending at this turn.
    """
    counts = {}
    end_reason = (result_line or {}).get("end_reason")
    winner = (result_line or {}).get("winner")
    if end_reason != "survived_window" or not winner:
        return counts
    winner_claim_id = None
    for line in reversed(decisions):
        pending = (line.get("observation") or {}).get("pending_claim")
        if pending and pending.get("player") == winner \
                and pending.get("claim_id") is not None:
            winner_claim_id = pending["claim_id"]
            break
    for line in decisions:
        obs = line.get("observation") or {}
        pending = obs.get("pending_claim")
        seat = line.get("seat")
        if not pending or pending.get("player") == seat:
            continue
        if winner != pending.get("player"):
            continue
        if winner_claim_id is not None \
                and pending.get("claim_id") != winner_claim_id:
            continue
        claimant_duels = {action["action_id"]
                          for action in obs.get("legal_actions", [])
                          if action.get("kind") == "duel"
                          and action.get("target") == pending.get("player")}
        if not claimant_duels:
            continue
        if line.get("action_id") in claimant_duels:
            continue
        counts[seat] = counts.get(seat, 0) + 1
    return counts


def parse_game_log(path):
    """Parse one match.jsonl into the pieces the series report needs."""
    match_start = None
    failure = None
    result = None
    decisions = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            kind = record.get("type")
            if kind == "match_start":
                match_start = record
            elif kind == "decision":
                decisions.append(record)
            elif kind == "failure":
                failure = record
            elif kind == "result":
                result = record
    per_seat = {}
    for seat, entry in ((result or {}).get("seats") or {}).items():
        per_seat[seat] = {"provider": entry.get("provider"),
                          "model": entry.get("model"),
                          "decisions": entry.get("decisions", 0),
                          "calls": entry.get("calls", 0),
                          "cost_usd": entry.get("cost_usd", 0.0),
                          "input_tokens": 0,
                          "latencies": [],
                          "missed_interventions": 0}
    for line in decisions:
        seat = line.get("seat")
        entry = per_seat.get(seat)
        if entry is None:
            continue
        usage = line.get("usage") or {}
        tokens = usage.get("input_tokens")
        if isinstance(tokens, (int, float)) and not isinstance(tokens, bool):
            entry["input_tokens"] += int(tokens)
        latency = line.get("latency_ms")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            entry["latencies"].append(latency)
    return {"match_start": match_start, "decisions": decisions,
            "failure": failure, "result": result, "per_seat": per_seat}


def build_summary(players, seeds, game_entries, shuffle_totals, meta):
    """Assemble the series summary.json document.

    players: the series player specs, [{"provider", "model"}, ...] in
    declaration order. game_entries: one dict per planned game, either
    {"status": "played", "seed", "seed_index", "game", "run_dir",
    "seat_players", "result", "per_seat"} or {"status": "skipped",
    "seed", "seed_index", "game", "reason", "run_dir": None}.
    shuffle_totals: {label: {"selected", "turns"}} accumulated over all
    games. meta: series identity, budget state, and timing.
    """
    stats = {}
    for spec in players:
        label = player_label(spec.get("provider"), spec.get("model"))
        stats[label] = {"provider": spec.get("provider"),
                        "model": spec.get("model"),
                        "games": 0, "wins": 0,
                        "wins_by_seat": {seat: 0 for seat in SEATS},
                        "incomplete_games": 0, "missed_interventions": 0,
                        "decisions": 0, "calls": 0, "input_tokens": 0,
                        "cost_usd": 0.0, "latencies": [],
                        "position1": {"selected": 0, "turns": 0}}
    games_played = 0
    games_skipped = 0
    games_incomplete = 0
    for entry in game_entries:
        if entry.get("status") == "skipped":
            games_skipped += 1
            continue
        games_played += 1
        result = entry.get("result") or {}
        if result.get("incomplete"):
            games_incomplete += 1
        seat_players = entry.get("seat_players") or {}
        per_seat = entry.get("per_seat") or {}
        for seat, label in seat_players.items():
            stat = stats.get(label)
            seat_stat = per_seat.get(seat)
            if stat is None or seat_stat is None:
                continue
            stat["games"] += 1
            if result.get("outcome") == "win" \
                    and result.get("winner") == seat:
                stat["wins"] += 1
                stat["wins_by_seat"][seat] += 1
            if result.get("incomplete"):
                stat["incomplete_games"] += 1
            stat["missed_interventions"] += seat_stat.get(
                "missed_interventions", 0)
            stat["decisions"] += seat_stat.get("decisions", 0)
            stat["calls"] += seat_stat.get("calls", 0)
            stat["input_tokens"] += seat_stat.get("input_tokens", 0)
            stat["cost_usd"] += seat_stat.get("cost_usd", 0.0)
            stat["latencies"].extend(seat_stat.get("latencies", []))
    for label, totals in (shuffle_totals or {}).items():
        stat = stats.get(label)
        if stat is not None:
            stat["position1"]["selected"] += totals.get("selected", 0)
            stat["position1"]["turns"] += totals.get("turns", 0)
    players_stats = {}
    for label, stat in stats.items():
        turns = stat["position1"]["turns"]
        selected = stat["position1"]["selected"]
        players_stats[label] = {
            "provider": stat["provider"], "model": stat["model"],
            "games": stat["games"], "wins": stat["wins"],
            "win_rate": (round(stat["wins"] / stat["games"], 4)
                         if stat["games"] else None),
            "win_rate_wilson_95": wilson_interval(stat["wins"],
                                                  stat["games"]),
            "wins_by_seat": stat["wins_by_seat"],
            "incomplete_games": stat["incomplete_games"],
            "missed_interventions": stat["missed_interventions"],
            "decisions": stat["decisions"], "calls": stat["calls"],
            "input_tokens": stat["input_tokens"],
            "cost_usd": round(stat["cost_usd"], 6),
            "latency_ms": {
                "median": (round(percentile(stat["latencies"], 0.5), 1)
                           if stat["latencies"] else None),
                "p95": (round(percentile(stat["latencies"], 0.95), 1)
                        if stat["latencies"] else None)},
            "position1": {"selected": selected, "turns": turns,
                          "rate": (round(selected / turns, 4)
                                   if turns else None)}}
    total_cost = sum(entry["cost_usd"] for entry in players_stats.values())
    return {"type": "series_result", "series_id": meta.get("series_id"),
            "rules": {"path": meta.get("rules_path"),
                      "rules_hash": meta.get("rules_hash")},
            "seeds": seeds,
            "rotate_seats": meta.get("rotate_seats"),
            "shuffle_candidates": meta.get("shuffle_candidates"),
            "budget": meta.get("budget"),
            "started_utc": meta.get("started_utc"),
            "duration_s": meta.get("duration_s"),
            "games": {"played": games_played, "skipped": games_skipped,
                      "incomplete": games_incomplete,
                      "total": len(game_entries)},
            "total_cost_usd": round(total_cost, 6),
            "players": players_stats,
            "game_list": game_entries}


def games_incomplete_count(summary):
    """Number of played games that ended incomplete, from a summary."""
    return sum(1 for entry in summary.get("game_list", [])
               if entry.get("status") == "played"
               and (entry.get("result") or {}).get("incomplete"))
