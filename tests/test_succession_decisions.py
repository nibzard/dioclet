"""Public-only succession shortlist regressions."""

import copy
import json
from pathlib import Path
import random
import unittest

import candidate_actions as candidates
import engine
import policies

ROOT = Path(__file__).resolve().parents[1]


class TestSuccessionProjection(unittest.TestCase):
    def setUp(self):
        self.rules = engine.load_rules(str(ROOT / "rules/imperial-rivals-v0.10.2.json"))
        self.state = engine.new_game(self.rules, 2026, "succession-decisions")
        self.obs = engine.observe(self.state, self.state["active_player"])

    def test_projection_uses_new_objective_and_only_public_fields(self):
        obs = copy.deepcopy(self.obs)
        obs["district_equipment"] = {"A": "SECRET_SENTINEL"}
        obs["rng"] = "FUTURE_SENTINEL"
        projection = candidates.project_observation(obs, self.rules)
        blob = json.dumps(projection)
        self.assertEqual(projection["schema"], candidates.SUCCESSION_SCHEMA_VERSION)
        self.assertIn("survive", projection["objective"])
        self.assertNotIn("SECRET_SENTINEL", blob)
        self.assertNotIn("FUTURE_SENTINEL", blob)
        self.assertNotIn("seals_required", projection["rule_summary"])
        self.assertNotIn("emperor_hits", projection["self"])

    def test_all_essential_actions_survive_shortlist(self):
        selected, excluded = candidates.build_candidates(self.obs, self.rules, cap=3)
        kept = {a["action_id"] for a in selected}
        essential = {"proclaim", "maintain_claim", "gain_support", "claim_checkpoint", "explore"}
        for action in self.obs["legal_actions"]:
            if action["kind"] in essential:
                self.assertIn(action["action_id"], kept)
        self.assertTrue(kept <= {a["action_id"] for a in self.obs["legal_actions"]})
        self.assertEqual(len(kept), len(selected))
        self.assertEqual(kept | {a["action_id"] for a in excluded if "action_id" in a},
                         {a["action_id"] for a in self.obs["legal_actions"]})

    def test_explore_annotations_ignore_unrevealed_item_fields(self):
        obs = copy.deepcopy(self.obs)
        for action in obs["legal_actions"]:
            action["item"] = "HIDDEN_ITEM_SENTINEL"
        selected, _ = candidates.build_candidates(obs, self.rules)
        self.assertNotIn("HIDDEN_ITEM_SENTINEL", json.dumps(selected))

    def test_distances_follow_streets(self):
        dists = candidates._succession_distances(self.obs, self.rules, [5, 0])
        self.assertEqual(dists[(3, 12)], 16)

    def test_every_counterclaim_is_kept_and_costed(self):
        rules = copy.deepcopy(self.rules)
        rules["succession"]["contest_fee"] = 1
        state = engine.new_game(rules, 1, "response")
        state["phase"] = 2
        state["active_player"] = "P1"
        state["current_roll"] = 12
        state["players"]["P0"]["pos"] = rules["succession"]["map"]["checkpoint"][:]
        state["players"]["P0"]["support"] = ["army", "officials"]
        state["players"]["P1"]["pos"] = [8, 6]
        state["players"]["P1"]["prestige"] = 3
        state["pending_claim"] = {"player": "P0", "claim_id": 1, "responded": ["P2", "P3"]}
        obs = engine.observe(state, "P1")
        selected, _ = candidates.build_candidates(obs, rules, cap=2)
        by_id = {c["action_id"]: c for c in selected}
        counterclaims = [a for a in obs["legal_actions"] if a["kind"] == "duel" and a["target"] == "P0"]
        self.assertTrue(counterclaims)
        for action in counterclaims:
            c = by_id[action["action_id"]]
            self.assertTrue(c["features"]["would_cancel_claim_if_won"])
            self.assertEqual(c["features"]["prestige_cost"], 1 + bool(action["spend_prestige"]))


class TestTwinBoardShortlist(unittest.TestCase):
    def test_shortlist_builds_on_both_maps(self):
        # The succession phase of the twin-board rules is played on the
        # succession map. The shortlist once measured distances on the
        # palace map, so any succession-map cell missing from the palace
        # streets raised KeyError (found in a live four-agent game at
        # turn 98).
        rules = engine.load_rules(str(ROOT / "rules/imperial-rivals-v0.10.2.json"))
        state = engine.new_game(rules, 20261114, "twin-shortlist")
        rng = random.Random(7)
        phases = set()
        while not engine.is_finished(state):
            obs = engine.observe(state, state["active_player"])
            phases.add(obs["phase"])
            built = candidates.build_candidates(obs, rules)
            shortlist = built[0] if isinstance(built, tuple) else built
            self.assertTrue(shortlist)
            action_id, reason = policies.act("tactical", obs, rng)
            engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
        self.assertEqual(phases, {1, 2})


if __name__ == "__main__":
    unittest.main()
