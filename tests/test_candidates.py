"""Offline tests for observation projection and candidate shortlists."""

import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidate_actions
import engine
import report

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "rules_baseline.json")
V03_BASE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "rules_v03_base.json")


def load(path=RULES_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def collect_observations(rules, seed, limit=60):
    """Play one scripted game, capturing every public observation."""
    state = engine.new_game(rules, seed, f"obs-{seed}",
                            {"P0": "balanced", "P1": "greedy",
                             "P2": "aggressive", "P3": "random"})
    prng = __import__("random").Random(seed)
    out = []
    while not engine.is_finished(state) and len(out) < limit:
        obs = engine.observe(state, state["active_player"])
        out.append(copy.deepcopy(obs))
        action_id, reason = report._act(
            state["policies"][state["active_player"]], obs, rules, prng)
        engine.apply_action(state, state["active_player"], obs["turn_id"],
                            action_id, reason)
    return out, state


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


class TestProjection(unittest.TestCase):
    def test_projection_public_and_stable(self):
        rules = load()
        observations, state = collect_observations(rules, 12, limit=8)
        proj = candidate_actions.project_observation(observations[0], rules)
        blob = json.dumps(proj, sort_keys=True)
        for key in ("objective", "turn", "self", "opponents",
                    "public_locations", "rule_summary"):
            self.assertIn(key, blob)
        again = candidate_actions.project_observation(observations[0], rules)
        self.assertEqual(proj, again)
        self.assertEqual(
            candidate_actions.projection_hash(proj),
            candidate_actions.projection_hash(again))
        # Hidden mapping never enters the projection.
        for name, item in state["district_equipment"].items():
            if name not in state["revealed"]:
                self.assertNotIn(item, json.dumps(proj.get(
                    "revealed_districts", {})))

    def test_projection_excludes_unrevealed_mapping(self):
        rules = load()
        state = engine.new_game(rules, 5, "p")
        obs = engine.observe(state, state["active_player"])
        proj = candidate_actions.project_observation(obs, rules)
        # Equipment NAMES are a public catalog; the hidden information
        # is which district holds which item. Only revealed pairs may
        # appear together in revealed_districts.
        revealed = proj["revealed_districts"]
        for name, item in state["district_equipment"].items():
            if name not in state["revealed"]:
                self.assertNotIn(name, revealed)
        for name, item in revealed.items():
            self.assertEqual(state["district_equipment"][name], item)


class TestCandidates(unittest.TestCase):
    def _check(self, obs, rules, cap=16):
        candidates, excluded = candidate_actions.build_candidates(
            obs, rules, cap=cap)
        legal = {a["action_id"] for a in obs["legal_actions"]}
        ids = [c["action_id"] for c in candidates]
        self.assertTrue(ids)
        self.assertLessEqual(len(ids), 24)          # API bound 2..255
        self.assertGreaterEqual(len(ids), 2)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids) <= legal)          # never invents actions
        kept = set(ids) | {e["action_id"] for e in excluded
                           if "action_id" in e}
        self.assertEqual(kept, legal)               # exclusions audited
        # Mandatory kinds always retained.
        for action in obs["legal_actions"]:
            if action["kind"] in ("attack_emperor", "claim_checkpoint",
                                  "attempt_seal", "explore"):
                self.assertIn(action["action_id"], ids)
        # Distinct duel targets retained.
        targets = {a["target"] for a in obs["legal_actions"]
                   if a["kind"] == "duel"}
        kept_targets = {c["target"] for c in candidates if c["kind"] == "duel"}
        self.assertEqual(targets, kept_targets)
        return candidates, excluded

    def test_shortlist_invariants_across_generated_observations(self):
        rules = load()
        total = 0
        for seed in (21, 22):
            observations, _ = collect_observations(rules, seed, limit=55)
            for obs in observations:
                self._check(obs, rules)
                total += 1
        self.assertGreaterEqual(total, 100)  # spec: 100+ observations

    def test_deterministic_and_stable(self):
        rules = load()
        observations, _ = collect_observations(rules, 23, limit=10)
        for obs in observations:
            a = candidate_actions.build_candidates(obs, rules)
            b = candidate_actions.build_candidates(obs, rules)
            self.assertEqual(a, b)

    def test_keeps_non_greedy_move_alternative(self):
        rules = load()
        state = engine.new_game(rules, 31, "g")
        obs = engine.observe(state, state["active_player"])
        obs = copy.deepcopy(obs)
        # Fake a rich goal-directed field: several move actions exist.
        moves = [a for a in obs["legal_actions"] if a["kind"] == "move"]
        if len(moves) < 2:
            self.skipTest("few moves on this roll")
        candidates, _ = candidate_actions.build_candidates(obs, rules)
        kept_moves = [c for c in candidates if c["kind"] == "move"]
        self.assertGreaterEqual(len(kept_moves), 2)

    def test_cap_escalation_never_drops_mandatory(self):
        rules = load(V03_BASE)
        state = engine.new_game(rules, 7, "c")
        state["phase"] = 2
        state["round"] = 1
        for pid, p in state["players"].items():
            p["equipment"] = sorted(rules["equipment"])
        state["players"]["P0"]["pos"] = [2, 4]
        state["players"]["P0"]["seals"] = ["cellars", "peristyle"]
        state["players"]["P0"]["hits"] = 1
        state["turn_index"] = state["turn_order"].index("P0")
        state["active_player"] = "P0"
        state["current_roll"] = 6
        obs = engine.observe(state, "P0")
        candidates, excluded = candidate_actions.build_candidates(
            obs, rules, cap=2)
        kinds = {c["kind"] for c in candidates}
        self.assertIn("attack_emperor", kinds)
        notes = [e for e in excluded if "note" in e]
        self.assertTrue(any("cap raised" in e["note"] for e in notes))

    def test_single_legal_action_short_circuit(self):
        rules = load()
        state = engine.new_game(rules, 3, "s")
        obs = engine.observe(state, state["active_player"])
        obs = copy.deepcopy(obs)
        only = obs["legal_actions"][0]
        obs["legal_actions"] = [only]
        candidates, excluded = candidate_actions.build_candidates(obs, rules)
        self.assertEqual([c["action_id"] for c in candidates],
                         [only["action_id"]])
        self.assertEqual(excluded, [])

    def test_features_exact_not_heuristic(self):
        rules = load(V03_BASE)
        state = engine.new_game(rules, 9, "f")
        state["phase"] = 2
        for p in state["players"].values():
            p["equipment"] = sorted(rules["equipment"])
        me = state["players"][state["active_player"]]
        me["pos"] = [2, 4]
        me["seals"] = ["cellars", "peristyle"]
        me["hits"] = 1
        state["current_roll"] = 1
        obs = engine.observe(state, state["active_player"])
        candidates, _ = candidate_actions.build_candidates(obs, rules)
        for c in candidates:
            if c["kind"] == "attack_emperor":
                expected = candidate_actions.contest_probability(
                    2 + (2 if c["spend_glory"] else 0), 2, False)
                self.assertAlmostEqual(
                    c["features"]["hit_probability_exact"], expected,
                    delta=0.0001)
                self.assertTrue(c["features"]["would_win_game_if_hit"])
                self.assertIn("exact", json.dumps(c["description"]))


if __name__ == "__main__":
    unittest.main()
