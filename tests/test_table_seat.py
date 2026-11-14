"""The seat view's claim lines (tools/table_seat.py)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools")]

import engine  # noqa: E402
import table_seat  # noqa: E402

RULES = engine.load_rules(os.path.join(ROOT, "rules_v0102_bigboard.json"))
GAME = os.path.join(ROOT, "runs", "haiku-table-v0101", "game1")


class ClaimLines(unittest.TestCase):
    def test_palace_phase_names_the_checkpoint_claim(self):
        obs = {"phase": 1, "progress": {"first_challenger": None,
                                        "players_with_full_equipment": []}}
        (line,) = table_seat.claim_lines(obs, RULES)
        self.assertIn("palace checkpoint claim: nobody yet", line)
        self.assertNotIn("standing claim", line)

    def test_succession_phase_hides_the_palace_claim(self):
        # Two seats read "first challenger: P2" beside "pending claim:
        # None" as a standing claim by P2 (runs/haiku-table-v0101).
        obs = {"phase": 2, "pending_claim": None,
               "progress": {"first_challenger": "P2"}}
        text = "\n".join(table_seat.claim_lines(obs, RULES))
        self.assertIn("standing claim: none", text)
        self.assertNotIn("P2", text)
        self.assertNotIn("first challenger", text)

    def test_window_end_matches_the_recorded_win(self):
        # In the 0.10.1 table game, claim 110 was proclaimed in round 11
        # and won at the end of round 12.
        with open(os.path.join(GAME, "state.json")) as fh:
            state = json.load(fh)
        pending = state["pending_claim"]
        self.assertEqual((pending["claim_id"], pending["round"]), (110, 11))
        self.assertEqual((state["end_reason"], state["round"]), ("survived_window", 13))
        obs = {"phase": 2, "pending_claim": pending, "progress": {}}
        (line,) = table_seat.claim_lines(obs, state["rules"])
        self.assertIn("standing claim: P3 (proclaimed in round 11)", line)
        self.assertIn("wins at the end of round 12", line)
        self.assertIn("fee 1 Prestige", line)


class AsciiMap(unittest.TestCase):
    def test_north_gate_is_on_the_top_row(self):
        # The printed boards put y 0 (the Golden Gate, north) at the top.
        state = engine.new_game(RULES, 1, "g1", {p: "random" for p in ("P0", "P1", "P2", "P3")})
        obs = engine.observe(state, state["active_player"])
        rows = table_seat.ascii_map(obs).splitlines()
        self.assertTrue(rows[0].startswith(" 0 "))
        self.assertTrue(rows[12].startswith("12 "))
        north = obs["board"]["gates"]["P0"]
        self.assertEqual(tuple(north), (6, 0))
        self.assertNotEqual(rows[0][3 + north[0]], ".")

if __name__ == "__main__":
    unittest.main()
