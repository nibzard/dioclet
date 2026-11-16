# ABOUTME: Shared engine infrastructure tests: rules hash, rules loading,
# ABOUTME: run-directory persistence, and the serialized RNG helpers.
"""Tests for the engine's shared infrastructure.

These tests cover the parts that serve every rules file and runner: the
rules hash, `load_rules` and its validation gate, run-directory
persistence, and the serialized RNG helpers. Game behavior is covered by
test_succession.py and the golden-trace replay.
"""

import copy
import json
import os
import random
import tempfile
import unittest

import engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules_v0102_bigboard.json")


def played_state(rules=None, seed=31):
    """A fresh game state with one action applied, for persistence tests."""
    state = engine.new_game(rules or engine.load_rules(RULES_PATH), seed,
                            f"persist-{seed}")
    action = engine.legal_actions(state)[0]
    engine.apply_action(state, state["active_player"], state["turn_id"],
                        action["action_id"])
    return state


class TestRulesHash(unittest.TestCase):
    def test_stable_and_key_order_insensitive(self):
        rules = engine.load_rules(RULES_PATH)
        shuffled = {key: rules[key] for key in reversed(list(rules))}
        self.assertEqual(engine.rules_hash(rules), engine.rules_hash(shuffled))

    def test_content_changes_the_hash(self):
        rules = engine.load_rules(RULES_PATH)
        changed = copy.deepcopy(rules)
        changed["succession"]["support_cost"] += 1
        self.assertNotEqual(engine.rules_hash(rules),
                            engine.rules_hash(changed))


class TestLoadRules(unittest.TestCase):
    def test_loads_and_validates_the_default_rules(self):
        rules = engine.load_rules(RULES_PATH)
        self.assertEqual(rules["players"], 4)
        self.assertEqual(rules["gameplay_mode"], "succession-v1")

    def test_invalid_file_raises_invalid_rules_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"gameplay_mode": "succession-v1"}, fh)
            with self.assertRaises(engine.EngineError) as ctx:
                engine.load_rules(path)
        self.assertEqual(ctx.exception.code, "invalid_rules")


class TestRunPersistence(unittest.TestCase):
    def test_write_run_and_load_run_roundtrip(self):
        state = played_state()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = os.path.join(tmp, state["game_id"])
            engine.write_run(run_dir, state)
            for name in ("rules.snapshot.json", "metadata.json",
                         "state.json", "events.jsonl"):
                self.assertTrue(os.path.exists(os.path.join(run_dir, name)),
                                f"{name} missing after write_run")
            self.assertEqual(engine.load_run(run_dir), state)

    def test_write_run_appends_each_event_once(self):
        state = played_state()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = os.path.join(tmp, "once")
            engine.write_run(run_dir, state)
            engine.write_run(run_dir, state)
            with open(os.path.join(run_dir, "events.jsonl"),
                      encoding="utf-8") as fh:
                lines = [line for line in fh if line.strip()]
        self.assertEqual(len(lines), len(state["events"]))

    def test_reset_events_file_truncates_to_state(self):
        state = played_state()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = os.path.join(tmp, "reset")
            engine.write_run(run_dir, state)
            events_path = os.path.join(run_dir, "events.jsonl")
            with open(events_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"junk": True}) + "\n")
            engine.reset_events_file(run_dir, state)
            with open(events_path, encoding="utf-8") as fh:
                lines = [line for line in fh if line.strip()]
        self.assertEqual(len(lines), len(state["events"]))
        for line, record in zip(lines, state["events"]):
            self.assertEqual(json.loads(line), record)


class TestRngHelpers(unittest.TestCase):
    def test_dump_and_load_preserve_the_sequence(self):
        rng = engine._rng_from_seed(42, "movement")
        [rng.random() for _ in range(5)]  # advance past the seed state
        blob = engine._dump_rng(rng)
        expected = [rng.random() for _ in range(5)]
        restored = engine._load_rng(blob)
        self.assertEqual([restored.random() for _ in range(5)], expected)

    def test_stream_names_seed_different_sequences(self):
        gates = engine._rng_from_seed(42, "gates")
        order = engine._rng_from_seed(42, "order")
        self.assertNotEqual([gates.random() for _ in range(5)],
                            [order.random() for _ in range(5)])

    def test_dumped_state_is_json_serializable(self):
        blob = engine._dump_rng(random.Random(7))
        roundtrip = engine._load_rng(json.loads(json.dumps(blob)))
        self.assertEqual(roundtrip.random(), random.Random(7).random())


if __name__ == "__main__":
    unittest.main()
