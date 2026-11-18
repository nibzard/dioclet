# ABOUTME: Match runner tests: config validation, budget, retry, logging shape.
# ABOUTME: All provider doubles are test-only and injected via provider_factory.

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arena import engine_adapter, match as match_mod
from arena.providers import Decision, TransportError

ARENA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ARENA_DIR, "..", "rules",
                          "imperial-rivals-v0.10.2.json")
DECISION_FIELDS = {"seq", "round", "turn_id", "phase", "seat", "provider",
                   "model", "action_id", "action_kind", "action_summary",
                   "p_chosen", "latency_ms", "cost_usd", "usage", "attempt",
                   "reason", "legal_count", "candidate_count"}


def tiny_rules(tmp_path, palace_rounds=1, succession_rounds=1, reveal_all=False):
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        rules = json.load(fh)
    rules["palace"]["max_rounds"] = palace_rounds
    rules["succession"]["max_rounds"] = succession_rounds
    if reveal_all:
        # Starts the game with every treasure face up, so scripted play
        # sees a fully revealed board from the first turn.
        rules["treasures"]["start_face_up"] = 6
    path = tmp_path / "tiny_rules.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    return str(path)


def make_config(rules_path, seed=7, provider="balanced", budget=None,
                monkeypatch=None):
    if provider in ("jev", "openai", "clef", "pplx") and monkeypatch:
        for var in ("TYPESAFE_API_KEY", "OPENAI_API_KEY",
                    "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID",
                    "PERPLEXITY_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    return match_mod.make_config(
        rules_path, seed,
        [{"provider": provider} for _ in range(4)], budget)


class FirstLegal:
    name = "scripted"
    model = "double"
    timeout_s = 0.0

    def __init__(self):
        self.calls = 0

    def decide(self, view):
        self.calls += 1
        first = view.observation["legal_actions"][0]["action_id"]
        return Decision(action_id=first,
                        probabilities={first: 0.62},
                        latency_ms=12.0, cost_usd=0.00004,
                        usage={"input_tokens": 40})


class Scripted:
    """Steps: an Exception to raise, 'illegal', or 'legal' (default)."""

    name = "scripted"
    model = "double"
    timeout_s = 0.0

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = 0

    def decide(self, view):
        self.calls += 1
        step = self.steps.pop(0) if self.steps else "legal"
        if isinstance(step, Exception):
            raise step
        first = view.observation["legal_actions"][0]["action_id"]
        if step == "illegal":
            return Decision(action_id="zzz0000")
        return Decision(action_id=first, probabilities={first: 0.62})


class FailIfCalled:
    name = "uncalled"
    model = "double"
    timeout_s = 0.0

    def decide(self, view):
        raise AssertionError("provider must not be called on this match")


def read_lines(run_dir):
    with open(os.path.join(run_dir, "match.jsonl"), "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_match_file(tmp_path, doc):
    path = tmp_path / "match.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

def test_rejects_three_seats(tmp_path):
    doc = {"rules": "../rules/imperial-rivals-v0.10.2.json", "seed": 1,
           "seats": [{"provider": "balanced"} for _ in range(3)]}
    with pytest.raises(match_mod.MatchConfigError, match="exactly 4"):
        match_mod.load_match(write_match_file(tmp_path, doc))


def test_rejects_unknown_provider(tmp_path):
    doc = {"rules": "../rules/imperial-rivals-v0.10.2.json", "seed": 1,
           "seats": [{"provider": "deep-blue"} for _ in range(4)]}
    with pytest.raises(match_mod.MatchConfigError, match="unknown provider"):
        match_mod.load_match(write_match_file(tmp_path, doc))


def test_rejects_missing_rules_file(tmp_path):
    doc = {"rules": "rules/nope.json", "seed": 1,
           "seats": [{"provider": "balanced"} for _ in range(4)]}
    with pytest.raises(match_mod.MatchConfigError, match="not found"):
        match_mod.load_match(write_match_file(tmp_path, doc))


def test_rejects_remote_seat_without_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    doc = {"rules": "../rules/imperial-rivals-v0.10.2.json", "seed": 1,
           "seats": [{"provider": "jev"} for _ in range(4)]}
    with pytest.raises(match_mod.MatchConfigError,
                       match="TYPESAFE_API_KEY"):
        match_mod.load_match(write_match_file(tmp_path, doc))


def test_rejects_unknown_top_level_key(tmp_path):
    doc = {"rules": "../rules/imperial-rivals-v0.10.2.json", "seed": 1,
           "seats": [{"provider": "balanced"} for _ in range(4)],
           "seeds": 2}
    with pytest.raises(match_mod.MatchConfigError, match="seeds"):
        match_mod.load_match(write_match_file(tmp_path, doc))


def test_rejects_negative_budget(tmp_path):
    doc = {"rules": "../rules/imperial-rivals-v0.10.2.json", "seed": 1,
           "seats": [{"provider": "balanced"} for _ in range(4)],
           "budget": {"max_calls": -1}}
    with pytest.raises(match_mod.MatchConfigError, match="max_calls"):
        match_mod.load_match(write_match_file(tmp_path, doc))


# ---------------------------------------------------------------------------
# Runner behaviour
# ---------------------------------------------------------------------------

def test_full_local_match_runs_and_logs_shape(tmp_path):
    config = make_config(tiny_rules(tmp_path, reveal_all=True), seed=7,
                         provider="balanced")
    run_dir = str(tmp_path / "run")
    summary = match_mod.run_match(config, run_dir)
    assert summary["incomplete"] is False
    assert summary["outcome"] in ("win", "draw")
    lines = read_lines(run_dir)
    assert lines[0]["type"] == "match_start"
    assert lines[0]["seed"] == 7
    assert lines[0]["game_id"].startswith("arena-7-")
    assert len(lines[0]["seats"]) == 4
    assert lines[-1]["type"] == "result"
    decisions = [line for line in lines if line["type"] == "decision"]
    assert decisions
    for line in decisions:
        assert DECISION_FIELDS <= set(line)
        assert line["action_summary"]
        assert line["attempt"] in (1, 2)
    assert lines[-1]["outcome"] == summary["outcome"]
    assert set(lines[-1]["seats"]) == {"P0", "P1", "P2", "P3"}


def test_budget_call_cap_stops_match(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         budget={"max_calls": 3, "max_usd": 0.0},
                         monkeypatch=monkeypatch)
    double = FirstLegal()
    run_dir = str(tmp_path / "run")
    summary = match_mod.run_match(config, run_dir,
                                  provider_factory=lambda seat: double)
    assert summary["incomplete"] is True
    assert double.calls == 3
    lines = read_lines(run_dir)
    failures = [line for line in lines if line["type"] == "failure"]
    assert len(failures) == 1
    assert failures[0]["error_class"] == "BudgetExceeded"
    assert failures[0]["turn_id"] > 0
    result = lines[-1]
    assert result["type"] == "result"
    assert result["incomplete"] is True
    assert sum(seat["calls"] for seat in result["seats"].values()) == 3
    assert "BudgetExceeded" in result["incomplete_reason"]


def test_transport_error_once_then_success_retries(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    double = Scripted([TransportError("boom")])
    summary = match_mod.run_match(config, str(tmp_path / "run"),
                                  provider_factory=lambda seat: double)
    assert summary["incomplete"] is False
    decisions = [line for line in read_lines(str(tmp_path / "run"))
                 if line["type"] == "decision"]
    assert any(line["attempt"] == 2 and line["p_chosen"] == 0.62
               for line in decisions)


def test_rate_limit_wait_is_honored_before_the_retry(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    double = Scripted([TransportError("HTTP 429: rate limited",
                                      retry_after_s=9.0)])
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(match_mod.time, "sleep", fake_sleep)
    summary = match_mod.run_match(config, str(tmp_path / "run"),
                                  provider_factory=lambda seat: double)
    assert summary["incomplete"] is False
    assert sleeps == [10.0]
    waits = [a["waited_s"] for line in read_lines(str(tmp_path / "run"))
             if line["type"] == "decision" for a in line["attempts"]
             if "waited_s" in a]
    assert waits == [10.0]


def test_rate_limit_wait_is_capped(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    double = Scripted([TransportError("HTTP 429: rate limited",
                                      retry_after_s=500.0)])
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(match_mod.time, "sleep", fake_sleep)
    summary = match_mod.run_match(config, str(tmp_path / "run"),
                                  provider_factory=lambda seat: double)
    assert summary["incomplete"] is False
    assert sleeps == [60.0]


def test_illegal_answer_once_then_legal_retries(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    double = Scripted(["illegal"])
    summary = match_mod.run_match(config, str(tmp_path / "run"),
                                  provider_factory=lambda seat: double)
    assert summary["incomplete"] is False
    decisions = [line for line in read_lines(str(tmp_path / "run"))
                 if line["type"] == "decision"]
    assert any(line["attempt"] == 2 for line in decisions)


def test_failure_twice_stops_match_with_details(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    double = Scripted([TransportError("timeout one"), "illegal"])
    run_dir = str(tmp_path / "run")
    summary = match_mod.run_match(config, run_dir,
                                  provider_factory=lambda seat: double)
    assert summary["incomplete"] is True
    lines = read_lines(run_dir)
    failure = next(line for line in lines if line["type"] == "failure")
    assert failure["provider"] == "scripted"
    assert failure["model"] == "double"
    assert failure["seat"] in ("P0", "P1", "P2", "P3")
    assert failure["error_class"] == "InvalidAnswerError"
    assert "illegal action_id" in failure["error"]
    assert failure["turn_id"] > 0
    assert lines[-1]["type"] == "result"
    assert lines[-1]["incomplete"] is True
    assert len(lines[-1]["seats"][failure["seat"]]["errors"]) == 1


def test_non_provider_error_propagates(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    double = Scripted([ValueError("bot bug")])
    with pytest.raises(ValueError, match="bot bug"):
        match_mod.run_match(config, str(tmp_path / "run"),
                            provider_factory=lambda seat: double)


def test_single_legal_action_skips_provider(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    real_observe = engine_adapter.observe

    def one_action_observe(state):
        obs = dict(real_observe(state))
        obs["legal_actions"] = obs["legal_actions"][:1]
        return obs

    monkeypatch.setattr(engine_adapter, "observe", one_action_observe)
    double = FailIfCalled()
    summary = match_mod.run_match(config, str(tmp_path / "run"),
                                  provider_factory=lambda seat: double)
    assert summary["incomplete"] is False
    decisions = [line for line in read_lines(str(tmp_path / "run"))
                 if line["type"] == "decision"]
    assert decisions
    for line in decisions:
        assert line["attempt"] == 0
        assert line["reason"] == "single_legal_action"
        assert line["legal_count"] == 1


# ---------------------------------------------------------------------------
# Training-grade log
# ---------------------------------------------------------------------------

class Exchanging:
    """Fails once with a recorded exchange, then answers with one."""

    name = "scripted"
    model = "double"
    timeout_s = 0.0

    def __init__(self):
        self.calls = 0

    def decide(self, view):
        self.calls += 1
        if self.calls == 1:
            raise TransportError("boom", exchange={
                "request": {"n": 1}, "response": None})
        first = view.observation["legal_actions"][0]["action_id"]
        return Decision(action_id=first, probabilities={first: 0.62},
                        confidence=0.4,
                        exchange={"request": {"n": self.calls},
                                  "response": {"body": {"ok": True}}})


class InterruptAfter:
    name = "scripted"
    model = "double"
    timeout_s = 0.0

    def __init__(self, calls):
        self.left = calls

    def decide(self, view):
        if self.left == 0:
            raise KeyboardInterrupt
        self.left -= 1
        return Decision(action_id=view.observation["legal_actions"][0]
                        ["action_id"])


def test_match_start_records_schema_and_full_rules(tmp_path):
    config = make_config(tiny_rules(tmp_path, reveal_all=True), seed=7)
    run_dir = str(tmp_path / "run")
    match_mod.run_match(config, run_dir)
    start = read_lines(run_dir)[0]
    assert start["schema"] == match_mod.LOG_SCHEMA == "arena-match-v3"
    assert start["rules"]["doc"] == config.rules


def test_every_decision_is_a_complete_training_example(tmp_path):
    config = make_config(tiny_rules(tmp_path, reveal_all=True), seed=7)
    run_dir = str(tmp_path / "run")
    match_mod.run_match(config, run_dir)
    decisions = [line for line in read_lines(run_dir)
                 if line["type"] == "decision"]
    assert decisions
    for line in decisions:
        legal = {a["action_id"] for a in line["observation"]["legal_actions"]}
        assert line["action_id"] in legal
        assert line["observation"]["active_player"] == line["seat"]
        assert line["projection"]
        assert all("description" in c for c in line["candidates"])
        assert {"probabilities", "confidence", "attempts"} <= set(line)
        assert line["play"]["action_id"] == line["action_id"]
        assert line["play"]["player"] == line["seat"]


def test_remote_attempts_keep_request_response_and_error(tmp_path,
                                                         monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    run_dir = str(tmp_path / "run")
    match_mod.run_match(config, run_dir,
                        provider_factory=lambda seat: Exchanging())
    first = next(line for line in read_lines(run_dir)
                 if line["type"] == "decision" and line["attempt"] == 2)
    failed, ok = first["attempts"]
    assert failed == {"attempt": 1, "ok": False,
                      "error_class": "TransportError", "error": "boom",
                      "exchange": {"request": {"n": 1}, "response": None}}
    assert ok["ok"] is True
    assert ok["exchange"]["response"] == {"body": {"ok": True}}
    assert first["confidence"] == 0.4
    assert first["probabilities"] == {first["action_id"]: 0.62}


def test_failure_line_keeps_what_the_seat_saw(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    double = Scripted([TransportError("one"), TransportError("two")])
    run_dir = str(tmp_path / "run")
    match_mod.run_match(config, run_dir,
                        provider_factory=lambda seat: double)
    failure = next(line for line in read_lines(run_dir)
                   if line["type"] == "failure")
    assert failure["observation"]["active_player"] == failure["seat"]
    assert failure["candidates"]
    assert [a["error"] for a in failure["attempts"]] == ["one", "two"]


def test_result_line_keeps_the_engine_result(tmp_path):
    config = make_config(tiny_rules(tmp_path, reveal_all=True), seed=7)
    run_dir = str(tmp_path / "run")
    summary = match_mod.run_match(config, run_dir)
    result = read_lines(run_dir)[-1]
    assert result["engine_result"]["outcome"] == summary["outcome"]


def test_interrupt_writes_an_interrupted_result(tmp_path, monkeypatch):
    config = make_config(tiny_rules(tmp_path), provider="jev",
                         monkeypatch=monkeypatch)
    run_dir = str(tmp_path / "run")
    double = InterruptAfter(2)
    summary = match_mod.run_match(config, run_dir,
                                  provider_factory=lambda seat: double)
    assert summary["outcome"] == "interrupted"
    lines = read_lines(run_dir)
    assert lines[-1]["type"] == "result"
    assert lines[-1]["incomplete"] is True
    assert lines[-1]["incomplete_reason"] == "interrupted by the user"
    assert not [name for name in os.listdir(os.path.join(run_dir, "engine"))
                if name.endswith(".tmp")]
