"""Offline provider tests: mock, playback, and a stubbed live client.

No test in this file touches the network. The "live" provider is
exercised against a stub client that records requests and returns
canned response objects shaped like the documented Decisions schema.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidate_actions
import decisions_policy
import engine

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "rules_baseline.json")


def load_rules():
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def sample_projection_and_candidates():
    rules = load_rules()
    state = engine.new_game(rules, 42, "dp")
    obs = engine.observe(state, state["active_player"])
    projection = candidate_actions.project_observation(obs, rules)
    candidates, _ = candidate_actions.build_candidates(obs, rules)
    return projection, candidates


CONFIG = {"provider": "live", "model": "gpt-6-luna", "candidate_cap": 16,
          "prompt_version": "v04-1", "selection_mode": "top",
          "max_retries": 1, "timeout_seconds": 20,
          "fallback_on_live_error": False, "persona": "win_focused"}


class Ans:  # lightweight response shapers
    pass


def make_response(choice, probabilities=None, confidence=0.9,
                  answer_type="choice", name="best_action",
                  input_tokens=1500, cached=0, cache_write=0,
                  request_id="req_test_1", model="gpt-6-luna"):
    answer = Ans()
    answer.type = answer_type
    answer.name = name
    answer.choice = choice
    answer.probabilities = probabilities
    answer.confidence = confidence
    response = Ans()
    response.answers = [answer]
    response.model = model
    response.id = request_id
    usage = Ans()
    usage.input_tokens = input_tokens
    usage.output_tokens = 0
    usage.total_tokens = input_tokens
    details = Ans()
    details.cached_tokens = cached
    details.cache_write_tokens = cache_write
    usage.input_tokens_details = details
    response.usage = usage
    return response


class StubClient:
    """Records decisions.create kwargs; returns scripted responses."""

    def __init__(self, responses):
        self.decisions = self
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class TestMockAndPlayback(unittest.TestCase):
    def test_mock_deterministic(self):
        projection, candidates = sample_projection_and_candidates()
        provider = decisions_policy.MockProvider()
        a = provider.decide(projection, candidates, CONFIG)
        b = provider.decide(projection, candidates, CONFIG)
        self.assertEqual(a, b)
        self.assertIn(a.action_id, {c["action_id"] for c in candidates})
        self.assertEqual(a.metadata["provider"], "mock")
        self.assertEqual(a.metadata["estimated_cost_usd"], 0.0)

    def test_playback_replays_recorded_choice(self):
        projection, candidates = sample_projection_and_candidates()
        key = (projection["game_id"], projection["turn"]["id"],
               projection["turn"]["player"])
        chosen = candidates[0]["action_id"]
        provider = decisions_policy.PlaybackProvider({key: chosen})
        decision = provider.decide(projection, candidates, CONFIG)
        self.assertEqual(decision.action_id, chosen)
        self.assertEqual(decision.reason, "playback_record")

    def test_playback_rejects_missing_or_illegal(self):
        projection, candidates = sample_projection_and_candidates()
        provider = decisions_policy.PlaybackProvider({("x", 1, "P9"): "a1"})
        with self.assertRaises(decisions_policy.InvalidAnswerError):
            provider.decide(projection, candidates, CONFIG)


class TestLiveRequestSchema(unittest.TestCase):
    def test_request_matches_documented_schema(self):
        projection, candidates = sample_projection_and_candidates()
        provider = decisions_policy.LiveProvider(client=StubClient([]))
        request = provider.build_request(projection, candidates)
        self.assertEqual(request["model"], "gpt-6-luna")
        self.assertIsInstance(request["questions"], list)
        self.assertEqual(len(request["questions"]), 1)
        question = request["questions"][0]
        self.assertEqual(question["type"], "choice")
        self.assertEqual(question["name"], "best_action")
        choices = question["choices"]
        self.assertIsInstance(choices, list)
        self.assertGreaterEqual(len(choices), 2)
        self.assertLessEqual(len(choices), 255)
        self.assertEqual(choices[0].keys(), {"value", "description"})
        self.assertEqual([c["value"] for c in choices],
                         [c["action_id"] for c in candidates])
        message = request["input"][0]
        self.assertEqual(message["role"], "user")
        types = [part["type"] for part in message["content"]]
        self.assertEqual(types, ["input_text", "input_json"])
        self.assertEqual(message["content"][1]["data"], projection)

    def test_request_carries_no_secrets(self):
        projection, candidates = sample_projection_and_candidates()
        provider = decisions_policy.LiveProvider(client=StubClient([]))
        blob = json.dumps(provider.build_request(projection, candidates))
        for secret in ("sk-", "OPENAI_API_KEY", "Authorization"):
            self.assertNotIn(secret, blob)


class TestLiveParsing(unittest.TestCase):
    def _decide(self, response, budget=None, config=None,
                candidates=None):
        projection, cands = sample_projection_and_candidates()
        if candidates is None:
            candidates = cands
        stub = StubClient([response])
        provider = decisions_policy.LiveProvider(client=stub)
        return provider.decide(projection, candidates,
                               config or CONFIG, budget), stub

    def test_successful_choice_parse(self):
        projection, candidates = sample_projection_and_candidates()
        chosen = candidates[0]["action_id"]
        other = candidates[1]["action_id"]
        probabilities = [{"value": c["action_id"],
                          "probability": 0.0}
                         for c in candidates]
        by_value = {p["value"]: p for p in probabilities}
        by_value[chosen]["probability"] = 0.7
        by_value[other]["probability"] = 0.3
        decision, stub = self._decide(
            make_response(chosen, probabilities, confidence=0.8,
                          input_tokens=2000, cached=512, cache_write=100),
            candidates=candidates)
        self.assertEqual(decision.action_id, chosen)
        self.assertEqual(decision.reason, "openai_decisions_choice")
        meta = decision.metadata
        self.assertEqual(meta["model"], "gpt-6-luna")
        self.assertEqual(meta["request_id"], "req_test_1")
        self.assertEqual(meta["usage"]["input_tokens"], 2000)
        self.assertEqual(meta["usage"]["cached_tokens"], 512)
        self.assertEqual(meta["usage"]["cache_write_tokens"], 100)
        self.assertAlmostEqual(meta["estimated_cost_usd"], 0.0002)
        self.assertEqual(meta["confidence"], 0.8)
        self.assertFalse(meta["probability_flags"])

    def test_refusal_raises(self):
        with self.assertRaises(decisions_policy.RefusalError):
            self._decide(make_response(None, answer_type="refusal"))

    def test_choice_outside_shortlist_rejected(self):
        with self.assertRaises(decisions_policy.InvalidAnswerError):
            self._decide(make_response("a9999"))

    def test_bad_answer_type_rejected(self):
        with self.assertRaises(decisions_policy.InvalidAnswerError):
            self._decide(make_response("a0001", answer_type="predicate"))

    def test_confidence_bounds_enforced(self):
        projection, candidates = sample_projection_and_candidates()
        with self.assertRaises(decisions_policy.InvalidAnswerError):
            self._decide(make_response(candidates[0]["action_id"],
                                       confidence=1.5))

    def test_probability_flags_logged_not_fatal(self):
        projection, candidates = sample_projection_and_candidates()
        chosen = candidates[0]["action_id"]
        other = candidates[1]["action_id"]
        bad = [{"value": chosen, "probability": 0.6},
               {"value": chosen, "probability": 0.2},    # duplicate
               {"value": other, "probability": 5.0}]     # out of range
        decision, _ = self._decide(make_response(chosen, bad))
        self.assertEqual(decision.action_id, chosen)  # choice unchanged
        self.assertTrue(decision.metadata["probability_flags"])

    def test_partial_coverage_flagged(self):
        projection, candidates = sample_projection_and_candidates()
        chosen = candidates[0]["action_id"]
        partial = [{"value": chosen, "probability": 1.0}]
        decision, _ = self._decide(make_response(chosen, partial))
        self.assertIn("partial_coverage",
                      " ".join(decision.metadata["probability_flags"]))


class TestBudgetAndRetry(unittest.TestCase):
    def test_call_cap_enforced_before_request(self):
        projection, candidates = sample_projection_and_candidates()
        stub = StubClient([make_response(candidates[0]["action_id"])])
        provider = decisions_policy.LiveProvider(client=stub)
        budget = decisions_policy.Budget(max_calls=1)
        provider.decide(projection, candidates, CONFIG, budget)
        with self.assertRaises(decisions_policy.BudgetExceededError):
            provider.decide(projection, candidates, CONFIG, budget)
        self.assertEqual(len(stub.requests), 1)  # second never sent

    def test_cost_cap_enforced_before_request(self):
        projection, candidates = sample_projection_and_candidates()
        # Actual usage (2M tokens -> $0.20) far exceeds the estimate;
        # the second call must stop on the recorded spend.
        stub = StubClient(
            [make_response(candidates[0]["action_id"],
                           input_tokens=2_000_000)])
        provider = decisions_policy.LiveProvider(client=stub)
        budget = decisions_policy.Budget(max_cost_usd=0.15)
        provider.decide(projection, candidates, CONFIG, budget)
        self.assertEqual(budget.calls, 1)
        self.assertAlmostEqual(budget.spent_estimate_usd, 0.20, places=4)
        with self.assertRaises(decisions_policy.BudgetExceededError):
            provider.decide(projection, candidates, CONFIG, budget)

    def test_input_token_cap(self):
        projection, candidates = sample_projection_and_candidates()
        stub = StubClient([])
        provider = decisions_policy.LiveProvider(client=stub)
        budget = decisions_policy.Budget(max_input_tokens=1)
        with self.assertRaises(decisions_policy.BudgetExceededError):
            provider.decide(projection, candidates, CONFIG, budget)
        self.assertEqual(stub.requests, [])

    def test_transient_failure_retried_once(self):
        projection, candidates = sample_projection_and_candidates()
        stub = StubClient([
            RuntimeError("connection reset"),
            make_response(candidates[0]["action_id"]),
        ])
        provider = decisions_policy.LiveProvider(client=stub)
        decision = provider.decide(projection, candidates, CONFIG)
        self.assertEqual(decision.action_id, candidates[0]["action_id"])
        self.assertEqual(len(stub.requests), 2)

    def test_persistent_failure_raises_unavailable(self):
        projection, candidates = sample_projection_and_candidates()
        stub = StubClient([RuntimeError("down"), RuntimeError("down")])
        provider = decisions_policy.LiveProvider(client=stub)
        with self.assertRaises(decisions_policy.LiveUnavailableError):
            provider.decide(projection, candidates, CONFIG)


class TestSelectionMode(unittest.TestCase):
    def test_top_mode(self):
        decision = decisions_policy.PlayerDecision(
            "a0001", "decisions", "openai_decisions_choice",
            {"provider": "live",
             "probabilities": [{"value": "a0001", "probability": 0.6},
                               {"value": "a0002", "probability": 0.4}],
             "probability_flags": []})
        action, mode = decisions_policy.select_action(decision, CONFIG)
        self.assertEqual((action, mode), ("a0001", "top"))

    def test_sample_mode_uses_policy_rng(self):
        import random
        decision = decisions_policy.PlayerDecision(
            "a0001", "decisions", "openai_decisions_choice",
            {"provider": "live",
             "probabilities": [{"value": "a0001", "probability": 1.0}],
             "probability_flags": []})
        rng = random.Random(7)
        action, mode = decisions_policy.select_action(
            decision, {"selection_mode": "sample"}, rng=rng)
        self.assertEqual(action, "a0001")
        self.assertEqual(mode, "sample")

    def test_sample_falls_back_without_valid_distribution(self):
        import random
        decision = decisions_policy.PlayerDecision(
            "a0001", "decisions", "openai_decisions_choice",
            {"provider": "live", "probabilities": [],
             "probability_flags": ["absent"]})
        action, mode = decisions_policy.select_action(
            decision, {"selection_mode": "sample"}, rng=random.Random(1))
        self.assertEqual((action, mode), ("a0001", "top_fallback"))


if __name__ == "__main__":
    unittest.main()
