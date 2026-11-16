# ABOUTME: Exact-odds tests for the candidate-action math: duel, contest,
# ABOUTME: and threshold probabilities over the six-by-six die grid.
"""Offline tests for the exact odds in candidate_actions.

The pure probability helpers are tested against known values, the claim
wording against the active rules, and duel_odds against the engine over
every equipment pairing and every die pair.
"""

import copy
import itertools
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidate_actions  # noqa: E402
import engine  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")


def _rules():
    return engine.load_rules(RULES_PATH)


class TestExactOdds(unittest.TestCase):
    def test_duel_probability_equal_bonus_tie_attacker(self):
        self.assertAlmostEqual(
            candidate_actions.duel_win_probability(0, 0, True), 21 / 36)

    def test_duel_probability_equal_bonus_tie_defender(self):
        self.assertAlmostEqual(
            candidate_actions.duel_win_probability(0, 0, False), 15 / 36)

    def test_contest_offset(self):
        # +2 vs +0, strict win: count a+2 > b over the 6x6 grid = 26.
        self.assertAlmostEqual(
            candidate_actions.contest_probability(2, 0, False), 26 / 36)
        # 0 vs +2, ties win: a >= b+2 over the grid = 10.
        self.assertAlmostEqual(
            candidate_actions.contest_probability(0, 2, True), 10 / 36)

    def test_threshold(self):
        self.assertAlmostEqual(candidate_actions.threshold_probability(4), 0.5)
        self.assertAlmostEqual(candidate_actions.threshold_probability(5), 1 / 3)
        self.assertAlmostEqual(candidate_actions.threshold_probability(1), 1.0)


class TestClaimRuleText(unittest.TestCase):
    def test_window_text_carries_the_rules_value(self):
        rules = _rules()
        window = rules["succession"]["claim_window_rounds"]
        self.assertEqual(
            candidate_actions.claim_rule_text(rules),
            f"A proclaimed claim wins after it survives {window} full "
            "round(s) uncancelled; rivals must cancel it inside the "
            "window.")

    def test_zero_window_text_carries_the_response_rule(self):
        rules = _rules()
        rules["succession"]["claim_window_rounds"] = 0
        self.assertEqual(
            candidate_actions.claim_rule_text(rules),
            "Each distinct rival completes one response turn; the claim "
            "wins when the last response ends without cancelling it.")

    def test_rule_summary_and_projection_reuse_one_wording(self):
        rules = _rules()
        text = candidate_actions.claim_rule_text(rules)
        self.assertEqual(
            candidate_actions.rule_summary(rules)["claim_response_rule"], text)
        state = engine.new_game(rules, 1, "claim-text")
        obs = engine.observe(state, "P0")
        projection = candidate_actions.project_observation(obs, rules)
        self.assertIn(text, projection["objective"])


class TestDuelOdds(unittest.TestCase):
    """Known values for the engine-mirroring duel odds."""

    def _odds(self, attack_items, defense_items, pending_player=None,
              rules=None):
        rules = rules or _rules()
        pending = ({"player": pending_player, "claim_id": 1,
                    "responded": [], "round": 0} if pending_player else None)
        return candidate_actions.duel_odds(
            {"id": "P1", "equipment": list(attack_items)},
            {"id": "P0", "equipment": list(defense_items)},
            rules, pending)

    def test_plain_duel_tie_rule_sends_ties_to_the_attacker(self):
        odds = self._odds([], [])
        self.assertEqual(odds["probability"], 21 / 36)
        self.assertEqual(
            odds["parts"],
            {"attack_bonus": 0, "defense_bonus": 0, "attacker_pugio": False,
             "defender_pugio": False, "tie_rule": "attacker"})

    def test_attack_meets_defense_and_a_lone_defender_pugio_wins_ties(self):
        odds = self._odds(["gladius"], ["scutum", "pugio"])
        self.assertEqual(odds["probability"], 15 / 36)
        self.assertEqual(odds["parts"]["attack_bonus"], 1)
        self.assertEqual(odds["parts"]["defense_bonus"], 1)
        self.assertTrue(odds["parts"]["defender_pugio"])
        self.assertFalse(odds["parts"]["attacker_pugio"])

    def test_offsets_over_the_grid(self):
        # +1 offset, attacker wins ties: 21 strict wins + 5 score ties.
        self.assertEqual(self._odds(["gladius"], [])["probability"], 26 / 36)
        # -1 offset, attacker wins ties: 10 strict wins + 5 score ties.
        self.assertEqual(self._odds([], ["scutum"])["probability"], 15 / 36)

    def test_pilum_counts_only_against_the_pending_claimant(self):
        held_back = self._odds(["pilum"], ["pugio"])
        self.assertEqual(held_back["probability"], 15 / 36)
        vs_claimant = self._odds(["pilum"], ["pugio"], pending_player="P0")
        self.assertEqual(vs_claimant["probability"], 21 / 36)
        other_claim = self._odds(["pilum"], ["pugio"], pending_player="P2")
        self.assertEqual(other_claim["probability"], 15 / 36)

    def test_best_attack_modifier_applies_never_a_sum(self):
        rules = _rules()
        rules["treasures"]["abilities"]["spear"] = {
            "type": "attack_bonus", "value": 2}
        odds = self._odds(["gladius", "spear"], ["scutum"], rules=rules)
        self.assertEqual(odds["parts"]["attack_bonus"], 2)
        # Net +1 with attacker ties: 26/36; a forbidden sum would be +2
        # and 31/36.
        self.assertEqual(odds["probability"], 26 / 36)

    def test_two_pugios_fall_back_to_the_tie_rule(self):
        both = self._odds(["pugio"], ["pugio"])
        self.assertTrue(both["parts"]["attacker_pugio"])
        self.assertTrue(both["parts"]["defender_pugio"])
        self.assertEqual(both["probability"], 21 / 36)
        rules = _rules()
        rules["duels"]["tie_winner"] = "defender"
        self.assertEqual(
            self._odds(["pugio"], ["pugio"], rules=rules)["probability"],
            15 / 36)


class TestDuelOddsMatchesEngine(unittest.TestCase):
    """Every equipment pairing on both sides, every die pair, through real
    engine duels: duel_odds must equal the engine exactly."""

    PERISTYLE = [9, 6]
    NEAR_PERISTYLE = [8, 6]

    def _state(self, rules):
        state = engine.new_game(rules, 7, "duel-odds",
                                dict.fromkeys(engine.IDS, "balanced"))
        state.update(turn_order=list(engine.IDS), round_start=0,
                     turn_index=0, active_player="P1")
        state["phase"] = 2
        state["players"]["P0"].update(pos=self.PERISTYLE[:],
                                      support=["army", "elites"])
        state["players"]["P1"].update(pos=self.NEAR_PERISTYLE[:], prestige=5)
        state["current_roll"], state["current_dice"] = 6, [3, 3]
        return state

    @staticmethod
    def _snapshot(state):
        players = {pid: (p["pos"][:], p["prestige"], dict(p["abilities_used"]),
                         dict(p["stats"]), p["turns"], list(p["equipment"]),
                         list(p["support"]))
                   for pid, p in state["players"].items()}
        scalars = (state["turn_id"], state["turn_index"], state["round"],
                   state["round_start"], state["event_seq"],
                   state["current_roll"], list(state["current_dice"]))
        return players, scalars, copy.deepcopy(state["pending_claim"]), \
            len(state["events"])

    @staticmethod
    def _restore(state, snapshot):
        players, scalars, pending, n_events = snapshot
        for pid, snap in players.items():
            player = state["players"][pid]
            player.update(pos=snap[0][:], prestige=snap[1],
                          abilities_used=dict(snap[2]), stats=dict(snap[3]),
                          turns=snap[4], equipment=list(snap[5]),
                          support=list(snap[6]))
        (state["turn_id"], state["turn_index"], state["round"],
         state["round_start"], state["event_seq"], state["current_roll"],
         state["current_dice"]) = scalars
        state["current_dice"] = list(scalars[6])
        state["pending_claim"] = copy.deepcopy(pending)
        del state["events"][n_events:]

    def _engine_wins(self, state, snapshot, die, duel, attack_items,
                     defense_items):
        won = 0
        bonuses = None
        for attack_roll in range(1, 7):
            for defense_roll in range(1, 7):
                self._restore(state, snapshot)
                state["players"]["P1"]["equipment"] = list(attack_items)
                state["players"]["P0"]["equipment"] = list(defense_items)
                die.side_effect = [attack_roll, defense_roll, 3, 3]
                engine.apply_action(state, "P1", state["turn_id"],
                                    duel["action_id"])
                row = state["events"][-1]
                event = next(e for e in row["events"] if e["type"] == "duel")
                if bonuses is None:
                    bonuses = (event["attacker_bonus"],
                               event["defender_bonus"])
                won += event["winner"] == "P1"
        return won, bonuses

    def test_every_pairing_and_die_pair_matches_the_engine(self):
        rules = engine.load_rules(RULES_PATH)
        items = rules["treasures"]["items"]
        subsets = [list(combo) for size in range(len(items) + 1)
                   for combo in itertools.combinations(items, size)]
        self.assertEqual(len(subsets), 2 ** len(items))
        checked = 0
        for pending_player in (None, "P0"):
            state = self._state(rules)
            state["pending_claim"] = (
                {"player": pending_player, "claim_id": state["turn_id"],
                 "responded": [], "round": state["round"]}
                if pending_player else None)
            duel = next(a for a in engine.legal_actions(state)
                        if a["kind"] == "duel" and a["target"] == "P0")
            # The captured action must still be what the engine offers now.
            fresh = next(a for a in engine.legal_actions(state)
                         if a["kind"] == "duel" and a["target"] == "P0")
            self.assertEqual(duel, fresh)
            snapshot = self._snapshot(state)
            legal_patcher = patch.object(engine, "legal_actions",
                                         return_value=[duel])
            die_patcher = patch.object(engine, "_die")
            legal_patcher.start()
            die = die_patcher.start()
            try:
                for attack_items in subsets:
                    for defense_items in subsets:
                        # The odds read the variant's pristine pending: the
                        # engine restores it before every duel, while the
                        # live state may already show it cancelled.
                        odds = candidate_actions.duel_odds(
                            {"id": "P1", "equipment": list(attack_items)},
                            {"id": "P0", "equipment": list(defense_items)},
                            rules, snapshot[2])
                        won, bonuses = self._engine_wins(
                            state, snapshot, die, duel, attack_items,
                            defense_items)
                        self.assertEqual(
                            won, odds["probability"] * 36,
                            f"attacker {attack_items} vs defender "
                            f"{defense_items}, pending {pending_player}")
                        self.assertEqual(
                            bonuses,
                            (odds["parts"]["attack_bonus"],
                             odds["parts"]["defense_bonus"]))
                        checked += 1
            finally:
                legal_patcher.stop()
                die_patcher.stop()
        self.assertEqual(checked, 2 * 2 ** len(items) * 2 ** len(items))


if __name__ == "__main__":
    unittest.main()
