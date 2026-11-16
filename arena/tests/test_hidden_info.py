# ABOUTME: Hidden-information boundary test, ported from the repo sentinel test.
# ABOUTME: A secret planted in engine state must never reach a provider payload or a log.

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arena import match as match_mod
from arena.providers import Decision

ARENA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ARENA_DIR, "..", "rules",
                          "imperial-rivals-v0.10.2.json")
SENTINEL = "SENTINEL-HIDDEN-9f3a"


class RecordingProvider:
    name = "recorder"
    model = "double"
    timeout_s = 0.0

    def __init__(self):
        self.calls = 0
        self.payloads = []

    def decide(self, view):
        self.calls += 1
        self.payloads.append(
            json.dumps(view.observation, sort_keys=True, default=str)
            + json.dumps(view.projection, sort_keys=True, default=str)
            + json.dumps(view.candidates, sort_keys=True, default=str))
        first = view.observation["legal_actions"][0]["action_id"]
        return Decision(action_id=first)


class SentinelInjector:
    """Plants the sentinel into live engine state once, before any call."""

    def __init__(self):
        self.injected = False

    def on_turn_start(self, state, view):
        if not self.injected:
            pid = next(iter(state["players"]))
            state["secret_sentinel"] = SENTINEL
            # Hidden per-player detail: no projection or feature may carry it.
            state["players"][pid]["stats"]["secret_sentinel"] = SENTINEL
            self.injected = True


def test_hidden_sentinel_never_reaches_provider_or_logs(tmp_path, monkeypatch):
    for var in ("TYPESAFE_API_KEY", "OPENAI_API_KEY", "CLOUDFLARE_API_TOKEN",
                "CLOUDFLARE_ACCOUNT_ID", "PERPLEXITY_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        rules = json.load(fh)
    rules["palace"]["max_rounds"] = 1
    rules["succession"]["max_rounds"] = 1
    tiny = tmp_path / "tiny.json"
    tiny.write_text(json.dumps(rules), encoding="utf-8")
    config = match_mod.make_config(str(tiny), 5,
                                   [{"provider": "jev"} for _ in range(4)],
                                   {"max_calls": 0, "max_usd": 0.0})
    recorder = RecordingProvider()
    injector = SentinelInjector()
    run_dir = str(tmp_path / "run")
    summary = match_mod.run_match(config, run_dir, hooks=injector,
                                  provider_factory=lambda seat: recorder)

    assert injector.injected is True
    assert recorder.calls > 0
    for payload in recorder.payloads:
        assert SENTINEL not in payload
        assert "secret_sentinel" not in payload
        assert "stats" not in payload
        assert "equipment_bonus" not in payload
    with open(os.path.join(run_dir, "match.jsonl"), "r",
              encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]
    for row in rows:
        if row["type"] == "result":
            # engine.result publishes final player-stat diagnostics; only
            # the provider-facing rows must keep hidden state out.
            continue
        blob = json.dumps(row, sort_keys=True)
        assert SENTINEL not in blob
        assert "secret_sentinel" not in blob
        assert "stats" not in blob
        assert "equipment_bonus" not in blob
    with open(os.path.join(run_dir, "engine", "state.json"), "r",
              encoding="utf-8") as fh:
        state_blob = fh.read()
    assert SENTINEL in state_blob
    assert summary["incomplete"] is False
