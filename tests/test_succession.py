# ABOUTME: Rules, visibility, replay, and strategy checks for the
# ABOUTME: succession game that lives inside engine.py.
"""Rules, visibility, replay, and strategy checks for the succession game."""
import copy
import json
import os
import random
import tempfile
import unittest
from unittest.mock import patch

import engine
import policies
import report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")
PERISTYLE = [9, 6]
NEAR_PERISTYLE = [8, 6]


def rules():
    return engine.load_rules(RULES_PATH)


def game(value=None):
    state = engine.new_game(value or rules(), 2026, "succession-test", dict.fromkeys(engine.IDS, "balanced"))
    state.update(turn_order=list(engine.IDS), round_start=0, turn_index=0, active_player="P0")
    state["current_roll"], state["current_dice"] = 6, [3, 3]
    return state


def take(state, kind, **fields):
    actions = engine.legal_actions(state)
    action = next(a for a in actions if a["kind"] == kind and all(a.get(k) == v for k, v in fields.items()))
    return engine.apply_action(state, state["active_player"], state["turn_id"], action["action_id"])


def active(state, pid):
    state["turn_index"] = engine.current_order(state).index(pid)
    state["active_player"] = pid
    state["current_roll"], state["current_dice"] = 6, [3, 3]


def pending_game():
    """A standing claim under a zero-round window, so three responses
    crown the claimant by acclamation (the V0.8 court the claim-window
    rule replaced)."""
    state = game()
    state["phase"] = 2
    state["rules"]["succession"]["claim_window_rounds"] = 0
    state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"])
    take(state, "proclaim")
    return state


def standing_claim_game():
    """A standing claim under the printed claim window, with P1
    funded for a contest duel."""
    state = game()
    state["phase"] = 2
    state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"])
    state["players"]["P1"].update(prestige=1)
    take(state, "proclaim")
    return state


def outlast(state, proclaimed):
    """Play the rounds between the proclaim and round R+window: rivals move,
    the claimant maintains."""
    window = state["rules"]["succession"]["claim_window_rounds"]
    guard = 0
    while (state["status"] == "in_progress" and state["round"] < proclaimed + window
           and guard < 40):
        pid = state["active_player"]
        take(state, "maintain_claim" if pid == "P0" else "move")
        guard += 1


class TestClaimWindow(unittest.TestCase):
    def test_claim_wins_after_window_full_rounds(self):
        # A claim proclaimed in round R wins when the last turn of
        # round R + window ends: the state round counter reads R + window + 1,
        # because it advances at each round wrap.
        state = standing_claim_game()
        window = state["rules"]["succession"]["claim_window_rounds"]
        proclaimed = state["pending_claim"]["round"]
        outlast(state, proclaimed)
        guard = 0
        while state["status"] == "in_progress" and guard < 40:
            pid = state["active_player"]
            take(state, "maintain_claim" if pid == "P0" else "move")
            guard += 1
        self.assertEqual(state["end_reason"], "survived_window")
        self.assertEqual(state["winner"], "P0")
        self.assertEqual(state["round"], proclaimed + window + 1)
        engine.check_invariants(state)

    def test_claim_can_still_die_in_the_last_window_round(self):
        # The window counts full rounds after the proclaim round, so a
        # standing claim still lives through round R + window and a
        # rival can cancel it there.
        state = standing_claim_game()
        window = state["rules"]["succession"]["claim_window_rounds"]
        proclaimed = state["pending_claim"]["round"]
        outlast(state, proclaimed)
        guard = 0
        while (state["status"] == "in_progress"
               and not (state["round"] == proclaimed + window
                        and state["active_player"] == "P1") and guard < 40):
            pid = state["active_player"]
            take(state, "maintain_claim" if pid == "P0" else "move")
            guard += 1
        self.assertEqual((state["round"], state["active_player"]),
                         (proclaimed + window, "P1"))
        state["players"]["P1"]["pos"] = NEAR_PERISTYLE[:]
        with patch.object(engine, "_die", side_effect=[6, 1, 3, 3]):
            record = take(state, "duel", target="P0", spend_prestige=False)
        self.assertEqual(record["round"], proclaimed + window)
        self.assertIsNone(state["pending_claim"])
        self.assertIsNone(state["winner"])
        self.assertEqual(state["status"], "in_progress")
        engine.check_invariants(state)

    def test_a_claim_proclaimed_after_round_24_still_wins(self):
        # The succession phase has no round limit: the game runs past
        # round 24, and a claim proclaimed there is crowned at the end
        # of its window.
        state = game()
        state["phase"] = 2
        state["round"] = 30
        window = state["rules"]["succession"]["claim_window_rounds"]
        active(state, "P3")
        take(state, "move")
        self.assertEqual((state["status"], state["round"]), ("in_progress", 31))
        state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"])
        active(state, "P0")
        take(state, "proclaim")
        guard = 0
        while state["status"] == "in_progress" and guard < 40:
            pid = state["active_player"]
            take(state, "maintain_claim" if pid == "P0" else "move")
            guard += 1
        self.assertEqual(state["end_reason"], "survived_window")
        self.assertEqual(state["winner"], "P0")
        self.assertEqual(state["round"], 31 + window + 1)
        engine.check_invariants(state)


class TestSuccessionRules(unittest.TestCase):
    def test_invalid_succession_values_rejected(self):
        for field, value in (("support_cost", 0), ("contest_fee", -1),
                             ("factions_to_proclaim", 4), ("claim_window_rounds", 7),
                             ("proclaim_cost", "1")):
            candidate = rules()
            candidate["succession"][field] = value
            with self.subTest(field=field), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)

    def test_misspelled_experiment_knob_is_rejected(self):
        candidate = rules()
        candidate["succession"]["contset_cost"] = 1
        with self.assertRaisesRegex(engine.EngineError, "unknown succession keys"):
            engine.validate_rules(candidate)
        candidate = rules()
        del candidate["treasures"]
        with self.assertRaisesRegex(engine.EngineError, "missing top-level keys"):
            engine.validate_rules(candidate)

    def test_succession_cannot_restore_the_eight_block_map(self):
        candidate = rules()
        # Carve an extra street through the two middle blocks: the
        # six-block contract must refuse an eight-block layout.
        board_map = candidate["palace"]["map"]
        carved = {(9, y) for y in range(1, 12)}
        board_map["blocked"] = [cell for cell in board_map["blocked"]
                                if tuple(cell) not in carved]
        with self.assertRaisesRegex(engine.EngineError, "six intact blocks"):
            engine.validate_rules(candidate)

    def test_random_gates_use_an_independent_replayable_stream(self):
        a = engine.new_game(rules(), 2026, "a")
        b = engine.new_game(rules(), 2026, "b")
        c = engine.new_game(rules(), 2027, "c")
        self.assertEqual(a["gate_assignments"], b["gate_assignments"])
        self.assertEqual(sorted(a["gate_assignments"].values()), list(engine.IDS))
        for field in ("turn_order", "district_equipment", "current_dice"):
            self.assertEqual(a[field], b[field], field)
        for stream in ("order", "equipment", "movement", "combat"):
            self.assertEqual(a["rng"][stream], b["rng"][stream], stream)
        self.assertNotEqual(a["rng"]["gates"], c["rng"]["gates"])

    def test_transition_keeps_equipment_and_moves_to_gates(self):
        value = rules()
        value["palace"]["max_rounds"] = 1
        state = game(value)
        state["players"]["P0"].update(equipment=value["treasures"]["items"][:2], pos=[3, 0])
        active(state, "P3")
        record = take(state, "move")
        self.assertEqual(state["phase"], 2)
        self.assertEqual(state["players"]["P0"]["equipment"], value["treasures"]["items"][:2])
        for pid, player in state["players"].items():
            self.assertEqual(player["pos"], engine._gate_cell(state, player))
        self.assertTrue(state["palace_timeout"])
        self.assertFalse(any(ev["type"] == "auto_equipment_granted" for ev in record["events"]))
        engine.check_invariants(state)

    def test_uniform_support_cost_and_no_repeat(self):
        state = game()
        state["phase"] = 2
        state["players"]["P0"].update(pos=[15, 12], prestige=1)
        take(state, "gain_support", faction="elites")
        player = state["players"]["P0"]
        self.assertEqual((player["prestige"], player["support"]), (0, ["elites"]))
        active(state, "P0")
        player["prestige"] = 3
        self.assertFalse(any(a["kind"] == "gain_support" and a["faction"] == "elites" for a in engine.legal_actions(state)))
        self.assertEqual(player["stats"]["support_gained"], 1)

    def test_support_and_collection_are_distinct_actions(self):
        state = game()
        state["players"]["P0"].update(pos=[3, 0], prestige=1)
        self.assertTrue(any(a["kind"] == "explore" and a["destination"] == [3, 0]
                            for a in engine.legal_actions(state)))
        self.assertFalse(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))
        state["phase"] = 2
        state["players"]["P0"]["pos"] = [15, 12]
        self.assertFalse(any(a["kind"] == "explore" for a in engine.legal_actions(state)))
        self.assertTrue(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))
        state["players"]["P0"]["prestige"] = 0
        self.assertFalse(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))

    def test_public_observation_does_not_leak_hidden_mapping(self):
        state = game()
        state["district_equipment"]["A"] = "PRIVATE-SENTINEL"
        obs = engine.observe(state, "P0")
        self.assertNotIn("PRIVATE-SENTINEL", json.dumps(obs))
        self.assertNotIn("rng", obs)
        self.assertNotIn("district_equipment", obs)
        self.assertTrue(all("item" not in a for a in obs["legal_actions"]))
        self.assertNotIn("seals", obs["players"]["P0"])
        self.assertNotIn("hits", obs["players"]["P0"])

    def test_claim_requires_succession_support_and_crossing(self):
        state = game()
        me = state["players"]["P0"]
        me.update(pos=PERISTYLE[:], support=["army", "elites"])
        self.assertFalse(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))
        state["phase"] = 2
        self.assertTrue(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))
        me["support"] = ["army"]
        self.assertFalse(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))
        me["support"] = ["army", "elites"]
        me["pos"] = [6, 6]  # one circle short of the Peristyle
        proclaims = [a for a in engine.legal_actions(state) if a["kind"] == "proclaim"]
        self.assertTrue(proclaims)  # legal only by first walking to the crossing
        self.assertTrue(all(a["destination"] == PERISTYLE for a in proclaims))

    def test_claim_needs_all_three_distinct_responses(self):
        state = pending_game()
        for pid in ("P1", "P2", "P3"):
            self.assertEqual(state["active_player"], pid)
            take(state, "move")
            if pid != "P3":
                self.assertEqual(state["status"], "in_progress")
        self.assertEqual(state["winner"], "P0")
        self.assertEqual(state["pending_claim"]["responded"], ["P1", "P2", "P3"])
        self.assertEqual(state["end_reason"], "acclamation")
        engine.check_invariants(state)

    def test_round_rotation_does_not_omit_a_response(self):
        state = game()
        state["phase"] = 2
        state["rules"]["succession"]["claim_window_rounds"] = 0
        active(state, "P3")
        state["players"]["P3"].update(pos=PERISTYLE[:], support=["army", "elites"])
        take(state, "proclaim")
        self.assertEqual(state["active_player"], "P1")
        take(state, "move")
        take(state, "move")
        self.assertEqual(state["active_player"], "P3")
        take(state, "maintain_claim")
        self.assertEqual(state["status"], "in_progress")
        self.assertEqual(state["active_player"], "P0")
        take(state, "move")
        self.assertEqual(state["winner"], "P3")

    def test_repeated_responder_is_not_counted_twice(self):
        state = pending_game()
        state["pending_claim"]["responded"] = ["P1"]
        take(state, "move")
        self.assertEqual(state["pending_claim"]["responded"], ["P1"])
        self.assertEqual(state["players"]["P1"]["stats"]["response_turns"], 0)

    def test_successful_contest_cancels_and_displaces(self):
        state = pending_game()
        state["players"]["P1"].update(pos=NEAR_PERISTYLE[:], prestige=1)
        with patch.object(engine, "_die", side_effect=[6, 1, 3, 3]):
            take(state, "duel", target="P0", spend_prestige=False)
        self.assertIsNone(state["pending_claim"])
        self.assertEqual(state["players"]["P0"]["pos"],
                         engine._gate_cell(state, state["players"]["P0"]))
        self.assertEqual(state["players"]["P0"]["support"], ["army", "elites"])
        self.assertEqual(state["players"]["P1"]["stats"]["claims_cancelled_by"], 1)

    def test_contest_fee_cannot_be_bypassed(self):
        state = pending_game()
        state["players"]["P1"].update(pos=NEAR_PERISTYLE[:])
        self.assertFalse(any(a["kind"] == "duel" and a["target"] == "P0" for a in engine.legal_actions(state)))
        state["players"]["P1"]["prestige"] = 1
        contests = [a for a in engine.legal_actions(state) if a["kind"] == "duel" and a["target"] == "P0"]
        self.assertTrue(contests)
        self.assertTrue(all(a["contest_cost"] == 1 and not a["spend_prestige"] for a in contests))

    def test_failed_challenge_still_pays_fee_and_shame(self):
        state = pending_game()
        state["players"]["P1"].update(pos=NEAR_PERISTYLE[:], prestige=3)
        state["players"]["P0"]["equipment"] = state["rules"]["treasures"]["items"][:]
        with patch.object(engine, "_die", side_effect=[1, 6, 3, 3]):
            record = take(state, "duel", target="P0", spend_prestige=False)
        self.assertEqual(state["players"]["P1"]["prestige"], 1)  # contest fee plus shame
        self.assertEqual(state["players"]["P1"]["stats"]["contest_prestige_spent"], 1)
        self.assertEqual(state["pending_claim"]["responded"], ["P1"])
        self.assertEqual(sum(e["amount"] for e in record["events"] if e["type"] == "prestige_spent"), 2)

    def test_claimant_leaving_cancels_claim(self):
        state = pending_game()
        active(state, "P0")
        take(state, "move")
        self.assertIsNone(state["pending_claim"])
        self.assertEqual(state["players"]["P0"]["stats"]["claims_cancelled"], 1)

    def test_stale_and_illegal_actions_do_not_mutate_state(self):
        state = game()
        before = copy.deepcopy(state)
        with self.assertRaises(engine.EngineError):
            engine.apply_action(state, "P0", state["turn_id"] - 1, "a0001")
        with self.assertRaises(engine.EngineError):
            engine.apply_action(state, "P0", state["turn_id"], "invalid")
        self.assertEqual(state, before)

    def test_uncapped_prestige_and_deadline(self):
        value = rules()
        value["prestige"]["cap"] = None
        value["palace"]["max_rounds"] = 1
        value["succession"]["max_rounds"] = 1
        state = game(value)
        state["players"]["P0"]["prestige"] = 100
        for _ in range(8):
            take(state, "move")
        self.assertTrue(engine.is_finished(state))
        self.assertTrue(state["succession_timeout"])
        engine.check_invariants(state)

    def test_full_games_and_clean_result_metrics(self):
        value = rules()
        for seed in range(8):
            mapping = dict(zip(engine.IDS, ("balanced", "collector", "early_support", "aggressive")))
            state = report.play_game(value, 4000 + seed, f"mix-{seed}", mapping)
            engine.check_invariants(state)
            result = engine.result(state)
            row = report.game_row(result)
            self.assertEqual(row["total_turns"], len(state["events"]))
            self.assertTrue(all("seals" not in m and "auto_granted" not in m
                                for m in result["players"].values()))

    def test_all_strategy_probes_use_only_legal_actions(self):
        state = game()
        obs = engine.observe(state, state["active_player"])
        for name in engine.POLICY_NAMES:
            aid, reason = policies.act(name, obs, random.Random(1))
            self.assertIn(aid, {a["action_id"] for a in obs["legal_actions"]})
            self.assertIn(engine.POLICY_VERSION, reason)

    def test_persisted_events_replay_exactly(self):
        value = rules()
        state = report.play_game(value, 17, "replay-test", dict.fromkeys(engine.IDS, "balanced"))
        with tempfile.TemporaryDirectory() as directory:
            engine.write_run(directory, state)
            loaded = engine.load_run(directory)
            self.assertEqual(engine.result(loaded), engine.result(state))
        replay = engine.new_game(value, 17, "replay-test", state["policies"])
        for record in state["events"]:
            engine.apply_action(replay, record["player"], record["turn_id"], record["action_id"], record.get("reason"))
        self.assertEqual(replay["events"], state["events"])
        self.assertEqual(engine.result(replay), engine.result(state))


if __name__ == "__main__":
    unittest.main()
