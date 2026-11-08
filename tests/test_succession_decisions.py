"""Public-only succession decisions and bounded experiment regressions."""

import copy
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import candidate_actions as candidates
import decisions_policy as decisions
import engine

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("succession_experiments", ROOT / "tools/succession_experiments.py")
experiments = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiments)


class StubClient:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.decisions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def response(choice, kind="choice"):
    return SimpleNamespace(answers=[SimpleNamespace(type=kind, name="best_action", choice=choice,
                                                    probabilities=None, confidence=None)],
                           usage=SimpleNamespace(input_tokens=100, output_tokens=0, total_tokens=100,
                                                 input_tokens_details=None),
                           model="gpt-6-luna", id="test-request")


class TestSuccessionProjection(unittest.TestCase):
    def setUp(self):
        self.rules = engine.load_rules(str(ROOT / "rules_v08_succession.json"))
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
        rules["succession"]["contest_cost"] = 1
        state = engine.new_game(rules, 1, "response")
        state["phase"] = 2
        state["active_player"] = "P1"
        state["current_roll"] = 12
        state["players"]["P0"]["pos"] = rules["board"]["checkpoint"][:]
        state["players"]["P0"]["support"] = ["army", "officials"]
        state["players"]["P1"]["pos"] = [6, 5]
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

    def test_live_request_has_succession_goal_and_features(self):
        projection = candidates.project_observation(self.obs, self.rules)
        selected, _ = candidates.build_candidates(self.obs, self.rules)
        provider = decisions.LiveProvider(client=StubClient(None))
        request = provider.build_request(projection, selected)
        self.assertIn("succession", request["questions"][0]["instructions"])
        self.assertIn("candidate_features", request["input"][0]["content"][1]["data"])
        self.assertEqual(request["model"], "gpt-6-luna")


class TestExperimentBudget(unittest.TestCase):
    def test_sent_invalid_request_stays_counted(self):
        client = StubClient(response("not-legal"))
        provider = decisions.LiveProvider(client=client)
        budget = decisions.Budget(max_calls=1, max_cost_usd=0.75)
        choices = [{"action_id": "a1", "description": "First"}, {"action_id": "a2", "description": "Second"}]
        with self.assertRaises(decisions.InvalidAnswerError):
            provider.decide({}, choices, {"strict_budget": True}, budget)
        self.assertEqual(budget.calls, 1)
        self.assertGreater(budget.spent_estimate_usd, 0)
        with self.assertRaises(decisions.BudgetExceededError):
            provider.decide({}, choices, {"strict_budget": True}, budget)
        self.assertEqual(len(client.calls), 1)

    def test_persistent_ledger_never_resets_between_cycles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.json"
            budget = experiments.LedgerBudget(path, 2, 0.75)
            budget.record(100, 0.01)
            budget.close()
            next_cycle = experiments.LedgerBudget(path, 2, 0.75)
            self.assertEqual(next_cycle.calls, 1)
            self.assertEqual(next_cycle.spent_estimate_usd, 0.01)
            next_cycle.close()
            with self.assertRaises(ValueError):
                experiments.LedgerBudget(path, 3, 0.75)

    def test_gate_schedule_covers_every_permutation(self):
        gates = {experiments.schedule(i)[0] for i in range(24)}
        self.assertEqual(gates, set(itertools.permutations(experiments.IDS)))
        self.assertEqual(set(experiments.schedule(0)[1].values()), set(experiments.PROFILES))

    def test_alternative_audit_does_not_mutate_state(self):
        rules = engine.load_rules(str(ROOT / "rules_v08_succession.json"))
        state = engine.new_game(rules, 2026, "audit")
        before = copy.deepcopy(state)
        action = engine.legal_actions(state)[0]
        audit = experiments.alternative_audit(state, action["action_id"], rollouts=1, turn_bound=10)
        self.assertEqual(before, state)
        self.assertTrue(audit["alternatives"])
        self.assertNotIn("district_equipment", audit["public_projection"])
        self.assertIn("policy-dependent", audit["limitations"])
        self.assertTrue(all("truncated" in a["outcomes"] for a in audit["alternatives"]))


if __name__ == "__main__":
    unittest.main()
