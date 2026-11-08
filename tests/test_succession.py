"""Rules, visibility, replay, and strategy checks for succession-v1."""
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
import succession

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rules():
    value = engine.load_rules(os.path.join(ROOT, "rules_v08_succession.json"))
    value["succession"]["gate_assignment"] = "manual"
    value["succession"]["contest_cost"] = 0
    return value


def game(value=None):
    state = engine.new_game(value or rules(), 2026, "succession-test", dict.fromkeys(succession.IDS, "balanced"))
    state.update(turn_order=list(succession.IDS), round_start=0, turn_index=0, active_player="P0")
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
    state = game()
    state["phase"] = 2
    state["players"]["P0"].update(pos=[6, 6], support=["army", "elites"])
    take(state, "proclaim")
    return state


class TestSuccessionRules(unittest.TestCase):
    def test_mode_dispatch_and_legacy_validation(self):
        value = rules()
        self.assertTrue(engine.validate_rules(value))
        value["gameplay_mode"] = "unknown"
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(value)
        legacy = engine.load_rules(os.path.join(ROOT, "rules_baseline.json"))
        legacy["level1"]["auto_equip_at_transition"] = False
        with self.assertRaisesRegex(engine.EngineError, "rejected"):
            engine.validate_rules(legacy)

    def test_invalid_succession_values_rejected(self):
        for field, value in (("support_cost", 0), ("contest_cost", -1), ("challenge_cost", 0),
                             ("required_support", 4), ("gate_order", ["P0"] * 4), ("gate_rotation", 4)):
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
        del candidate["equipment"]
        with self.assertRaisesRegex(engine.EngineError, "missing top-level keys"):
            engine.validate_rules(candidate)

    def test_succession_cannot_restore_the_eight_block_map(self):
        candidate = rules()
        with open(os.path.join(ROOT, "rules_v072_cardo.json"), encoding="utf-8") as source:
            candidate["board"] = json.load(source)["board"]
        with self.assertRaisesRegex(engine.EngineError, "six intact blocks"):
            engine.validate_rules(candidate)

    def test_random_gates_use_an_independent_replayable_stream(self):
        manual = rules()
        randomized = copy.deepcopy(manual)
        randomized["succession"]["gate_assignment"] = "random"
        a = engine.new_game(manual, 2026, "a")
        b = engine.new_game(randomized, 2026, "b")
        c = engine.new_game(randomized, 2026, "c")
        self.assertEqual(sorted(b["gate_assignments"].values()), list(succession.IDS))
        self.assertEqual(b["gate_assignments"], c["gate_assignments"])
        self.assertNotEqual(a["gate_assignments"], b["gate_assignments"])
        for field in ("turn_order", "district_equipment", "current_dice"):
            self.assertEqual(a[field], b[field])
        for stream in ("order", "equipment", "movement", "combat"):
            self.assertEqual(a["rng"][stream], b["rng"][stream])

    def test_gate_rotation_does_not_change_player_identity(self):
        value = rules()
        value["succession"].update(gate_order=["P3", "P2", "P1", "P0"], gate_rotation=1)
        state = engine.new_game(value, 3, "rotation")
        self.assertEqual(state["gate_assignments"], {"P0": "P2", "P1": "P1", "P2": "P0", "P3": "P3"})
        self.assertEqual(state["players"]["P0"]["gate"], value["board"]["gates"]["P2"])

    def test_transition_keeps_equipment_and_positions(self):
        value = rules()
        value["level1"]["max_rounds"] = 1
        state = game(value)
        state["players"]["P0"].update(equipment=value["equipment"][:2], pos=[3, 0])
        active(state, "P3")
        before = copy.deepcopy(state["players"])
        record = take(state, "move")
        self.assertEqual(state["phase"], 2)
        self.assertEqual(state["players"]["P0"]["equipment"], value["equipment"][:2])
        self.assertEqual(state["players"]["P0"]["pos"], [3, 0])
        self.assertEqual(state["players"]["P3"]["pos"], record["position_after"])
        self.assertTrue(state["phase1_timeout"])
        self.assertFalse(any(ev["type"] == "auto_equipment_granted" for ev in record["events"]))
        active(state, "P0")
        self.assertTrue(any(a["kind"] == "explore" and a["destination"] == [3, 0] for a in engine.legal_actions(state)))
        engine.check_invariants(state)

    def test_optional_position_reset_uses_assigned_gate(self):
        value = rules()
        value["level1"]["max_rounds"] = 1
        value["succession"].update(reset_positions=True, gate_rotation=1)
        state = game(value)
        active(state, "P3")
        take(state, "move")
        for player in state["players"].values():
            self.assertEqual(player["pos"], player["gate"])

    def test_uniform_support_cost_and_no_repeat(self):
        state = game()
        state["players"]["P0"].update(pos=[3, 0], prestige=1)
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
        kinds = {a["kind"] for a in engine.legal_actions(state) if a["destination"] == [3, 0]}
        self.assertTrue({"gain_support", "explore"} <= kinds)
        state["players"]["P0"]["prestige"] = 0
        self.assertFalse(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))

    def test_support_timing_is_configurable(self):
        value = rules()
        value["succession"]["support_in_city"] = False
        state = game(value)
        state["players"]["P0"].update(pos=[3, 0], prestige=1)
        self.assertFalse(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))
        state["phase"] = 2
        self.assertTrue(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))

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
        me.update(pos=[6, 6], support=["army", "elites"])
        self.assertFalse(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))
        state["phase"] = 2
        self.assertTrue(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))
        me["support"] = ["army"]
        self.assertFalse(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))

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
        active(state, "P3")
        state["players"]["P3"].update(pos=[6, 6], support=["army", "elites"])
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
        state["players"]["P1"]["pos"] = [6, 8]
        with patch.object(succession, "_die", side_effect=[6, 1, 3, 3]):
            take(state, "duel", target="P0", spend_prestige=False)
        self.assertIsNone(state["pending_claim"])
        self.assertEqual(state["players"]["P0"]["pos"], state["players"]["P0"]["gate"])
        self.assertEqual(state["players"]["P0"]["support"], ["army", "elites"])
        self.assertEqual(state["players"]["P1"]["stats"]["claims_cancelled_by"], 1)

    def test_contest_fee_cannot_be_bypassed(self):
        state = pending_game()
        state["rules"]["succession"]["contest_cost"] = 1
        state["players"]["P1"]["pos"] = [6, 8]
        self.assertFalse(any(a["kind"] == "duel" and a["target"] == "P0" for a in engine.legal_actions(state)))
        state["players"]["P1"]["prestige"] = 1
        contests = [a for a in engine.legal_actions(state) if a["kind"] == "duel" and a["target"] == "P0"]
        self.assertTrue(contests)
        self.assertTrue(all(a["contest_cost"] == 1 and not a["spend_prestige"] for a in contests))

    def test_failed_paid_challenge_still_pays_both_costs(self):
        state = pending_game()
        state["rules"]["succession"]["contest_cost"] = 1
        state["players"]["P1"].update(pos=[6, 8], prestige=3)
        state["players"]["P0"]["equipment"] = state["rules"]["equipment"][:]
        with patch.object(succession, "_die", side_effect=[1, 6, 3, 3]):
            record = take(state, "duel", target="P0", spend_prestige=True)
        self.assertEqual(state["players"]["P1"]["prestige"], 1)
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
        value["glory"]["cap"] = None
        value["level1"]["max_rounds"] = 1
        value["level2"]["max_rounds"] = 1
        state = game(value)
        state["players"]["P0"]["prestige"] = 100
        for _ in range(8):
            take(state, "move")
        self.assertTrue(engine.is_finished(state))
        self.assertTrue(state["phase2_timeout"])
        engine.check_invariants(state)

    def test_full_games_and_legacy_csv_compatibility(self):
        value = rules()
        value["succession"]["contest_cost"] = 1
        for seed in range(8):
            mapping = dict(zip(succession.IDS, ("balanced", "collector", "early_support", "aggressive")))
            state = report.play_game(value, 4000 + seed, f"mix-{seed}", mapping)
            engine.check_invariants(state)
            result = engine.result(state)
            row = report.game_row(result)
            self.assertEqual(row["total_turns"], len(state["events"]))
            self.assertTrue(all(m["auto_granted"] == 0 and m["seals"] == [] for m in result["players"].values()))

    def test_all_strategy_probes_use_only_legal_actions(self):
        state = game()
        obs = engine.observe(state, state["active_player"])
        for name in succession.POLICY_NAMES:
            aid, reason = policies.act(name, obs, random.Random(1))
            self.assertIn(aid, {a["action_id"] for a in obs["legal_actions"]})
            self.assertIn(succession.POLICY_VERSION, reason)

    def test_persisted_events_replay_exactly(self):
        value = rules()
        value["succession"]["contest_cost"] = 1
        state = report.play_game(value, 17, "replay-test", dict.fromkeys(succession.IDS, "balanced"))
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
