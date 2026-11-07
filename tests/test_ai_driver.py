"""Offline driver tests: mock games, replay, budgets, hidden state."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_driver
import candidate_actions
import decisions_policy
import engine
import tactical_policy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(BASE_DIR, "rules_baseline.json")
V03_BASE = os.path.join(BASE_DIR, "rules_v03_base.json")

CONFIG = {"provider": "mock", "model": "gpt-6-luna", "candidate_cap": 16,
          "prompt_version": "v04-1", "selection_mode": "top",
          "max_retries": 1, "timeout_seconds": 20,
          "fallback_on_live_error": False, "persona": "win_focused"}


def load_rules(path=RULES_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class Ans:
    pass


def stub_response(choice):
    answer = Ans()
    answer.type = "choice"
    answer.name = "best_action"
    answer.choice = choice
    answer.probabilities = [{"value": choice, "probability": 1.0}]
    answer.confidence = 0.9
    response = Ans()
    response.answers = [answer]
    response.model = "gpt-6-luna"
    response.id = "req_stub"
    usage = Ans()
    usage.input_tokens = 900
    usage.output_tokens = 0
    usage.total_tokens = 900
    details = Ans()
    details.cached_tokens = 0
    details.cache_write_tokens = 0
    usage.input_tokens_details = details
    response.usage = usage
    return response


class RecordingStub:
    """Live stub: records requests, answers with a legal candidate."""

    def __init__(self):
        self.decisions = self
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        values = kwargs["questions"][0]["choices"]
        # Deterministic pick: first candidate value.
        return stub_response(values[0]["value"])


class DriverTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v04-driver-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_game(self, rules=None, seed=4400, provider="mock",
                 players=None, **kwargs):
        rules = rules or load_rules()
        players = players or {p: "decisions" for p in ai_driver.SEATS}
        out = os.path.join(self.tmp, f"run-{seed}")
        return ai_driver.run_ai_game(
            rules, seed, f"v04test{seed}", players, out,
            provider=provider, config=dict(CONFIG), **kwargs), out


class TestMockGames(DriverTestBase):
    def test_four_decisions_mock_game_completes_and_replays(self):
        summary, out = self.run_game(load_rules(V03_BASE), seed=4400)
        self.assertEqual(summary["status"], "finished")
        self.assertEqual(summary["decisions"]["invalid"], 0)
        self.assertGreater(summary["decisions"]["applied"], 40)
        self.assertTrue(os.path.exists(os.path.join(out, "result.json")))
        decisions_log = [json.loads(line) for line in
                         open(os.path.join(out, "decisions.jsonl"))]
        self.assertEqual(len(decisions_log),
                         summary["decisions"]["applied"])
        for record in decisions_log:
            for key in ("game_id", "turn_id", "player", "observation_hash",
                        "candidates", "chosen_action", "applied_action",
                        "metadata", "selected_mode", "config_hash"):
                self.assertIn(key, record)
        import subprocess
        proc = subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "sim.py"), "replay",
             "--run", out, "--verify"],
            capture_output=True, text=True, cwd=BASE_DIR)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"verified": true', proc.stdout)

    def test_mixed_policies_game(self):
        players = {"P0": "decisions", "P1": "tactical",
                   "P2": "balanced", "P3": "greedy"}
        summary, _ = self.run_game(load_rules(V03_BASE), seed=4402,
                                   players=players)
        self.assertEqual(summary["status"], "finished")
        self.assertIn(summary["winner"], ai_driver.SEATS)

    def test_run_dir_collision_rejected(self):
        summary, out = self.run_game(load_rules(V03_BASE), seed=4403,
                                     players={"P0": "balanced",
                                              "P1": "balanced",
                                              "P2": "balanced",
                                              "P3": "balanced"})
        with self.assertRaises(FileExistsError):
            self.run_game(load_rules(V03_BASE), seed=4403,
                          players={"P0": "balanced", "P1": "balanced",
                                   "P2": "balanced", "P3": "balanced"},
                          provider="mock")

    def test_live_requires_explicit_budget(self):
        with self.assertRaises(ValueError):
            self.run_game(provider="live")


class TestInformationBoundary(DriverTestBase):
    def test_hidden_sentinel_never_reaches_provider_or_logs(self):
        rules = load_rules(V03_BASE)
        sentinel = "SENTINEL-HIDDEN-9f3a"
        real_new_game = engine.new_game

        def planted_new_game(*args, **kwargs):
            state = real_new_game(*args, **kwargs)
            state["secret_sentinel"] = sentinel  # hidden engine field
            state["rng"]["placement"][1][0] = 123456789  # raw RNG blob
            return state

        stub = RecordingStub()
        out = os.path.join(self.tmp, "sentinel")
        with mock.patch.object(engine, "new_game",
                               side_effect=planted_new_game):
            summary = ai_driver.run_ai_game(
                rules, 4404, "v04sentinel",
                {p: "decisions" for p in ai_driver.SEATS}, out,
                provider="live", config=dict(CONFIG), live_client=stub,
                max_decisions_calls=6, max_cost_usd=1.0)
        # Budget stop expected: the game cannot finish inside 6 calls.
        # `attempted` counts turns that reached the provider boundary,
        # including the one blocked by the cap; budget.calls is the
        # authoritative count of requests actually sent.
        self.assertEqual(summary["budget"]["calls"], 6)
        self.assertEqual(summary["decisions"]["attempted"], 7)
        self.assertIsNotNone(summary["incomplete_reason"])
        for request in stub.requests:
            blob = json.dumps(request)
            self.assertNotIn(sentinel, blob)
            self.assertNotIn("secret_sentinel", blob)
        log_blob = open(os.path.join(out, "decisions.jsonl")).read()
        self.assertNotIn(sentinel, log_blob)
        self.assertNotIn("secret_sentinel", log_blob)
        # state.json holds it, the model side never does.
        self.assertIn(sentinel,
                      open(os.path.join(out, "state.json")).read())


class TestSingleLegalAction(DriverTestBase):
    def test_single_legal_action_skips_provider(self):
        rules = load_rules(V03_BASE)
        real_observe = engine.observe

        def doctored_observe(state, player):
            # Every decisions turn sees exactly one legal action, so
            # the driver must never call the provider.
            obs = real_observe(state, player)
            obs = dict(obs)
            obs["legal_actions"] = obs["legal_actions"][:1]
            return obs

        out = os.path.join(self.tmp, "single")
        stub = RecordingStub()
        with mock.patch.object(engine, "observe",
                               side_effect=doctored_observe):
            summary = ai_driver.run_ai_game(
                rules, 4405, "v04single",
                {p: "decisions" for p in ai_driver.SEATS}, out,
                provider="live", config=dict(CONFIG), live_client=stub,
                max_decisions_calls=1, max_cost_usd=1.0)
        self.assertEqual(summary["status"], "finished")
        self.assertEqual(summary["decisions"]["attempted"], 0)
        self.assertEqual(summary["decisions"]["single_action"],
                         summary["decisions"]["applied"])
        self.assertEqual(len(stub.requests), 0)  # no API call made
        log = json.loads(open(os.path.join(out, "decisions.jsonl"))
                         .readline())
        self.assertEqual(log["reason_code"], "single_legal_action")


class TestBudgetStop(DriverTestBase):
    def test_budget_stop_marks_game_incomplete(self):
        stub = RecordingStub()
        out = os.path.join(self.tmp, "budget")
        summary = ai_driver.run_ai_game(
            load_rules(V03_BASE), 4406, "v04budget",
            {p: "decisions" for p in ai_driver.SEATS}, out,
            provider="live", config=dict(CONFIG), live_client=stub,
            max_decisions_calls=3, max_cost_usd=1.0)
        self.assertEqual(summary["status"], "in_progress")
        self.assertIn("budget", summary["incomplete_reason"])
        self.assertEqual(summary["budget"]["calls"], 3)
        self.assertEqual(summary["decisions"]["attempted"], 4)
        self.assertFalse(os.path.exists(os.path.join(out, "result.json")))
        self.assertTrue(os.path.exists(os.path.join(out, "incomplete.json")))
        # Partial engine state preserved and resumable.
        state = engine.load_run(out)
        self.assertEqual(state["status"], "in_progress")
        self.assertEqual(len(state["events"]), 3)


class TestTacticalPolicy(unittest.TestCase):
    def _obs(self, rules=None, **over):
        rules = rules or load_rules(V03_BASE)
        state = engine.new_game(rules, 7, "tt")
        state["phase"] = 2
        for p in state["players"].values():
            p["equipment"] = sorted(rules["equipment"])
        me = state["players"][state["active_player"]]
        me["pos"] = [2, 4]
        me["seals"] = over.get("seals", ["cellars", "peristyle"])
        me["hits"] = over.get("hits", 1)
        me["glory"] = over.get("glory", 1)
        if "target_pos" in over:
            other = next(p for p in state["players"]
                         if p != state["active_player"])
            state["players"][other]["pos"] = list(over["target_pos"])
        state["current_roll"] = over.get("roll", 2)
        return engine.observe(state, state["active_player"])

    def test_winning_emperor_attack_beats_duel(self):
        # The exact trap `aggressive` falls into: duel offered alongside
        # a game-winning attack. Tactical must attack.
        obs = self._obs(target_pos=[2, 3])
        obs = dict(obs)
        obs["legal_actions"] = [
            a for a in obs["legal_actions"]
            if a["kind"] in ("attack_emperor", "duel")]
        self.assertTrue(any(a["kind"] == "duel" for a in obs["legal_actions"]))
        action_id, reason = tactical_policy.choose(obs, load_rules(V03_BASE))
        self.assertEqual(reason, "emperor_attack_spend")

    def test_spends_glory_only_when_it_matters(self):
        obs = self._obs(glory=1)
        obs = dict(obs)
        obs["legal_actions"] = [
            a for a in obs["legal_actions"] if a["kind"] == "attack_emperor"]
        rules = load_rules(V03_BASE)
        p_free = candidate_actions.contest_probability(2, 2, False)
        p_paid = candidate_actions.contest_probability(4, 2, False)
        self.assertGreaterEqual(p_paid - p_free, 0.15)
        _, reason = tactical_policy.choose(obs, rules)
        self.assertEqual(reason, "emperor_attack_spend")

    def test_seal_before_duel(self):
        obs = self._obs(hits=0, seals=["cellars"], glory=2)
        obs = dict(obs)
        obs["legal_actions"] = [
            a for a in obs["legal_actions"]
            if a["kind"] in ("attempt_seal", "duel")]
        kinds = {a["kind"] for a in obs["legal_actions"]}
        self.assertIn("attempt_seal", kinds)
        _, reason = tactical_policy.choose(obs, load_rules(V03_BASE))
        self.assertTrue(reason.startswith("seal"), reason)

    def test_duel_needs_edge_and_threat(self):
        obs = self._obs(hits=0, target_pos=[0, 0])
        obs["players"][obs["viewer"]]["seals"] = ["cellars", "peristyle"]
        obs = dict(obs)
        obs["legal_actions"] = [
            a for a in obs["legal_actions"]
            if a["kind"] in ("duel", "move")]
        _, reason = tactical_policy.choose(obs, load_rules(V03_BASE))
        self.assertEqual(reason, "advance")  # far target, no threat

    def test_version_frozen(self):
        self.assertEqual(tactical_policy.TACTICAL_VERSION, "tactical-v04.1")


if __name__ == "__main__":
    unittest.main()
