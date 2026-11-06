"""Engine invariant and rules tests (SPEC §14)."""

import copy
import json
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine
import policies
import report

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "rules_baseline.json")


def load_baseline():
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def phase2_state(seed=7, active="P0", **over):
    """Craft a Level 2 state for targeted resolution tests."""
    rules = load_baseline()
    state = engine.new_game(rules, seed, "t")
    state["phase"] = 2
    state["round"] = 1
    for pid, p in state["players"].items():
        p["equipment"] = sorted(rules["equipment"])
        p["seals"] = []
        p["hits"] = 0
    state["turn_index"] = state["turn_order"].index(active)
    state["active_player"] = active
    for key, value in over.items():
        if key == "pos":
            state["players"][active]["pos"] = list(value)
        elif key == "glory":
            state["players"][active]["glory"] = value
        elif key == "seals":
            state["players"][active]["seals"] = list(value)
        elif key == "hits":
            state["players"][active]["hits"] = value
        elif key == "roll":
            state["current_roll"] = value
        elif key == "others_pos":
            for pid, pos in value.items():
                state["players"][pid]["pos"] = list(pos)
        else:
            raise KeyError(key)
    return state


class TestRulesValidation(unittest.TestCase):
    def test_baseline_loads(self):
        rules = engine.load_rules(RULES_PATH)
        self.assertEqual(rules["players"], 4)

    def _bad(self, mutate, needle):
        rules = load_baseline()
        mutate(rules)
        with self.assertRaises(engine.EngineError) as ctx:
            engine.validate_rules(rules)
        self.assertIn(needle, str(ctx.exception))

    def test_unknown_key_rejected(self):
        self._bad(lambda r: r.update({"surprise": 1}), "unknown top-level keys")

    def test_auto_equip_false_rejected(self):
        self._bad(lambda r: r["level1"].update(
            {"auto_equip_at_transition": False}), "auto_equip")

    def test_bad_gate_rejected(self):
        self._bad(lambda r: r["board"]["gates"].update({"P0": [9, 9]}),
                  "gate P0")

    def test_too_many_seals_required(self):
        self._bad(lambda r: r["level2"].update(
            {"required_distinct_seals": 4}), "required_distinct_seals")

    def test_missing_bonus_tier(self):
        self._bad(lambda r: r["combat"].update(
            {"equipment_bonus_tiers": [
                {"min_count": 0, "max_count": 2, "bonus": 0}]}),
            "tier missing")

    def test_duplicate_district_cells(self):
        self._bad(lambda r: r["board"]["districts"].update(
            {"F": r["board"]["districts"]["E"]}), "distinct")


class TestNewGameAndObservation(unittest.TestCase):
    def test_initial_state(self):
        state = engine.new_game(load_baseline(), 11, "g")
        rules = load_baseline()
        for pid, p in state["players"].items():
            self.assertEqual(p["pos"], rules["board"]["gates"][pid])
            self.assertEqual(p["equipment"], [])
            self.assertEqual(p["glory"], 0)
        self.assertIn(state["active_player"], ("P0", "P1", "P2", "P3"))
        self.assertGreaterEqual(state["current_roll"], 1)
        mapping = state["district_equipment"]
        self.assertEqual(sorted(mapping.values()), sorted(rules["equipment"]))

    def test_turn_order_seed_stable(self):
        a = engine.new_game(load_baseline(), 5, "g")
        b = engine.new_game(load_baseline(), 5, "g")
        c = engine.new_game(load_baseline(), 6, "g")
        self.assertEqual(a["turn_order"], b["turn_order"])
        self.assertNotEqual(a["turn_order"], c["turn_order"])

    def test_observe_idempotent_and_unrevealed_hidden(self):
        state = engine.new_game(load_baseline(), 3, "g")
        first = engine.observe(state, state["active_player"])
        snapshot = copy.deepcopy(state)
        for _ in range(3):
            again = engine.observe(state, state["active_player"])
            self.assertEqual(again, first)
        self.assertEqual(state, snapshot)  # no RNG or state drift
        blob = json.dumps(first)
        for name, item in state["district_equipment"].items():
            if name not in state["revealed"]:
                self.assertNotIn(
                    json.dumps({"district": name, "item": item})[1:-1],
                    blob.replace(" ", ""))

    def test_observe_rejects_non_active_player(self):
        state = engine.new_game(load_baseline(), 3, "g")
        other = next(p for p in ("P0", "P1", "P2", "P3")
                     if p != state["active_player"])
        with self.assertRaises(engine.EngineError):
            engine.observe(state, other)

    def test_action_ids_stable_and_sorted(self):
        state = engine.new_game(load_baseline(), 3, "g")
        actions = engine.legal_actions(state)
        ids = [a["action_id"] for a in actions]
        self.assertEqual(ids, [f"a{i + 1:04d}" for i in range(len(ids))])
        keys = [(a["kind"], a["destination"][0], a["destination"][1],
                 a.get("target") or "", 1 if a.get("spend_glory") else 0)
                for a in actions]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(engine.legal_actions(state), actions)

    def test_invalid_actions_do_not_mutate(self):
        state = engine.new_game(load_baseline(), 3, "g")
        snapshot = copy.deepcopy(state)
        for player, turn_id, action_id in (
                (state["active_player"], 99, "a0001"),
                (state["active_player"], 1, "a9999"),
                ("P0" if state["active_player"] != "P0" else "P1", 1, "a0001")):
            with self.assertRaises(engine.EngineError):
                engine.apply_action(state, player, turn_id, action_id)
        self.assertEqual(state, snapshot)


class TestBoard(unittest.TestCase):
    def test_shortest_path_deterministic(self):
        board = engine.Board(load_baseline())
        path = board.path((0, 0), (2, 2))
        # East is preferred over south at every tie.
        self.assertEqual(path, [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)])
        self.assertEqual(board.distance((0, 4), (4, 0)), 8)

    def test_no_diagonal_steps(self):
        board = engine.Board(load_baseline())
        for x in range(5):
            for y in range(5):
                for nx in range(5):
                    for ny in range(5):
                        for a, b in zip(board.path((x, y), (nx, ny)),
                                        board.path((x, y), (nx, ny))[1:]):
                            self.assertEqual(abs(a[0] - b[0]) +
                                             abs(a[1] - b[1]), 1)


class TestResolution(unittest.TestCase):
    def _apply(self, state, kind, **match):
        for action in engine.legal_actions(state):
            if action["kind"] == kind and all(
                    action.get(k) == v for k, v in match.items()):
                return engine.apply_action(state, state["active_player"],
                                           state["turn_id"], action["action_id"])
        raise AssertionError(f"no {kind} action with {match}")

    def test_explore_reveals_and_grants(self):
        rules = load_baseline()
        state = engine.new_game(rules, 1, "g")
        state["current_roll"] = 6
        me = state["players"][state["active_player"]]
        me["pos"] = [2, 1]  # district B
        record = self._apply(state, "explore", destination=[2, 1])
        types = [e["type"] for e in record["events"]]
        self.assertIn("district_revealed", types)
        self.assertIn("equipment_collected", types)
        self.assertEqual(len(me["equipment"]), 1)
        self.assertEqual(state["revealed"]["B"], me["equipment"][0])

    def test_explore_unrevealed_duplicate_grants_nothing(self):
        # D1: standing on an unrevealed district whose type I own.
        rules = load_baseline()
        state = engine.new_game(rules, 1, "g")
        me = state["players"][state["active_player"]]
        me["pos"] = [2, 1]
        me["equipment"] = [state["district_equipment"]["B"]]
        record = self._apply(state, "explore", destination=[2, 1])
        types = [e["type"] for e in record["events"]]
        self.assertIn("district_revealed", types)
        self.assertIn("explore_no_gain", types)
        self.assertEqual(len(me["equipment"]), 1)

    def test_guard_post_needs_movement(self):
        rules = load_baseline()
        state = engine.new_game(rules, 1, "g")
        me = state["players"][state["active_player"]]
        me["pos"] = [0, 1]  # a glory post
        state["current_roll"] = 3
        for action in engine.legal_actions(state):
            if action["kind"] == "guard_post":
                self.assertNotEqual(action["destination"], me["pos"],
                                    "stationary guard-post farming")

    def test_duel_tie_goes_to_defender(self):
        rules = load_baseline()
        seen_tie = duels = 0
        for seed in range(30):
            state = engine.new_game(rules, seed, "g")
            me = state["players"][state["active_player"]]
            other = next(p for p in state["players"] if p != state["active_player"])
            me["pos"] = [2, 2]
            state["players"][other]["pos"] = [2, 1]  # within duel range
            state["players"][other]["equipment"] = list(me["equipment"])
            state["current_roll"] = 3
            record = self._apply(state, "duel", destination=[2, 1],
                                 target=other)
            duels += 1
            for ev in record["events"]:
                if ev["type"] == "duel" and \
                        ev["attacker_score"] == ev["defender_score"]:
                    seen_tie += 1
                    self.assertEqual(ev["winner"], ev["defender"])
        self.assertGreater(duels, 20)
        self.assertGreater(seen_tie, 0, "no tie observed in 30 seeded duels")

    def test_claim_checkpoint_and_grace(self):
        rules = load_baseline()
        state = engine.new_game(rules, 1, "g")
        me = state["players"][state["active_player"]]
        me["equipment"] = sorted(rules["equipment"])
        me["pos"] = [2, 2]
        state["current_roll"] = 2
        trigger_round = 4
        state["round"] = trigger_round
        record = self._apply(state, "claim_checkpoint")
        self.assertEqual(state["first_challenger"], record["player"])
        self.assertEqual(state["trigger_round"], trigger_round)
        # Transition must happen after round min(4+2, 24) = 6.
        while state["phase"] == 1:
            self._apply(state, "move")
            engine.check_invariants(state)
        self.assertEqual(state["rounds_level1"], 6)
        for p in state["players"].values():
            self.assertEqual(len(p["equipment"]), 6)  # auto-equipped
            self.assertEqual(p["pos"], p["gate"])     # reset to gates
        self.assertEqual(state["round"], 1)
        self.assertEqual(state["phase"], 2)
        self.assertFalse(state["phase1_timeout"])

    def test_phase1_timeout_when_nobody_claims(self):
        rules = load_baseline()
        rules["level1"]["max_rounds"] = 2
        state = engine.new_game(rules, 1, "g")
        while state["phase"] == 1:
            for action in engine.legal_actions(state):
                if action["kind"] == "move":
                    engine.apply_action(state, state["active_player"],
                                        state["turn_id"], action["action_id"])
                    break
            else:
                engine.apply_action(state, state["active_player"],
                                    state["turn_id"],
                                    engine.legal_actions(state)[0]["action_id"])
        self.assertTrue(state["phase1_timeout"])
        self.assertEqual(state["rounds_level1"], 2)

    def test_peristyle_glory_purchase(self):
        state = phase2_state(active="P0", pos=[2, 2], glory=1, seals=[])
        record = self._apply(state, "attempt_seal", spend_glory=True)
        me = state["players"]["P0"]
        self.assertEqual(me["glory"], 0)
        self.assertEqual(me["seals"], ["peristyle"])
        self.assertEqual(record["dice_used"], [])  # no roll: guaranteed
        engine.check_invariants(state)

    def test_completed_seal_cannot_repeat(self):
        state = phase2_state(active="P0", pos=[1, 1], seals=["cellars"])
        state["current_roll"] = 0  # stationary only
        for action in engine.legal_actions(state):
            self.assertNotEqual(
                (action["kind"], tuple(action["destination"])),
                ("attempt_seal", (1, 1)))

    def test_emperor_needs_seals(self):
        state = phase2_state(active="P0", pos=[2, 4], seals=["cellars"])
        state["current_roll"] = 0
        kinds = {a["kind"] for a in engine.legal_actions(state)}
        self.assertNotIn("attack_emperor", kinds)

    def test_emperor_failure_retreats_and_success_wins(self):
        rules = load_baseline()
        misses = wins = 0
        for seed in range(1, 40):
            state = phase2_state(seed=seed, active="P0", pos=[2, 4],
                                 seals=["cellars", "peristyle"], hits=1,
                                 glory=2)
            record = self._apply(state, "attack_emperor", spend_glory=True)
            me = state["players"]["P0"]
            for ev in record["events"]:
                if ev["type"] == "emperor_miss":
                    misses += 1
                    self.assertEqual(me["pos"], [2, 3])   # retreat node
                    self.assertEqual(record["position_after"], [2, 3])
                    self.assertEqual(me["hits"], 1)       # hits persist
                    self.assertEqual(me["glory"], 1)      # spent, not refunded
            if state["status"] == "finished":
                wins += 1
                self.assertEqual(state["winner"], "P0")
                self.assertEqual(me["hits"], 2)
                if me["pos"] != [2, 4]:
                    self.assertEqual(me["pos"], [2, 4])  # stays in chamber
        self.assertGreater(misses, 0, "no emperor miss in 39 seeded attacks")
        self.assertGreater(wins, 0, "no emperor win in 39 seeded attacks")

    def test_phase2_timeout_draw(self):
        rules = load_baseline()
        rules["level2"]["max_rounds"] = 1
        rules["level2"]["required_distinct_seals"] = 3  # unreachable quickly
        state = engine.new_game(rules, 1, "g")
        me = state["players"][state["active_player"]]
        me["equipment"] = sorted(rules["equipment"])
        me["pos"] = [2, 2]
        state["current_roll"] = 1
        self._apply(state, "claim_checkpoint")
        while state["status"] == "in_progress":
            engine.apply_action(state, state["active_player"], state["turn_id"],
                                engine.legal_actions(state)[0]["action_id"])
        self.assertIsNone(state["winner"])
        self.assertTrue(state["phase2_timeout"])


class TestReplayAndBatch(unittest.TestCase):
    def test_full_game_replay_identical(self):
        rules = engine.load_rules(RULES_PATH)
        pol = {"P0": "balanced", "P1": "greedy",
               "P2": "aggressive", "P3": "random"}
        state = report.play_game(rules, 99, "replay-t", pol)
        first = engine.result(state)
        events = copy.deepcopy(state["events"])

        replay = engine.new_game(rules, 99, "replay-t", pol)
        for record in events:
            engine.apply_action(replay, record["player"], record["turn_id"],
                                record["action_id"], record.get("reason"))
        self.assertEqual(replay["events"], events)
        self.assertEqual(engine.result(replay), first)

    def test_played_games_keep_invariants(self):
        rules = engine.load_rules(RULES_PATH)
        for seed in (21, 22, 23):
            pol = report.schedule_for(seed % 4, 4)
            state = report.play_game(rules, seed, f"inv-{seed}", pol)
            engine.check_invariants(state)
            self.assertIn(state["status"], ("in_progress", "finished"))
            self.assertEqual(state["status"], "finished")

    def test_schedule_blocks(self):
        self.assertEqual(report.schedule_for(0, 1000),
                         {"P0": "balanced", "P1": "balanced",
                          "P2": "balanced", "P3": "balanced"})
        block2 = report.schedule_for(250, 1000)
        self.assertEqual(list(block2.values()).count("aggressive"), 1)
        self.assertEqual(report.schedule_for(253, 1000)["P3"], "aggressive")
        block3 = report.schedule_for(500, 1000)
        self.assertEqual(list(block3.values()).count("greedy"), 1)
        block4 = report.schedule_for(750, 1000)
        self.assertEqual(sorted(block4.values()),
                         ["aggressive", "balanced", "greedy", "random"])


class TestBoundedExhaustive(unittest.TestCase):
    """Apply every legal action from several states; no illegal transition."""

    def _exhaust(self, state, label):
        engine.check_invariants(state)
        count = 0
        for action in engine.legal_actions(state):
            clone = copy.deepcopy(state)
            engine.apply_action(clone, clone["active_player"],
                                clone["turn_id"], action["action_id"])
            engine.check_invariants(clone)
            for rec in [clone["events"][-1]]:
                self.assertLessEqual(len(rec["action"]["path"]) - 1,
                                     rec["movement_die"], f"{label}: too far")
            count += 1
        self.assertGreater(count, 0, label)
        return count

    def test_depth_one_from_various_states(self):
        rules = load_baseline()
        for seed in (1, 2, 3):
            state = engine.new_game(rules, seed, "e")
            self._exhaust(state, f"start-{seed}")
        mid = engine.new_game(load_baseline(), 4, "e")
        mid["round"] = 10
        mid["current_roll"] = 6
        mid["players"][mid["active_player"]]["equipment"] = \
            sorted(rules["equipment"])[:5]
        self._exhaust(mid, "mid-l1")
        self._exhaust(phase2_state(pos=[2, 2], glory=2), "l2-central")
        self._exhaust(phase2_state(pos=[2, 4], glory=1,
                                   seals=["cellars", "peristyle"]),
                      "l2-emperor")

    def test_depth_three_bounded(self):
        rules = load_baseline()
        state = engine.new_game(rules, 9, "e3")
        explored = 0

        def walk(state, depth):
            nonlocal explored
            actions = engine.legal_actions(state)
            for action in actions[:6]:  # bounded enumeration
                clone = copy.deepcopy(state)
                engine.apply_action(clone, clone["active_player"],
                                    clone["turn_id"], action["action_id"])
                engine.check_invariants(clone)
                explored += 1
                if depth > 1:
                    walk(clone, depth - 1)

        walk(state, 3)
        self.assertGreater(explored, 100)


if __name__ == "__main__":
    unittest.main()
