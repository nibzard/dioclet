# ABOUTME: One live contract call per remote provider, gated behind env flags.
# ABOUTME: Set ARENA_LIVE_CONTRACT=1 and the provider keys to run these.

import os
from pathlib import Path

import pytest

from arena import engine_adapter
from arena.providers import REQUIRED_ENV, TurnView, build_provider
from arena.rules_loader import load_rules_strict

RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "v0102.json"


def _first_turn_view():
    rules = load_rules_strict(RULES_PATH)
    state = engine_adapter.new_game(rules, 42, "live-contract")
    obs = engine_adapter.observe(state)
    projection = engine_adapter.projection(obs, rules)
    candidates, _ = engine_adapter.candidates(obs, rules)
    return TurnView(observation=obs, projection=projection,
                    candidates=candidates[:3], rules=rules)


@pytest.mark.parametrize("provider", ["openai", "jev", "clef", "pplx", "gateway"])
def test_live_contract_call(provider, capsys):
    if os.environ.get("ARENA_LIVE_CONTRACT") != "1":
        pytest.skip("set ARENA_LIVE_CONTRACT=1 to spend money")
    missing = [name for name in REQUIRED_ENV[provider]
               if not os.environ.get(name)]
    if missing:
        pytest.skip(f"no keys: {', '.join(missing)}")
    seat = build_provider(provider)
    view = _first_turn_view()
    offered = {c["action_id"] for c in view.candidates}
    decision = seat.decide(view)
    assert decision.action_id in offered
    assert decision.usage, "usage missing from the live answer"
    assert decision.cost_usd > 0
    with capsys.disabled():
        print(f"\n[live] {provider}/{seat.model} -> {decision.action_id} "
              f"p={decision.probabilities or '{}'} "
              f"{decision.latency_ms}ms ${decision.cost_usd:.6f} "
              f"usage={decision.usage}")
