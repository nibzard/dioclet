# ABOUTME: Claim-deadline projection tests: the block must predict the exact
# ABOUTME: turn the engine ends a survived claim, from public data only.
"""Phase 6 claim deadline tests.

The claim block must agree with the engine on the turn a claim wins,
must count each rival's cancel chances from the turn schedule, and must
derive can_cancel_this_turn from the legal actions. Claims are proclaimed
at each of the four positions in a round, because the schedule and the
chance counts depend on the position.
"""

import copy
import json
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidate_actions  # noqa: E402
import engine  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")

PERISTYLE = [9, 6]
NEAR_PERISTYLE = [8, 6]


def _rules():
    return engine.load_rules(RULES_PATH)


def _ready_state(rules, seed=7):
    """A phase-2 game on turn 1 with every seat ready to proclaim."""
    state = engine.new_game(rules, seed, "claim-deadline",
                            dict.fromkeys(engine.IDS, "balanced"))
    state.update(turn_order=list(engine.IDS), round_start=0,
                 turn_index=0, active_player="P0")
    state["phase"] = 2
    for player in state["players"].values():
        player.update(pos=PERISTYLE[:], support=["army", "elites"],
                      prestige=5, equipment=[])
    state["current_roll"], state["current_dice"] = 6, [3, 3]
    return state


def _proclaim_at(rules, position, claim_round=1):
    """Proclaim on turn `position` of `claim_round`; return state and claimant."""
    state = _ready_state(rules)
    for _ in range((claim_round - 1) * 4 + position - 1):
        actor = state["active_player"]
        obs = engine.observe(state, actor)
        move = next(a for a in obs["legal_actions"] if a["kind"] == "move")
        engine.apply_action(state, actor, obs["turn_id"], move["action_id"])
    claimant = state["active_player"]
    # The filler moves carried earlier seats away from the Peristyle; the
    # proclaiming seat returns there before it acts.
    state["players"][claimant].update(pos=PERISTYLE[:], support=["army", "elites"])
    state["current_roll"], state["current_dice"] = 6, [3, 3]
    obs = engine.observe(state, claimant)
    proclaim = next(a for a in obs["legal_actions"] if a["kind"] == "proclaim")
    engine.apply_action(state, claimant, obs["turn_id"], proclaim["action_id"])
    return state, claimant


def _non_cancelling_action(obs):
    """A legal action that neither duels the claimant nor abandons the claim."""
    pending = obs.get("pending_claim")
    if pending and pending["player"] == obs["viewer"]:
        return next(a for a in obs["legal_actions"]
                    if a["kind"] == "maintain_claim")
    return next(a for a in obs["legal_actions"]
                if not (a["kind"] == "duel" and pending
                        and a["target"] == pending["player"]))


def _claim_block(rules, state, viewer=None):
    obs = engine.observe(state, viewer or state["active_player"])
    return candidate_actions.project_observation(obs, rules)["claim"]


class TestClaimDeadline(unittest.TestCase):
    def _drive_to_end(self, state, rules):
        """Play non-cancelling actions to the end; keep the deadline pinned."""
        obs = engine.observe(state, state["active_player"])
        deadline = candidate_actions.project_observation(obs, rules)["claim"][
            "wins_after_turn"]
        while not engine.is_finished(state):
            obs = engine.observe(state, state["active_player"])
            if obs.get("pending_claim"):
                block = candidate_actions.project_observation(obs, rules)["claim"]
                self.assertEqual(block["wins_after_turn"], deadline)
            action = _non_cancelling_action(obs)
            engine.apply_action(state, obs["viewer"], obs["turn_id"],
                                action["action_id"])
        return deadline

    def test_projection_omits_the_claim_block_without_a_pending_claim(self):
        rules = _rules()
        state = _ready_state(rules)
        self.assertIsNone(state["pending_claim"])
        obs = engine.observe(state, "P0")
        self.assertNotIn("claim", candidate_actions.project_observation(obs, rules))
        palace = engine.new_game(rules, 3, "claim-absent")
        obs = engine.observe(palace, palace["active_player"])
        self.assertNotIn("claim", candidate_actions.project_observation(obs, rules))

    def test_survived_claim_wins_on_the_predicted_turn_from_every_position(self):
        rules = _rules()
        for claim_round in (1, 2):
            for position in (1, 2, 3, 4):
                with self.subTest(claim_round=claim_round, position=position):
                    state, claimant = _proclaim_at(rules, position, claim_round)
                    deadline = self._drive_to_end(state, rules)
                    self.assertTrue(engine.is_finished(state))
                    self.assertEqual(state["end_reason"], "survived_window")
                    self.assertEqual(state["turn_id"], deadline)
                    self.assertEqual(state["winner"], claimant)

    def test_claim_at_the_first_seat_pins_the_whole_block(self):
        rules = _rules()
        window = rules["succession"]["claim_window_rounds"]
        state, claimant = _proclaim_at(rules, position=1)
        self.assertEqual(claimant, "P0")
        obs = engine.observe(state, state["active_player"])
        projection = candidate_actions.project_observation(obs, rules)
        self.assertEqual(projection["schema"], "v0102-succession-proj-4")
        block = projection["claim"]
        # The window closes after the last turn of round 1 + window.
        last_turn = 4 * (1 + window)
        self.assertEqual(block["claimant"], "P0")
        self.assertEqual(block["wins_after_turn"], last_turn)
        self.assertEqual([t["turn"] for t in block["remaining_turns"]],
                         list(range(obs["turn_id"], last_turn + 1)))
        self.assertEqual(block["remaining_turns"][0],
                         {"round": 1, "turn": obs["turn_id"],
                          "player": obs["active_player"]})
        self.assertEqual(block["remaining_turns"][-1]["turn"], last_turn)
        self.assertEqual(
            block["cancel_chances"],
            {pid: window + 1 for pid in ("P1", "P2", "P3")})
        # The viewer sits on the Peristyle, so a duel at the claimant is legal.
        self.assertTrue(block["can_cancel_this_turn"])
        # The rotation moves the first seat one place each round.
        by_round = {}
        for turn in block["remaining_turns"]:
            by_round.setdefault(turn["round"], []).append(turn["player"])
        self.assertEqual(by_round[2], ["P1", "P2", "P3", "P0"])

    def test_cancel_chances_count_each_rivals_turns_before_the_deadline(self):
        rules = _rules()
        for claim_round in (1, 2):
            for position in (1, 2, 3, 4):
                with self.subTest(claim_round=claim_round, position=position):
                    state, _claimant = _proclaim_at(rules, position, claim_round)
                    block = _claim_block(rules, state)
                    schedule = Counter(
                        t["player"] for t in block["remaining_turns"])
                    self.assertNotIn(block["claimant"], block["cancel_chances"])
                    expected = {pid: count for pid, count in schedule.items()
                                if pid != block["claimant"]}
                    self.assertEqual(block["cancel_chances"], expected)
                    self.assertEqual(
                        sum(block["cancel_chances"].values())
                        + schedule[block["claimant"]],
                        len(block["remaining_turns"]))
                    self.assertLessEqual(
                        max(block["cancel_chances"].values()),
                        rules["succession"]["claim_window_rounds"] + 1)

    def test_fixed_first_player_repeats_the_same_order(self):
        rules = _rules()
        rules["turns"]["rotate_first_player_each_round"] = False
        state, _claimant = _proclaim_at(rules, position=2)
        block = _claim_block(rules, state)
        by_round = {}
        for turn in block["remaining_turns"]:
            by_round.setdefault(turn["round"], []).append(turn["player"])
        full = [players for players in by_round.values() if len(players) == 4]
        self.assertGreaterEqual(len(full), rules["succession"]["claim_window_rounds"])
        for players in full:
            self.assertEqual(players, list(engine.IDS))

    def test_can_cancel_this_turn_requires_a_reachable_duel_at_the_claimant(self):
        rules = _rules()
        fee = rules["succession"]["contest_fee"]

        def state_with(viewer_pos, viewer_prestige):
            state = _ready_state(rules)
            state["active_player"] = "P1"
            state["turn_index"] = 1
            state["players"]["P0"].update(pos=PERISTYLE[:])
            state["pending_claim"] = {"player": "P0", "claim_id": state["turn_id"],
                                      "responded": [], "round": state["round"]}
            state["players"]["P1"].update(pos=list(viewer_pos),
                                          prestige=viewer_prestige)
            return state

        near = state_with(NEAR_PERISTYLE, fee)
        obs = engine.observe(near, "P1")
        self.assertTrue(any(a["kind"] == "duel" and a["target"] == "P0"
                            for a in obs["legal_actions"]))
        self.assertTrue(_claim_block(rules, near, viewer="P1")
                        ["can_cancel_this_turn"])
        broke = state_with(NEAR_PERISTYLE, fee - 1)
        obs = engine.observe(broke, "P1")
        self.assertFalse(any(a["kind"] == "duel" and a["target"] == "P0"
                             for a in obs["legal_actions"]))
        self.assertFalse(_claim_block(rules, broke, viewer="P1")
                         ["can_cancel_this_turn"])
        far = state_with(rules["succession"]["map"]["gates"]["north"], fee)
        obs = engine.observe(far, "P1")
        self.assertFalse(any(a["kind"] == "duel" and a["target"] == "P0"
                             for a in obs["legal_actions"]))
        self.assertFalse(_claim_block(rules, far, viewer="P1")
                         ["can_cancel_this_turn"])
        own = _ready_state(rules)
        own["players"]["P0"].update(pos=PERISTYLE[:])
        own["pending_claim"] = {"player": "P0", "claim_id": own["turn_id"],
                                "responded": [], "round": own["round"]}
        self.assertTrue(any(a["kind"] == "maintain_claim"
                            for a in engine.observe(own, "P0")["legal_actions"]))
        self.assertFalse(_claim_block(rules, own, viewer="P0")
                         ["can_cancel_this_turn"])

    def test_zero_window_keeps_the_block_without_a_deadline(self):
        rules = _rules()
        rules["succession"]["claim_window_rounds"] = 0
        state, _claimant = _proclaim_at(rules, position=1)
        block = _claim_block(rules, state)
        self.assertIsNone(block["wins_after_turn"])
        self.assertEqual(block["remaining_turns"], [])
        self.assertEqual(block["cancel_chances"], {})
        self.assertIn("can_cancel_this_turn", block)
        while not engine.is_finished(state):
            obs = engine.observe(state, state["active_player"])
            action = _non_cancelling_action(obs)
            engine.apply_action(state, obs["viewer"], obs["turn_id"],
                                action["action_id"])
        self.assertEqual(state["end_reason"], "acclamation")

    def test_one_round_window_still_matches_the_engine(self):
        rules = _rules()
        rules["succession"]["claim_window_rounds"] = 1
        state, _claimant = _proclaim_at(rules, position=3)
        deadline = self._drive_to_end(state, rules)
        self.assertEqual(state["end_reason"], "survived_window")
        self.assertEqual(state["turn_id"], deadline)
        self.assertEqual(deadline, 8)

    def test_claim_past_the_last_round_never_wins(self):
        rules = _rules()
        max_round = rules["succession"]["max_rounds"]
        state = _ready_state(rules)
        state["active_player"] = "P1"
        state["turn_index"] = 1
        state["round"] = max_round
        state["players"]["P0"].update(pos=PERISTYLE[:])
        state["pending_claim"] = {"player": "P0", "claim_id": state["turn_id"],
                                  "responded": [], "round": state["round"]}
        block = _claim_block(rules, state)
        self.assertIsNone(block["wins_after_turn"])
        self.assertEqual(sorted({t["round"] for t in block["remaining_turns"]}),
                         [max_round])
        while not engine.is_finished(state):
            obs = engine.observe(state, state["active_player"])
            action = _non_cancelling_action(obs)
            engine.apply_action(state, obs["viewer"], obs["turn_id"],
                                action["action_id"])
        self.assertEqual(state["end_reason"], "succession_timeout")

    def test_the_block_reads_only_public_fields(self):
        rules = _rules()
        state, _claimant = _proclaim_at(rules, position=1)
        obs = engine.observe(state, state["active_player"])
        obs["rng"] = "FUTURE_SENTINEL"
        obs["district_equipment"] = {"A": "SECRET_ITEM_SENTINEL"}
        obs["pending_claim"]["claim_id"] = "SECRET_CLAIM_SENTINEL"
        obs["pending_claim"]["responded"] = ["RESPONSE_SENTINEL"]
        for action in obs["legal_actions"]:
            action["item"] = "ACTION_ITEM_SENTINEL"
        projection = candidate_actions.project_observation(obs, rules)
        block = json.dumps(projection["claim"])
        for sentinel in ("FUTURE_SENTINEL", "SECRET_ITEM_SENTINEL",
                         "SECRET_CLAIM_SENTINEL", "RESPONSE_SENTINEL",
                         "ACTION_ITEM_SENTINEL"):
            self.assertNotIn(sentinel, block)
        self.assertNotIn("FUTURE_SENTINEL", json.dumps(projection))
        self.assertEqual(set(projection["claim"]), {
            "claimant", "wins_after_turn", "remaining_turns",
            "cancel_chances", "can_cancel_this_turn"})


if __name__ == "__main__":
    unittest.main()
