"""Scope checks for the live-suite contest audit.

The AR1.1 erratum: the first live-audit version counted claims and
cancellations from every game in ``games.jsonl``, including a game
stopped mid-run at the request cap, while dividing by finished games
only. These checks pin the corrected scope (finished games only,
matching the evaluator's ``claim_statistics_scope``) and the purse
reconstruction that tracks Prestige a defender earns on another
player's turn.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import live_contest_audit as lca

REPO = Path(__file__).resolve().parents[1]


def turn(turn_id, player, action, events, prestige_after=None):
    return {"turn_id": turn_id, "player": player, "action": action,
            "events": events, "prestige_after": prestige_after}


def game_record(game_id, status, winner=None, rounds=6):
    return {"game_id": game_id, "seed": 1, "status": status,
            "players": {"P0": "decisions", "P1": "decisions",
                        "P2": "decisions", "P3": "decisions"},
            "winner": winner, "outcome": "win" if winner else "draw",
            "total_turns": 6, "total_rounds": rounds,
            "result": {"winner": winner, "outcome": "win" if winner else "draw",
                       "total_rounds": rounds, "total_turns": 6,
                       "gate_assignments": {"P0": "P0", "P1": "P1", "P2": "P2", "P3": "P3"}}}


class LiveAuditScope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        variant = Path(self.tmp.name) / "base"
        variant.mkdir()
        shutil.copy(REPO / "rules_v08_succession.json", variant / "rules.json")

        finished = [
            turn(1, "P0", {"kind": "proclaim"},
                 [{"type": "claim_proclaimed", "player": "P0", "claim_id": 101}], 1),
            # P1 earns Prestige on P0's turn (defender wins the duel);
            # the purse tracker must credit P1 before P1's response.
            turn(2, "P0", {"kind": "duel", "target": "P1"},
                 [{"type": "duel", "attacker": "P0", "defender": "P1", "winner": "P1"},
                  {"type": "prestige_earned", "player": "P1", "amount": 2}], 0),
            turn(3, "P1", {"kind": "duel", "target": "P0", "spend_prestige": True},
                 [{"type": "prestige_spent", "player": "P1", "amount": 2},
                  {"type": "duel", "attacker": "P1", "defender": "P0", "winner": "P1"},
                  {"type": "claim_cancelled", "player": "P0", "claim_id": 101}], 0),
            turn(4, "P1", {"kind": "proclaim"},
                 [{"type": "claim_proclaimed", "player": "P1", "claim_id": 102}], 0),
            turn(5, "P2", {"kind": "move"},
                 [{"type": "claim_response", "player": "P2", "claim_id": 102}]),
            turn(6, "P3", {"kind": "move"},
                 [{"type": "claim_response", "player": "P3", "claim_id": 102}]),
        ]
        # The stopped game holds a canceled claim and a chosen contest;
        # none of it may leak into the finished-game statistics.
        incomplete = [
            turn(1, "P0", {"kind": "duel", "target": "P2"},
                 [{"type": "duel", "attacker": "P0", "defender": "P2", "winner": "P2"},
                  {"type": "prestige_earned", "player": "P2", "amount": 1}], 0),
            turn(2, "P0", {"kind": "proclaim"},
                 [{"type": "claim_proclaimed", "player": "P0", "claim_id": 201}], 1),
            turn(3, "P2", {"kind": "duel", "target": "P0"},
                 [{"type": "claim_cancelled", "player": "P0", "claim_id": 201}], 0),
        ]
        for game_id, events in (("g-fin", finished), ("g-inc", incomplete)):
            game_dir = variant / game_id
            game_dir.mkdir()
            with (game_dir / "events.jsonl").open("w") as handle:
                for record in events:
                    handle.write(json.dumps(record) + "\n")
        with (variant / "games.jsonl").open("w") as handle:
            handle.write(json.dumps(game_record("g-fin", "finished", "P1")) + "\n")
            handle.write(json.dumps(game_record("g-inc", "in_progress", None, 3)) + "\n")
        choices = [
            {"game_id": "g-fin", "turn_id": 1, "player": "P0", "pending_claim": None,
             "available_categories": ["proclaim"], "chosen_kind": "proclaim"},
            {"game_id": "g-fin", "turn_id": 3, "player": "P1",
             "pending_claim": {"claim_id": 101, "player": "P0"},
             "available_categories": ["counterclaim", "move"], "chosen_kind": "duel"},
            {"game_id": "g-fin", "turn_id": 5, "player": "P2",
             "pending_claim": {"claim_id": 102, "player": "P1"},
             "available_categories": ["move"], "chosen_kind": "move"},
            {"game_id": "g-inc", "turn_id": 3, "player": "P2",
             "pending_claim": {"claim_id": 201, "player": "P0"},
             "available_categories": ["counterclaim"], "chosen_kind": "duel"},
        ]
        with (variant / "choices.jsonl").open("w") as handle:
            for record in choices:
                handle.write(json.dumps(record) + "\n")
        self.variant = variant

    def tearDown(self):
        self.tmp.cleanup()

    def audit(self):
        return lca.audit_suite(self.variant, out_json=str(Path(self.tmp.name) / "a.json"))

    def test_claim_statistics_cover_finished_games_only(self):
        summary = self.audit()
        self.assertEqual(summary["games_total"], 2)
        self.assertEqual(summary["finished"], 1)
        self.assertEqual(summary["incomplete"], 1)
        # One claim canceled in the finished game; the incomplete game's
        # canceled claim (and its chosen contest) must not leak into the
        # finished-game statistics.
        self.assertEqual(summary["claims"], 2)
        self.assertEqual(summary["cancellations_per_game"], 1.0)
        # One contested claim, one crowned without a contest.
        self.assertEqual(summary["claims_challenged"], 0.5)
        self.assertEqual(summary["claim_statistics_scope"], "finished_games")

    def test_defender_earned_prestige_is_counted_before_the_response(self):
        summary = self.audit()
        # P1's 2 Prestige were earned on P0's turn (defender award).
        # The boost (fee 1 plus challenge cost 1) was affordable and
        # bought, so the affordable and bought shares must agree.
        self.assertEqual(summary["boost_affordable_share_of_contests"], 1.0)
        self.assertEqual(summary["boost_share_of_contests"], 1.0)
        # Two response turns in the finished game: P1 could afford the
        # boost, P2 (no Prestige, no contest offered) could not.
        self.assertEqual(summary["can_afford_boost_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
