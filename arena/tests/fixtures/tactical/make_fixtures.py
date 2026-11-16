# ABOUTME: Offline generator for the frozen tactical fixtures; plays seeded
# ABOUTME: bot games and freezes the first observation that meets each situation.
#
# Run from the repository root or the arena directory:
#   uv run python arena/tests/fixtures/tactical/make_fixtures.py
#
# The generator is not part of the shipped package and the tests never run
# it; the JSON files it wrote are the frozen fixtures. Re-run it only to
# re-freeze after an engine change.

import json
import os
import random
import sys

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_ARENA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
for _path in (_REPO_ROOT, _ARENA_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import engine
from arena import engine_adapter
from arena.providers import local, TurnView

RULES_PATH = os.path.join(_REPO_ROOT, "rules",
                          "imperial-rivals-v0.10.2.json")
HERE = os.path.dirname(os.path.abspath(__file__))
MAX_SEEDS = 400
LINEUPS = [
    ("tactical", "tactical", "tactical", "tactical"),
    ("aggressive", "aggressive", "aggressive", "aggressive"),
    ("tactical", "aggressive", "greedy", "collector"),
    ("balanced", "aggressive", "tactical", "early_support"),
]


def duel_ids_against(obs, player):
    return sorted(action["action_id"] for action in obs["legal_actions"]
                  if action["kind"] == "duel"
                  and action.get("target") == player)


def find_hits(obs):
    """Return {fixture key: correct id set} when the position matches."""
    hits = {}
    pending = obs.get("pending_claim")
    window = obs["progress"]["claim_window_rounds"]
    active = obs["active_player"]
    if pending and pending["player"] != active and window \
            and obs["round"] - pending["round"] == window:
        ids = duel_ids_against(obs, pending["player"])
        if ids:
            hits["cancel-winning-claim"] = ids
    if obs["phase"] == 2 and not pending:
        ids = sorted(action["action_id"] for action in obs["legal_actions"]
                     if action["kind"] == "proclaim")
        if ids:
            hits["proclaim-legal"] = ids
    if obs["phase"] == 2:
        ids = sorted(action["action_id"] for action in obs["legal_actions"]
                     if action["kind"] == "gain_support")
        if ids:
            hits["gain-support-affordable"] = ids
    return hits


DESCRIPTIONS = {
    "cancel-winning-claim": {
        "description":
            "A rival claim is pending and this round is its last: the "
            "claim wins when the last turn of this round ends. The seat "
            "is in duel range of the claimant.",
        "judgement":
            "Cancel the claim. Every duel against the claimant is correct; "
            "each one contests the claim before the window closes.",
    },
    "proclaim-legal": {
        "description":
            "Phase 2, no claim pending, and the seat stands on the "
            "checkpoint with enough support and Prestige to proclaim.",
        "judgement":
            "Proclaim. A claim starts the win clock, so the position that "
            "offers it should take it.",
    },
    "gain-support-affordable": {
        "description":
            "Phase 2, and the seat stands on a revealed card space that "
            "holds a faction the seat does not support yet, with Prestige "
            "to pay the support cost.",
        "judgement":
            "Gain the support. The engine only offers the action when the "
            "seat can pay, so every gain_support id is correct.",
    },
}

HIDDEN_KEYS = ("faction_sites", "district_equipment")


def assert_public(doc, name):
    """The fixture may hold public observation data only."""
    text = json.dumps(doc)

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in HIDDEN_KEYS, \
                    f"{name}: hidden-state key '{key}' in fixture"
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    card_spaces = doc["observation"]["board"].get("card_spaces")
    if card_spaces is not None:
        assert set(card_spaces) <= {"candidates", "revealed"}, \
            f"{name}: card_spaces carries more than the public reveal"


def freeze(key, obs, rules, correct_ids):
    candidates = engine_adapter.candidates(obs, rules)[0]
    candidate_ids = {c["action_id"] for c in candidates}
    missing = set(correct_ids) - candidate_ids
    assert not missing, f"{key}: correct ids not in the shortlist: {missing}"
    doc = {
        "name": key,
        "description": DESCRIPTIONS[key]["description"],
        "judgement": DESCRIPTIONS[key]["judgement"],
        "rules": "../rules/imperial-rivals-v0.10.2.json",
        "observation": json.loads(json.dumps(obs)),
        "candidates": json.loads(json.dumps(candidates)),
        "correct": sorted(correct_ids),
    }
    assert_public(doc, key)
    path = os.path.join(HERE, f"{key}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    print(f"froze {key}: seed {obs['seed']}, seat {obs['active_player']}, "
          f"turn {obs['turn_id']}, round {obs['round']} -> {path}")


def main():
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        rules = json.load(fh)
    remaining = set(DESCRIPTIONS)
    for seed in range(1, MAX_SEEDS + 1):
        lineup = LINEUPS[seed % len(LINEUPS)]
        state = engine.new_game(rules, seed, f"fixture-hunt-{seed}")
        bots = {f"P{i}": local.build(name, rng=random.Random(
                    f"fixture-hunt:{seed}:{i}"))
                for i, name in enumerate(lineup)}
        while not engine.is_finished(state):
            obs = engine_adapter.observe(state)
            for key, ids in find_hits(obs).items():
                if key in remaining:
                    freeze(key, obs, rules, ids)
                    remaining.discard(key)
            if not remaining:
                return
            seat = obs["active_player"]
            view = TurnView(observation=obs,
                            projection=engine_adapter.projection(obs, rules),
                            candidates=engine_adapter.candidates(obs, rules)[0],
                            rules=rules)
            engine_adapter.apply(state, bots[seat].decide(view).action_id,
                                 "fixture-hunt")
    missing = ", ".join(sorted(remaining))
    raise SystemExit(f"no position found for: {missing}")


if __name__ == "__main__":
    main()
