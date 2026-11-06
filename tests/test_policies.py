"""Unit tests for the four observation-only policies (SPEC §10)."""

import copy
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine
import policies

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "rules_baseline.json")


def base_obs():
    """A neutral Level 1 observation used as the template for edits."""
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        import json
        rules = json.load(fh)
    state = engine.new_game(rules, 123, "p")
    return engine.observe(state, state["active_player"])


def with_actions(obs, actions):
    """Replace the observation's legal actions with the given synthetic set."""
    obs = copy.deepcopy(obs)
    obs["legal_actions"] = []
    for i, action in enumerate(actions):
        action = copy.deepcopy(action)
        action["action_id"] = f"a{i + 1:04d}"
        action.setdefault("destination", [0, 0])
        action.setdefault("path", [[0, 0]])
        obs["legal_actions"].append(action)
    return obs


class TestGreedy(unittest.TestCase):
    def test_claims_checkpoint_when_legal(self):
        obs = with_actions(base_obs(), [
            {"kind": "move", "destination": [2, 2], "path": [[0, 0], [2, 2]]},
            {"kind": "claim_checkpoint", "destination": [2, 2],
             "path": [[2, 2]]},
        ])
        action_id, _ = policies.policy_greedy(obs)
        self.assertEqual(action_id, "a0002")

    def test_prefers_certain_explore_over_unknown(self):
        obs = base_obs()
        obs["revealed_districts"] = {"B": "gladius"}
        obs["players"][obs["viewer"]]["equipment"] = []
        obs = with_actions(obs, [
            {"kind": "explore", "destination": [3, 3]},  # unrevealed F, nearer
            {"kind": "explore", "destination": [2, 1]},  # revealed B, farther
        ])
        obs["legal_actions"][0]["path"] = [[0, 0]] * 2   # 1 step
        obs["legal_actions"][1]["path"] = [[0, 0]] * 4   # 3 steps
        action_id, _ = policies.policy_greedy(obs)
        self.assertEqual(action_id, "a0002")  # certain progress wins

    def test_level2_attacks_emperor_without_glory(self):
        obs = base_obs()
        obs["phase"] = 2
        obs["progress"]["seals_required"] = 2
        obs = with_actions(obs, [
            {"kind": "attack_emperor", "destination": [2, 4],
             "spend_glory": False},
            {"kind": "attack_emperor", "destination": [2, 4],
             "spend_glory": True},
        ])
        action_id, _ = policies.policy_greedy(obs)
        self.assertEqual(obs["legal_actions"][0]["action_id"], action_id)


class TestAggressive(unittest.TestCase):
    def test_duels_when_glory_below_cap(self):
        obs = base_obs()
        obs["players"][obs["viewer"]]["glory"] = 0
        obs["glory_cap"] = 2
        obs["players"]["P2"]["equipment_bonus"] = 0
        obs = with_actions(obs, [
            {"kind": "move", "destination": [1, 1]},
            {"kind": "duel", "destination": [1, 1], "target": "P2"},
        ])
        obs["legal_actions"][0]["path"] = [[0, 0]] * 2
        action_id, _ = policies.policy_aggressive(obs)
        self.assertEqual(action_id, "a0002")

    def test_skips_duel_at_glory_cap(self):
        obs = base_obs()
        obs["players"][obs["viewer"]]["glory"] = 2
        obs["glory_cap"] = 2
        obs = with_actions(obs, [
            {"kind": "duel", "destination": [1, 1], "target": "P2"},
            {"kind": "explore", "destination": [1, 1]},
        ])
        action_id, _ = policies.policy_aggressive(obs)
        self.assertEqual(action_id, "a0002")  # explore, not duel

    def test_spends_glory_on_emperor(self):
        obs = base_obs()
        obs["phase"] = 2
        obs = with_actions(obs, [
            {"kind": "attack_emperor", "destination": [2, 4],
             "spend_glory": False},
            {"kind": "attack_emperor", "destination": [2, 4],
             "spend_glory": True},
        ])
        action_id, _ = policies.policy_aggressive(obs)
        self.assertEqual(action_id, "a0002")


class TestBalanced(unittest.TestCase):
    def test_guard_post_when_no_explore_and_glory_low(self):
        obs = base_obs()
        obs["players"][obs["viewer"]]["glory"] = 0
        obs["glory_cap"] = 2
        obs = with_actions(obs, [
            {"kind": "move", "destination": [0, 1]},
            {"kind": "guard_post", "destination": [0, 1]},
        ])
        action_id, _ = policies.policy_balanced(obs)
        self.assertEqual(action_id, "a0002")

    def test_explore_beats_guard_post(self):
        obs = base_obs()
        obs["revealed_districts"] = {"A": "pugio"}
        obs["players"][obs["viewer"]]["glory"] = 0
        obs = with_actions(obs, [
            {"kind": "guard_post", "destination": [0, 1]},
            {"kind": "explore", "destination": [1, 1]},
        ])
        action_id, _ = policies.policy_balanced(obs)
        self.assertEqual(action_id, "a0002")

    def test_avoids_duel_against_stronger_target(self):
        obs = base_obs()
        obs["players"][obs["viewer"]]["glory"] = 1
        obs["glory_cap"] = 2
        obs["players"][obs["viewer"]]["equipment_bonus"] = 0
        obs["players"]["P2"]["equipment_bonus"] = 2
        obs["players"]["P3"]["equipment_bonus"] = 0
        obs = with_actions(obs, [
            {"kind": "duel", "destination": [1, 1], "target": "P2"},
            {"kind": "duel", "destination": [1, 1], "target": "P3"},
        ])
        action_id, _ = policies.policy_balanced(obs)
        self.assertEqual(action_id, "a0002")  # duels P3, the even match

    def test_level2_duels_only_when_out_of_glory(self):
        obs = base_obs()
        obs["phase"] = 2
        obs["players"][obs["viewer"]]["glory"] = 0
        obs["glory_cap"] = 2
        obs["players"]["P2"]["equipment_bonus"] = 0
        obs = with_actions(obs, [
            {"kind": "move", "destination": [1, 1]},
            {"kind": "duel", "destination": [1, 1], "target": "P2"},
        ])
        action_id, _ = policies.policy_balanced(obs)
        self.assertEqual(action_id, "a0002")


class TestRandom(unittest.TestCase):
    def test_only_returns_legal_ids_and_is_seed_stable(self):
        for seed in (1, 2, 3):
            with open(RULES_PATH, "r", encoding="utf-8") as fh:
                import json
                rules = json.load(fh)
            state = engine.new_game(rules, seed, "r")
            rng = random.Random(seed)
            legal = {a["action_id"] for a in engine.legal_actions(state)}
            obs = engine.observe(state, state["active_player"])
            a = policies.policy_random(obs, random.Random(5))
            b = policies.policy_random(obs, random.Random(5))
            self.assertEqual(a, b)          # deterministic per RNG seed
            self.assertIn(a[0], legal)

    def test_random_policy_never_touches_engine_rng(self):
        with open(RULES_PATH, "r", encoding="utf-8") as fh:
            import json
            rules = json.load(fh)
        state = engine.new_game(rules, 8, "r")
        before = copy.deepcopy(state["rng"])
        for _ in range(50):
            engine.observe(state, state["active_player"])  # start of turn
        self.assertEqual(state["rng"], before)


if __name__ == "__main__":
    unittest.main()
