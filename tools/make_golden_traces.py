# ABOUTME: Golden-trace generator for the rules cleanup: plays seeded games
# ABOUTME: with the built-in bots and records name-neutral turn traces.
"""Build and regenerate the golden-trace fixtures for the rules cleanup.

Phase 0 of docs/rules-cleanup-plan.md records how the game behaves today.
Later phases rename engine vocabulary; they keep these traces equal. The
trace layer below maps engine state into its own neutral words. It never
writes raw engine keys into a trace.

Neutral trace schema (one JSON object per game, one line per game):

  game line    {"game": <0-based index>, "seed": <int>, "bots": [4 names],
                 "trace": [<turn record> ..., <result record>]}

  turn record  {"turn": <turn id>, "round": <round>, "phase": "palace" |
                 "succession", "player": <seat 0-3>, "kind": <verb>,
                 "to": "<x,y>", "target": <seat 0-3 or null>,
                 "dice": [<die rolls in roll order>],
                 "points": [<score per seat, after the turn>],
                 "positions": ["<x,y>" per seat, after the turn],
                 "items": [[<treasure name>, ...] per seat, sorted],
                 "support": {<faction>: [<seats that hold it>]}. Only a
                   faction that at least one seat holds appears,
                 "claim": [<checkpoint seat or null>,
                           <round the checkpoint was claimed or null>,
                           <pending-claim seat or null>,
                           <round the claim was proclaimed or null>,
                           [<seats that responded, sorted>]]}

  result rec.  {"kind": "result", "result": {"outcome": "win" | "draw",
                 "winner": <seat or null>, "end": "acclamation" |
                 "survived_window" | "timeout",
                 "rounds": {"palace": <n>, "succession": <n>},
                 "turns": {"palace": <n>, "succession": <n>, "total": <n>},
                 "points": [<final score per seat>]}}

Action verbs: move, explore, reveal, guard, search, support, claim,
proclaim, maintain, duel. Phase words: palace, succession. Score word:
points. Cell ids are plain "<x>,<y>" strings.

Sections marked "engine vocabulary adapter" read engine names. When a later
phase renames those names, update the adapter only. Its output must stay
the same.
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine  # noqa: E402
import policies  # noqa: E402

GENERATOR_VERSION = 1
GAMES = 200
SEED_BASE = 1000
SEATS = 4

# Every built-in succession bot except "tactical": that one names the old
# Emperor-game policy and does not read succession observations.
BOT_POOL = ("balanced", "balanced_se", "greedy", "aggressive", "random",
            "collector", "early_support", "prestige_farmer", "counterleader")

PHASE_NAMES = {1: "palace", 2: "succession"}

KIND_MAP = {
    "move": "move",
    "explore": "explore",
    "inspect": "reveal",
    "guard_post": "guard",
    "search_site": "search",
    "gain_support": "support",
    "claim_checkpoint": "claim",
    "proclaim": "proclaim",
    "maintain_claim": "maintain",
    "duel": "duel",
}

END_MAP = {
    "acclamation": "acclamation",
    "survived_window": "survived_window",
    "phase2_timeout": "timeout",
}

RULES_FILE = "rules/imperial-rivals-v0.10.2.json"

GOLDEN_DIR = os.path.join("tests", "fixtures", "golden")


def load_default_rules(root):
    """Return (rules, relative path) for the current default rules file."""
    return engine.load_rules(os.path.join(root, RULES_FILE)), RULES_FILE


# ---------------------------------------------------------------------------
# Engine vocabulary adapter. Reads engine key names; writes neutral ones.
# Later phases edit this section when the engine renames its vocabulary.
# ---------------------------------------------------------------------------

def _seat_index(pid):
    """Convert an engine seat id like 'P2' to the trace seat index 2."""
    return int(pid[1:])


def _cell_id(cell):
    """Convert an engine cell like [3, 4] to the trace cell id '3,4'."""
    return f"{cell[0]},{cell[1]}"


def _player_rows(state):
    """Per-seat player state, always in seat order P0..P3."""
    return [state["players"][f"P{i}"] for i in range(SEATS)]


def _score(pdata):
    """The per-player score. The palace game calls it glory; the
    succession game calls it prestige. The trace calls it points."""
    if "prestige" in pdata:
        return pdata["prestige"]
    return pdata["glory"]


def _points(state):
    return [_score(row) for row in _player_rows(state)]


def _positions(state):
    return [_cell_id(row["pos"]) for row in _player_rows(state)]


def _items(state):
    return [sorted(row.get("equipment", [])) for row in _player_rows(state)]


def _faction_names(state):
    config = state["rules"].get("succession") or {}
    return sorted(config.get("faction_cards", {}).get("factions") or [])


def _support(state):
    """Faction name to the seats that hold its support.

    Factions with no holder are absent; the trace keeps only live state.
    """
    holders = {name: [] for name in _faction_names(state)}
    for i, row in enumerate(_player_rows(state)):
        for faction in row.get("support", []):
            holders[faction].append(i)
    return {name: sorted(seats) for name, seats in holders.items() if seats}


def _claim(state):
    """Claim state as a fixed-order list: checkpoint seat, checkpoint
    round, pending-claim seat, claim round, responding seats."""
    pending = state.get("pending_claim")
    first = state.get("first_challenger")
    return [
        None if first is None else _seat_index(first),
        state.get("trigger_round"),
        None if pending is None else _seat_index(pending["player"]),
        None if pending is None else pending["round"],
        [] if pending is None
        else sorted(_seat_index(p) for p in pending["responded"]),
    ]


def _dice(record):
    """Every die rolled for the turn, in roll order: movement first,
    then any dice the action itself rolled."""
    rolls = list(record.get("movement_dice") or [])
    if not rolls and record.get("movement_die") is not None:
        rolls = [record["movement_die"]]
    return rolls + list(record.get("dice_used") or [])


# ---------------------------------------------------------------------------
# Neutral records
# ---------------------------------------------------------------------------

def neutral_turn(record, state):
    """One neutral trace record for one applied turn.

    `record` is the engine turn record; `state` is the game state after
    the engine advanced past the turn.
    """
    action = record["action"]
    target = action.get("target")
    return {
        "turn": record["turn_id"],
        "round": record["round"],
        "phase": PHASE_NAMES[record["phase"]],
        "player": _seat_index(record["player"]),
        "kind": KIND_MAP[action["kind"]],
        "to": _cell_id(action["destination"]),
        "target": None if target is None else _seat_index(target),
        "dice": _dice(record),
        "points": _points(state),
        "positions": _positions(state),
        "items": _items(state),
        "support": _support(state),
        "claim": _claim(state),
    }


def neutral_result(state):
    """The final trace record of a game."""
    res = engine.result(state)
    return {
        "kind": "result",
        "result": {
            "outcome": res["outcome"],
            "winner": (None if res["winner"] is None
                       else _seat_index(res["winner"])),
            "end": END_MAP[res["end_reason"]],
            "rounds": {"palace": res["rounds_level1"] or 0,
                       "succession": res["rounds_level2"]},
            "turns": {"palace": res["turns_level1"],
                      "succession": res["turns_level2"],
                      "total": res["total_turns"]},
            "points": _points(state),
        },
    }


# ---------------------------------------------------------------------------
# Game driving
# ---------------------------------------------------------------------------

def bots_for_seed(seed):
    """Seat-to-bot assignment derived from the game seed alone."""
    rng = random.Random(f"golden-bots:{seed}")
    return [rng.choice(BOT_POOL) for _ in range(SEATS)]


def build_game_line(rules, index, seed):
    """Play one game; return its full game line."""
    bots = bots_for_seed(seed)
    game_id = f"g{seed:06d}"
    seat_bots = {f"P{i}": bots[i] for i in range(SEATS)}
    state = engine.new_game(rules, seed, game_id, seat_bots)
    prng = random.Random(f"policy:{game_id}:{seed}")
    limit = 4 * (rules["palace"]["max_rounds"]
                 + rules["palace"]["rounds_after_checkpoint"]
                 + rules["succession"]["max_rounds"]) + 8
    trace, played = [], 0
    while not engine.is_finished(state):
        played += 1
        if played > limit:
            raise RuntimeError(f"game {game_id} exceeded its turn limit")
        active = state["active_player"]
        obs = engine.observe(state, active)
        action_id, reason = policies.act(seat_bots[active], obs, prng)
        record = engine.apply_action(state, active, obs["turn_id"],
                                     action_id, reason)
        trace.append(neutral_turn(record, state))
    engine.check_invariants(state)
    trace.append(neutral_result(state))
    return {"game": index, "seed": seed, "bots": bots, "trace": trace}


def build_all_games(rules, games=GAMES, seed_base=SEED_BASE):
    """Play every game; return the full list of game lines."""
    return [build_game_line(rules, i, seed_base + i) for i in range(games)]


# ---------------------------------------------------------------------------
# Fixture writing
# ---------------------------------------------------------------------------

def write_fixtures(root, games=GAMES, seed_base=SEED_BASE):
    """Regenerate traces.jsonl and meta.json under the golden dir."""
    rules, rules_rel = load_default_rules(root)
    lines = build_all_games(rules, games=games, seed_base=seed_base)
    out_dir = os.path.join(root, GOLDEN_DIR)
    os.makedirs(out_dir, exist_ok=True)
    traces_path = os.path.join(out_dir, "traces.jsonl")
    with open(traces_path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, separators=(",", ":"), sort_keys=True))
            fh.write("\n")
    meta = {
        "generator_version": GENERATOR_VERSION,
        "games": games,
        "seed_base": seed_base,
        "seeds": [seed_base + i for i in range(games)],
        "bot_pool": list(BOT_POOL),
        "rules_file": rules_rel,
        "rules_hash": engine.rules_hash(rules),
        "rules_version": rules["game"]["rules_version"],
    }
    meta_path = os.path.join(out_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return traces_path, meta_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="make_golden_traces.py",
        description="Regenerate the golden-trace fixtures "
                    "(tests/fixtures/golden/).")
    parser.add_argument("--games", type=int, default=GAMES)
    parser.add_argument("--seed-base", type=int, default=SEED_BASE)
    parser.add_argument("--root", default=os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    args = parser.parse_args(argv)
    traces_path, meta_path = write_fixtures(
        args.root, games=args.games, seed_base=args.seed_base)
    print(traces_path)
    print(meta_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
