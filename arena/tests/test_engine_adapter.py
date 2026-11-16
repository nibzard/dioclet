# ABOUTME: Tests for the Arena engine adapter: observation, candidates,
# ABOUTME: hidden-information hygiene, apply, and a headless game.
import json
import os

import pytest

from arena import engine_adapter

HERE = os.path.dirname(os.path.abspath(__file__))


def load_rules():
    arena_copy = os.path.join(HERE, "..", "rules", "v0102.json")
    if os.path.exists(arena_copy):
        path = arena_copy
    else:
        path = os.path.join(HERE, "..", "..", "rules_v0102_bigboard.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def rules():
    return load_rules()


def fresh_state(rules, seed=7):
    return engine_adapter.new_game(rules, seed, "adapter-test")


def test_observation_is_for_active_player(rules):
    state = fresh_state(rules)
    obs = engine_adapter.observe(state)
    assert obs["viewer"] == obs["active_player"] == state["active_player"]
    assert obs["legal_actions"]
    assert all("action_id" in a for a in obs["legal_actions"])


def test_candidates_are_legal_subset(rules):
    state = fresh_state(rules)
    obs = engine_adapter.observe(state)
    selected, excluded = engine_adapter.candidates(obs, rules)
    assert selected
    assert {c["action_id"] for c in selected} <= engine_adapter.legal_ids(obs)
    assert all(e.get("action_id") or "note" in e for e in excluded)


def test_projection_hides_unrevealed_mapping(rules):
    state = fresh_state(rules, seed=13)
    obs = engine_adapter.observe(state)
    blob = json.dumps(engine_adapter.projection(obs, rules), sort_keys=True)
    for name, item in state["district_equipment"].items():
        if name not in state["revealed"]:
            assert f'"{name}": "{item}"' not in blob


def test_apply_resolves_and_advances(rules):
    state = fresh_state(rules)
    obs = engine_adapter.observe(state)
    before_turn = state["turn_id"]
    before_player = state["active_player"]
    record = engine_adapter.apply(state, obs["legal_actions"][0]["action_id"],
                                  reason="first_legal")
    assert record["player"] == before_player
    assert state["turn_id"] > before_turn
    assert not engine_adapter.finished(state)


def test_headless_game_holds_invariants(rules):
    state = fresh_state(rules, seed=42)
    turns = 0
    while not engine_adapter.finished(state) and turns < 4000:
        obs = engine_adapter.observe(state)
        engine_adapter.apply(state, obs["legal_actions"][0]["action_id"])
        engine_adapter.check_invariants(state)
        turns += 1
    assert engine_adapter.finished(state)
    summary = engine_adapter.result(state)
    assert summary["outcome"] in ("win", "draw")
    assert summary["total_turns"] == turns
