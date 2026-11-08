#!/usr/bin/env python3
"""Legal contest-availability audit for LIVE Decisions suites.

``tools/contest_audit.py`` re-runs offline games to verify replays;
live games cannot be re-run because the model chose the actions. This
companion reads what the harness recorded and nothing else:

- ``choices.jsonl``: per-turn public categories (a ``counterclaim``
  category means a legal contest was OFFERED on that response turn);
- each game's ``events.jsonl``: the chosen action (kind, target,
  ``spend_prestige``), duel outcomes, claim events, and Prestige
  after each turn (so the purse BEFORE a response turn is the same
  player's previous recorded purse);
- ``games.jsonl``: outcomes.

It reports the same response-turn measures as the offline audit so
live and offline arms can be compared line by line. Written for the
autoresearch-ar1 live exercise; validated against the published V0.8
live probes (fee 2: zero contests offered; fee 1: 12 of 13 claims
challenged, 9 canceled).
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import engine


def audit_game(variant_dir, record, choices, rules):
    game_id = record["game_id"]
    game_dir = variant_dir / game_id
    fee = rules["succession"].get("contest_cost", 0)
    boost_price = fee + rules["succession"]["challenge_cost"]
    events = [json.loads(line) for line in (game_dir / "events.jsonl").open(encoding="utf-8") if line.strip()]
    choices_by_turn = {c["turn_id"]: c for c in choices if c["game_id"] == game_id}
    # Walk the event log itself: Prestige changes on any turn (a
    # defender wins a duel reward on the attacker's turn), so purses
    # must advance on every evented turn, whether or not a choices
    # row exists for it.
    purse = {pid: 0 for pid in ("P0", "P1", "P2", "P3")}
    rows = []

    def apply_turn_prestige(turn):
        for event in turn.get("events", []):
            if event["type"] == "prestige_earned":
                purse[event["player"]] += event["amount"]
            elif event["type"] == "prestige_spent":
                purse[event["player"]] -= event["amount"]

    for turn in sorted(events, key=lambda e: e["turn_id"]):
        choice = choices_by_turn.get(turn["turn_id"])
        pending = (choice or {}).get("pending_claim")
        if choice and pending and pending["player"] != choice["player"]:
            action = turn.get("action", {})
            duel_events = [e for e in turn.get("events", []) if e["type"] == "duel"]
            my_duel = next((e for e in duel_events if e["attacker"] == choice["player"]), None)
            chosen_contest = bool(action.get("kind") == "duel" and action.get("target") == pending["player"])
            rows.append({
                "game_id": game_id, "turn_id": turn["turn_id"], "responder": choice["player"],
                "claim_id": pending["claim_id"], "claimant": pending["player"],
                "responder_prestige_before": purse[choice["player"]],
                "contest_offered": "counterclaim" in choice["available_categories"],
                "can_afford_boost": purse[choice["player"]] >= boost_price,
                "chosen_contest": chosen_contest,
                "chosen_boost": bool(chosen_contest and action.get("spend_prestige")),
                "contest_won": bool(my_duel and my_duel["winner"] == choice["player"]) if chosen_contest else None,
                "claim_cancelled_this_turn": any(e["type"] == "claim_cancelled" for e in turn.get("events", [])),
            })
        apply_turn_prestige(turn)
    claims = []
    for turn in events:
        for event in turn.get("events", []):
            if event["type"] == "claim_proclaimed":
                claims.append({"game_id": game_id, "claim_id": event["claim_id"],
                               "claimant": event["player"], "responses": 0, "offered": 0,
                               "contests": 0, "canceled": False, "won": False})
            elif event["type"] == "claim_response" and claims:
                claims[-1]["responses"] += 1
            elif event["type"] == "claim_cancelled" and claims:
                claims[-1]["canceled"] = True
            elif event["type"] == "game_won" and claims and event.get("cause") == "acclamation":
                claims[-1]["won"] = True
    by_claim = {}
    for row in rows:
        entry = by_claim.setdefault(row["claim_id"], {"offered": 0, "contests": 0, "turns": 0})
        entry["turns"] += 1
        entry["offered"] += row["contest_offered"]
        entry["contests"] += row["chosen_contest"]
    for claim in claims:
        seen = by_claim.get(claim["claim_id"], {"offered": 0, "contests": 0, "turns": 0})
        claim["offered"] = seen["offered"]
        claim["contests"] = seen["contests"]
    return rows, claims


def summarize(rows, claims, games, rules):
    fee = rules["succession"].get("contest_cost", 0)
    boost_cost = rules["succession"]["challenge_cost"]
    response_turns = len(rows)
    purses = [r["responder_prestige_before"] for r in rows]

    def rate(predicate):
        return (sum(1 for r in rows if predicate(r)) / response_turns) if response_turns else None

    finished = [g for g in games if g["status"] == "finished"]
    draws = sum(1 for g in finished if g["winner"] is None)
    rounds = [g["result"]["total_rounds"] for g in finished]
    return {
        "provider": "live-decisions",
        "claim_statistics_scope": "finished_games",
        "games_total": len(games),
        "finished": len(finished),
        "incomplete": len(games) - len(finished),
        "draws": draws,
        "median_rounds": statistics.median(rounds) if rounds else None,
        "contest_fee": fee, "challenge_cost": boost_cost,
        "response_turns": response_turns,
        "claims": len(claims),
        "contest_offered_rate": rate(lambda r: r["contest_offered"]),
        "blocked_by_purse_share": rate(lambda r: not r["contest_offered"] and r["responder_prestige_before"] < fee),
        "blocked_by_position_share": rate(lambda r: not r["contest_offered"] and r["responder_prestige_before"] >= fee),
        "chosen_contest_rate": rate(lambda r: r["chosen_contest"]),
        "chosen_given_offered": (sum(1 for r in rows if r["chosen_contest"] and r["contest_offered"])
                                 / sum(1 for r in rows if r["contest_offered"]))
                                if any(r["contest_offered"] for r in rows) else None,
        "can_afford_boost_rate": rate(lambda r: r["can_afford_boost"]),
        "boost_share_of_contests": (sum(1 for r in rows if r["chosen_boost"]) / sum(1 for r in rows if r["chosen_contest"]))
                                   if any(r["chosen_contest"] for r in rows) else None,
        "boost_affordable_share_of_contests": (sum(1 for r in rows if r["can_afford_boost"])
                                               / sum(1 for r in rows if r["chosen_contest"]))
                                              if any(r["chosen_contest"] for r in rows) else None,
        "contest_win_rate_when_chosen": (sum(1 for r in rows if r["contest_won"])
                                         / sum(1 for r in rows if r["chosen_contest"]))
                                        if any(r["chosen_contest"] for r in rows) else None,
        "claims_with_contest_option": (sum(1 for c in claims if c["offered"] > 0) / len(claims)) if claims else None,
        "claims_challenged": (sum(1 for c in claims if c["contests"] > 0) / len(claims)) if claims else None,
        "claims_canceled": (sum(1 for c in claims if c["canceled"]) / len(claims)) if claims else None,
        "cancellations_per_game": (sum(1 for c in claims if c["canceled"]) / len(finished)) if finished else None,
        "claims_won_by_acclamation": (sum(1 for c in claims if c["won"]) / len(claims)) if claims else None,
        "claims_crowned_without_legal_contest": (sum(1 for c in claims if c["won"] and c["offered"] == 0) / len(claims)) if claims else None,
        "response_prestige_share": {str(v): (sum(1 for p in purses if p == v) / len(purses) if purses else None)
                                    for v in (0, 1, 2, 3)},
        "afford_at_fee": {str(f): (sum(1 for p in purses if p >= f) / len(purses)) if purses else None
                          for f in (0, 1, 2)},
        "interpretation": "Live Decisions games are recorded evidence, not replays. Offered means the "
                          "counterclaim category appeared in the responder's public legal categories. "
                          "Claim and cancellation statistics cover finished games only, matching the "
                          "evaluator's claim_statistics_scope; rows from a stopped incomplete game are "
                          "excluded (the AR1.1 erratum records why). A contested claim is a claim with "
                          "at least one chosen contest; boost affordability is a separate question "
                          "(responder Prestige at or above fee plus challenge cost).",
    }


def audit_suite(variant_dir, out_json=None):
    variant_dir = Path(variant_dir)
    rules = engine.load_rules(str(variant_dir / "rules.json"))
    games = [json.loads(line) for line in (variant_dir / "games.jsonl").open(encoding="utf-8") if line.strip()]
    choices = [json.loads(line) for line in (variant_dir / "choices.jsonl").open(encoding="utf-8") if line.strip()]
    finished_games = [g for g in games if g["status"] == "finished"]
    rows, claims = [], []
    for record in finished_games:
        game_rows, game_claims = audit_game(variant_dir, record, choices, rules)
        rows.extend(game_rows)
        claims.extend(game_claims)
    summary = summarize(rows, claims, games, rules)
    summary["rules_hash"] = engine.rules_hash(rules)
    target = Path(out_json) if out_json else variant_dir / "live-contest-audit.json"
    engine._atomic_write_json(str(target), summary)
    if out_json is None:
        engine._atomic_write_json(str(variant_dir / "live-contest-audit-claims.json"), claims)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, action="append",
                        help="Live evaluator variant directory (rules.json, games.jsonl, choices.jsonl)")
    parser.add_argument("--out", help="Optional output path (else written inside the suite)")
    args = parser.parse_args(argv)
    for suite in args.suite:
        print(json.dumps({Path(suite).name: audit_suite(suite, args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
