"""Checks for the bounded programme runner's pure logic."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import run_programme as rp


ALLOWED = json.loads(Path("experiments/v08-programme.json").read_text())["allowed_changes"]


class ValueMembership(unittest.TestCase):
    def test_bool_never_matches_int(self):
        self.assertTrue(rp.value_allowed(1, [0, 1, 2]))
        self.assertFalse(rp.value_allowed(1, [True, False]))
        self.assertTrue(rp.value_allowed(True, [True, False]))
        self.assertFalse(rp.value_allowed(True, [0, 1, 2]))

    def test_null_only_matches_null(self):
        self.assertTrue(rp.value_allowed(None, [None, 2, 3, 4]))
        self.assertFalse(rp.value_allowed(0, [None, 2, 3, 4]))


class ApplyChange(unittest.TestCase):
    def setUp(self):
        self.rules = {"succession": {"contest_cost": 0}, "glory": {"cap": 3}}

    def test_nested_path_is_written_on_a_copy(self):
        updated = rp.apply_change(self.rules, "succession.contest_cost", 1)
        self.assertEqual(updated["succession"]["contest_cost"], 1)
        self.assertEqual(self.rules["succession"]["contest_cost"], 0)

    def test_unknown_path_raises(self):
        with self.assertRaises(KeyError):
            rp.apply_change(self.rules, "succession.missing", 1)
        with self.assertRaises(KeyError):
            rp.apply_change(self.rules, "glory.nope", 1)


class ProposalValidation(unittest.TestCase):
    def make(self, **overrides):
        proposal = {"rule_path": "succession.contest_cost", "value": 1,
                    "hypothesis": "Free opposition lets rivals cancel every claim.",
                    "prediction": "Draws and cancellations drop sharply with a fee.",
                    "refutation_evidence": "Draws stay near the incumbent level instead."}
        proposal.update(overrides)
        return proposal

    def test_valid_proposal_passes(self):
        self.assertIsNone(rp.validate_proposal(self.make(), {"succession": {"contest_cost": 0},
                                                            "glory": {"cap": 3}}, ALLOWED))

    def test_wrong_shape_is_invalid_output(self):
        self.assertEqual(rp.validate_proposal({"rule_path": "glory.cap"}, {}, ALLOWED),
                         "invalid_output")
        self.assertEqual(rp.validate_proposal(self.make(hypothesis="short"), {}, ALLOWED),
                         "invalid_output")

    def test_paths_and_values_outside_the_space_are_rejected(self):
        rules = {"succession": {"contest_cost": 0, "support_cost": 1},
                 "glory": {"cap": 3}, "level1": {"grace_full_rounds": 1}}
        self.assertEqual(rp.validate_proposal(self.make(rule_path="movement.sides"),
                                              rules, ALLOWED), "path_outside_permitted_space")
        self.assertEqual(rp.validate_proposal(self.make(value=5), rules, ALLOWED),
                         "value_outside_permitted_space")

    def test_incumbent_value_is_a_no_op(self):
        rules = {"succession": {"contest_cost": 1}, "glory": {"cap": 3}}
        self.assertEqual(rp.validate_proposal(self.make(), rules, ALLOWED), "no_op_proposal")


class PromotionChecks(unittest.TestCase):
    PROMO = json.loads(Path("experiments/v08-programme.json").read_text())["promotion"]

    def metrics(self, draws=0.5, rounds=10, winners=("collector", "counterleader"),
                claims=2560, cancelled=2490, challenged=0.8, games=96):
        return {"finished_games": games, "incomplete_games": 0, "draw_fraction": draws,
                "median_rounds": rounds,
                "wins_by_strategy": {name: 10 for name in winners},
                "claims_made": claims, "claims_cancelled": cancelled,
                "challenged_claim_fraction": challenged,
                "cancellation_rate": cancelled / claims if claims else 0.0,
                "cancellations_per_game": cancelled / games}

    def test_improving_candidate_passes(self):
        incumbent = self.metrics()
        # Volume collapses even though most challenged claims still get canceled.
        candidate = self.metrics(draws=0.05, rounds=9, claims=760, cancelled=670,
                                 challenged=0.99, winners=("collector", "early_support"))
        checks = rp.promotion_checks(incumbent, candidate, self.PROMO)
        self.assertTrue(all(check["passed"] for check in checks), checks)

    def test_candidate_without_counterplay_fails(self):
        incumbent = self.metrics()
        candidate = self.metrics(draws=0.0, claims=760, cancelled=100, challenged=0.05)
        checks = rp.promotion_checks(incumbent, candidate, self.PROMO)
        failed = {check["check"] for check in checks if not check["passed"]}
        self.assertIn("counterplay_exists", failed)

    def test_single_profile_winner_fails(self):
        incumbent = self.metrics()
        candidate = self.metrics(draws=0.0, claims=760, cancelled=100, challenged=0.6,
                                 winners=("prestige_farmer",))
        checks = rp.promotion_checks(incumbent, candidate, self.PROMO)
        failed = {check["check"] for check in checks if not check["passed"]}
        self.assertIn("profile_diversity", failed)

    def test_draw_increase_fails_even_with_counterplay(self):
        incumbent = self.metrics(draws=0.0, claims=760, cancelled=100, challenged=0.6)
        candidate = self.metrics(draws=0.1, claims=760, cancelled=50, challenged=0.6)
        checks = rp.promotion_checks(incumbent, candidate, self.PROMO)
        failed = {check["check"] for check in checks if not check["passed"]}
        self.assertIn("draws_not_materially_worse", failed)

    def test_unshrunk_denial_loop_fails(self):
        incumbent = self.metrics()
        # Same per-game cancellation volume: the loop did not shrink.
        candidate = self.metrics(draws=0.05, claims=2560, cancelled=2400, challenged=0.99)
        checks = rp.promotion_checks(incumbent, candidate, self.PROMO)
        failed = {check["check"] for check in checks if not check["passed"]}
        self.assertIn("cancellation_reduction", failed)

    def test_improvement_checks_do_not_bind_on_a_healthy_incumbent(self):
        incumbent = self.metrics(draws=0.0, claims=100, cancelled=90, challenged=0.6)
        candidate = self.metrics(draws=0.0, claims=100, cancelled=90, challenged=0.6)
        checks = rp.promotion_checks(incumbent, candidate, self.PROMO)
        names = {check["check"] for check in checks}
        self.assertNotIn("draw_improvement", names)
        self.assertNotIn("cancellation_reduction", names)


class ScriptedProposals(unittest.TestCase):
    def test_every_scripted_proposal_is_permitted_and_labeled(self):
        rules = {"succession": {"contest_cost": 0, "support_cost": 1, "challenge_bonus": 2},
                 "glory": {"cap": 3}, "level1": {"grace_full_rounds": 1}}
        for proposal in rp.SCRIPTED_PROPOSALS:
            self.assertIn("Scripted smoke proposal", proposal["hypothesis"])
            self.assertIsNone(rp.validate_proposal(proposal, rules, ALLOWED))


class StopPaths(unittest.TestCase):
    """Runner-level stops, with no suites and no model calls."""

    def run_main(self, proposals):
        import contextlib
        import io
        import tempfile
        original = rp.SCRIPTED_PROPOSALS
        rp.SCRIPTED_PROPOSALS = tuple(proposals)
        try:
            with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
                code = rp.main(["--agent", "scripted", "--games", "1", "--cycles", "1",
                                "--out", str(Path(tmp) / "run")])
                stop = json.loads((Path(tmp) / "run" / "stop.json").read_text()) \
                    if (Path(tmp) / "run" / "stop.json").exists() else None
        finally:
            rp.SCRIPTED_PROPOSALS = original
        return code, stop

    def proposal(self, path, value):
        return {"rule_path": path, "value": value,
                "hypothesis": "Scripted smoke proposal used only by this test harness.",
                "prediction": "The runner must stop before running any suite.",
                "refutation_evidence": "A suite directory would appear inside the cycle."}

    def test_no_op_proposal_stops_the_run(self):
        incumbent = json.loads(
            Path("rules_v08_succession.json").read_text())["succession"]["contest_cost"]
        code, stop = self.run_main([self.proposal("succession.contest_cost", incumbent)])
        self.assertEqual(code, 3)
        self.assertEqual(stop["reason"], "no_op_proposal")

    def test_value_outside_space_stops_the_run(self):
        code, stop = self.run_main([self.proposal("succession.contest_cost", 7)])
        self.assertEqual(code, 3)
        self.assertEqual(stop["reason"], "value_outside_permitted_space")


class Prompt(unittest.TestCase):
    def test_prompt_carries_the_contract(self):
        cfg = json.loads(Path("experiments/v08-programme.json").read_text())
        rules = {"succession": {"contest_cost": 0, "support_cost": 1,
                                "support_in_city": True, "challenge_bonus": 2,
                                "reset_positions": False},
                 "glory": {"cap": 3}, "level1": {"grace_full_rounds": 1}}
        prompt, schema = rp.build_prompt(
            cfg, 1, 3, rules, "rules_v08_succession.json", [],
            [{"game_id": "g", "turn_id": 1, "choice_rich": True}])
        self.assertIn("Output ONLY a JSON object", prompt)
        self.assertIn("succession.contest_cost", prompt)
        self.assertIn("rules_v08_succession.json", prompt)
        self.assertEqual(schema["required"],
                         ["rule_path", "value", "hypothesis", "prediction",
                          "refutation_evidence"])
        self.assertEqual(sorted(schema["properties"]["rule_path"]["enum"]),
                         sorted(cfg["allowed_changes"]))


if __name__ == "__main__":
    unittest.main()
