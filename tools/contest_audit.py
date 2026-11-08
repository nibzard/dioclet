#!/usr/bin/env python3
"""Legal contest-availability audit for succession suites.

The V0.8 release review found a blind spot: the runner's promotion
checks let a contest fee of 2 pass because bot metrics stayed healthy
while live responders, holding 0 or 1 Prestige, were never offered a
legal contest at all. ``tools/succession_experiments.py`` counts
challenges that were chosen; nothing counted contests that were
*offerable*. This tool closes that gap without touching the frozen
evaluator.

For every game recorded in a suite's ``games.jsonl`` it re-runs the
exact same deterministic offline game (same rules, seed, gate order,
and probe RNG) and, at every claim-response turn, records from the
public observation only:

- the responder's Prestige and the distance to the claimant;
- whether the mandatory contest fee was affordable;
- whether any legal contest action was offered (reach plus purse);
- whether the optional boosted challenge was offered;
- which action was chosen and, for contests, the duel outcome.

Re-runs must reproduce the recorded winner and turn count; a mismatch
is a replay failure, not a draw. Aggregates are written next to the
suite. The cross-fee table answers, for the response purses that
actually occurred, which fee levels those purses could have paid.
"""

import argparse
import copy
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import engine
import policies
from tools import succession_experiments


def public_distance(obs, source, target):
    board = obs["board"]
    blocked = frozenset(map(tuple, board["blocked"]))
    start, goal = tuple(source), tuple(target)
    if start == goal:
        return 0
    distances = {start: 0}
    todo = [start]
    while todo:
        nxt = []
        for x, y in todo:
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                n = (x + dx, y + dy)
                if (0 <= n[0] < board["width"] and 0 <= n[1] < board["height"]
                        and n not in blocked and n not in distances):
                    distances[n] = distances[(x, y)] + 1
                    if n == goal:
                        return distances[n]
                    nxt.append(n)
        todo = nxt
    return None


def audit_game(rules, record):
    """Re-run one recorded game and return (turn_rows, claim_rows, ok)."""
    game_rules = copy.deepcopy(rules)
    game_rules["succession"]["gate_assignment"] = "manual"
    assignment = record["players"]
    gates = record["result"]["gate_assignments"]
    game_rules["succession"]["gate_order"] = [gates[pid] for pid in ("P0", "P1", "P2", "P3")]
    seed, game_id = record["seed"], record["game_id"]
    state = engine.new_game(game_rules, seed, game_id, assignment)
    rng = __import__("random").Random(f"probe:{seed}")
    cap = 4 * (rules["level1"]["max_rounds"] + rules["level2"]["max_rounds"] + 3)
    turn_rows, claim_rows = [], []
    ok = True
    for _ in range(cap):
        if engine.is_finished(state):
            break
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act(assignment[state["active_player"]], obs, rng)
        pending = obs.get("pending_claim")
        row = None
        if pending and pending["player"] != obs["viewer"]:
            duels = [a for a in obs["legal_actions"]
                     if a["kind"] == "duel" and a.get("target") == pending["player"]]
            me = obs["players"][obs["viewer"]]
            fee = duels[0]["contest_cost"] if duels else obs["progress"].get("contest_cost", 0)
            chosen = next(a for a in obs["legal_actions"] if a["action_id"] == action_id)
            row = {
                "game_id": game_id, "turn_id": obs["turn_id"], "round": obs["round"],
                "responder": obs["viewer"], "profile": assignment[obs["viewer"]],
                "claim_id": pending["claim_id"], "claimant": pending["player"],
                "responder_prestige": me["prestige"], "roll": obs["movement_die"],
                "contest_fee": fee,
                "distance_to_claimant": public_distance(obs, me["position"],
                                                        obs["players"][pending["player"]]["position"]),
                "contest_offered": bool(duels),
                "boost_offered": any(a["spend_prestige"] for a in duels),
                "can_afford_fee": me["prestige"] >= fee,
                "can_afford_boost": me["prestige"] >= fee + obs["progress"]["challenge_cost"],
                "chosen_kind": chosen["kind"],
                "chosen_contest": bool(chosen["kind"] == "duel" and chosen.get("target") == pending["player"]),
                "chosen_boost": bool(chosen["kind"] == "duel" and chosen.get("target") == pending["player"]
                                     and chosen.get("spend_prestige")),
            }
        record_out = engine.apply_action(state, state["active_player"], obs["turn_id"],
                                         action_id, reason)
        if row is not None:
            events = record_out.get("events", [])
            duel = next((e for e in events if e["type"] == "duel" and e["attacker"] == row["responder"]), None)
            row["contest_won"] = bool(duel and duel["winner"] == row["responder"]) if row["chosen_contest"] else None
            row["claim_cancelled_this_turn"] = any(e["type"] == "claim_cancelled" for e in events)
            turn_rows.append(row)
        for event in record_out.get("events", []):
            if event["type"] == "claim_proclaimed":
                claim_rows.append({"game_id": game_id, "claim_id": event["claim_id"],
                                   "claimant": event["player"], "turn_id": record_out["turn_id"],
                                   "responses": 0, "offered": 0, "contests": 0,
                                   "canceled": False, "cancel_cause": None, "won": False})
            elif event["type"] == "claim_response" and claim_rows:
                claim_rows[-1]["responses"] += 1
            elif event["type"] == "claim_cancelled" and claim_rows:
                claim_rows[-1]["canceled"] = True
                claim_rows[-1]["cancel_cause"] = event.get("cause")
            elif event["type"] == "game_won" and claim_rows and event.get("cause") == "acclamation":
                claim_rows[-1]["won"] = True
    if not engine.is_finished(state):
        raise RuntimeError(f"{game_id}: audit re-run exceeded its turn bound")
    engine.check_invariants(state)
    result = engine.result(state)
    ok = (result["winner"] == record["winner"] and
          result["total_turns"] == record["total_turns"] and
          result["outcome"] == record["outcome"])
    by_claim = {}
    for row in turn_rows:
        entry = by_claim.setdefault(row["claim_id"], {"offered": 0, "contests": 0, "turns": 0})
        entry["turns"] += 1
        entry["offered"] += row["contest_offered"]
        entry["contests"] += row["chosen_contest"]
    for claim in claim_rows:
        seen = by_claim.get(claim["claim_id"], {"offered": 0, "contests": 0, "turns": 0})
        claim["offered"] = seen["offered"]
        claim["contests"] = seen["contests"]
    return turn_rows, claim_rows, ok


def summarize(turn_rows, claim_rows, games_ok, games_total):
    response_turns = len(turn_rows)
    claims = len(claim_rows)
    purses = [r["responder_prestige"] for r in turn_rows]

    def rate(predicate):
        return (sum(1 for r in turn_rows if predicate(r)) / response_turns) if response_turns else None

    fee = turn_rows[0]["contest_fee"] if turn_rows else None
    offered_claims = sum(1 for c in claim_rows if c["offered"] > 0)
    won_claims = [c for c in claim_rows if c["won"]]
    crowned_without_option = sum(1 for c in won_claims if c["offered"] == 0)
    contested_claims = sum(1 for c in claim_rows if c["contests"] > 0)
    canceled_claims = sum(1 for c in claim_rows if c["canceled"])
    return {
        "games_total": games_total, "games_replay_verified": games_ok,
        "response_turns": response_turns, "claims": claims,
        "contest_fee": fee,
        "contest_offered_rate": rate(lambda r: r["contest_offered"]),
        "can_afford_fee_rate": rate(lambda r: r["can_afford_fee"]),
        "blocked_by_purse_share": rate(lambda r: not r["contest_offered"] and not r["can_afford_fee"]),
        "blocked_by_position_share": rate(lambda r: not r["contest_offered"] and r["can_afford_fee"]),
        "boost_offered_rate": rate(lambda r: r["boost_offered"]),
        "chosen_contest_rate": rate(lambda r: r["chosen_contest"]),
        "chosen_given_offered": (sum(1 for r in turn_rows if r["chosen_contest"] and r["contest_offered"])
                                 / sum(1 for r in turn_rows if r["contest_offered"]))
                                if any(r["contest_offered"] for r in turn_rows) else None,
        "contest_win_rate_when_chosen": (sum(1 for r in turn_rows if r["contest_won"])
                                         / sum(1 for r in turn_rows if r["chosen_contest"]))
                                        if any(r["chosen_contest"] for r in turn_rows) else None,
        "claims_with_contest_option": (offered_claims / claims) if claims else None,
        "claims_contested": (contested_claims / claims) if claims else None,
        "claims_canceled": (canceled_claims / claims) if claims else None,
        "claims_won_by_acclamation": (len(won_claims) / claims) if claims else None,
        "claims_crowned_without_legal_contest": (crowned_without_option / claims) if claims else None,
        "response_prestige_median": statistics.median(purses) if purses else None,
        "response_prestige_p25": (sorted(purses)[max(0, int(0.25 * len(purses)) - 1)] if purses else None),
        "response_prestige_p75": (sorted(purses)[min(len(purses) - 1, int(0.75 * len(purses)))] if purses else None),
        "response_prestige_share": {str(v): (sum(1 for p in purses if p == v) / len(purses) if purses else None)
                                    for v in (0, 1, 2, 3)},
        "response_prestige_share_4plus": (sum(1 for p in purses if p >= 4) / len(purses)) if purses else None,
        # Cross-fee probe: which fees these actual response purses could pay.
        "afford_at_fee": {str(f): (sum(1 for p in purses if p >= f) / len(purses)) if purses else None
                          for f in (0, 1, 2, 3)},
        "interpretation": "Offered means a legal contest action existed on the response turn "
                          "(within reach and purse). Not offered splits into purse-blocked and "
                          "position-blocked. Cross-fee rows are counterfactual affordability of "
                          "the observed purses, not replays under that fee.",
    }


def audit_suite(suite_dir):
    """Audit one evaluator variant directory; returns the summary."""
    suite_dir = Path(suite_dir)
    rules = engine.load_rules(str(suite_dir / "rules.json"))
    turn_rows, claim_rows = [], []
    games_ok = 0
    games_total = 0
    with (suite_dir / "games.jsonl").open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    with (suite_dir / "contest-audit-turns.jsonl").open("w", encoding="utf-8") as turns_out:
        for record in records:
            games_total += 1
            rows, claims, ok = audit_game(rules, record)
            games_ok += ok
            if not ok:
                raise RuntimeError(f"{record['game_id']}: audit re-run diverged from recorded game")
            for row in rows:
                turns_out.write(json.dumps(row, sort_keys=True) + "\n")
            turn_rows.extend(rows)
            claim_rows.extend(claims)
    summary = summarize(turn_rows, claim_rows, games_ok, games_total)
    summary["rules_hash"] = engine.rules_hash(rules)
    engine._atomic_write_json(str(suite_dir / "contest-audit-claims.json"), claim_rows)
    engine._atomic_write_json(str(suite_dir / "contest-audit.json"), summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, action="append",
                        help="Evaluator variant directory (contains rules.json and games.jsonl)")
    args = parser.parse_args(argv)
    out = {}
    for suite in args.suite:
        name = Path(suite).name
        out[name] = audit_suite(suite)
        print(json.dumps({name: out[name]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
