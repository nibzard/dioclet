# ABOUTME: One full four-seat game with the real local bots, end to end.
# ABOUTME: Verifies the terminal result, engine invariants, and match.jsonl counts.

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine

from arena import match as match_mod

ARENA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_full_bots_game_reaches_terminal_result(tmp_path):
    config = match_mod.load_match(
        os.path.join(ARENA_DIR, "matches", "bots.json"))
    run_dir = str(tmp_path / "run")
    summary = match_mod.run_match(config, run_dir)

    assert summary["incomplete"] is False
    assert summary["outcome"] in ("win", "draw")
    assert summary["winner"] in (None, "P0", "P1", "P2", "P3")
    assert summary["total_turns"] > 0

    with open(os.path.join(run_dir, "engine", "state.json"), "r",
              encoding="utf-8") as fh:
        state = json.load(fh)
    engine.check_invariants(state)
    result = engine.result(state)
    assert result["outcome"] == summary["outcome"]
    assert result["winner"] == summary["winner"]
    assert result["total_turns"] == summary["total_turns"]

    with open(os.path.join(run_dir, "match.jsonl"), "r",
              encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert lines[0]["type"] == "match_start"
    assert lines[-1]["type"] == "result"
    decisions = [line for line in lines if line["type"] == "decision"]
    skipped = sum(1 for record in state["events"]
                  if record["action"]["kind"] == "skip_turn")
    assert len(decisions) == len(state["events"]) - skipped
    for seat, entry in summary["seats"].items():
        assert entry["calls"] == 0
        assert entry["cost_usd"] == 0.0
        assert entry["errors"] == []
    assert sum(entry["decisions"] for entry in summary["seats"].values()) \
        == len(decisions)
