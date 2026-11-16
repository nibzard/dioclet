# ABOUTME: Tests for the strict Arena rules loader and the shipped rules file.
# ABOUTME: They cover hidden keys, unknown keys, wrong types, and engine validation.

import copy
import json
import os
import tempfile
import unittest

import engine
from arena import rules_loader

RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "rules", "v0102.json")

# Keys the engine reads with in-code defaults; the shipped file must state
# them so the JSON alone describes the game.
HIDDEN_KEYS = {
    ("level1", "claim_required_equipment"): 6,
    ("glory", "set_completion_reward"): 0,
    ("succession", "proclaim_cost"): 0,
    ("combat", "ability_stacking"): "best",
    ("succession", "gate_rotation"): 0,
}


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_tmp(rules):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(rules, fh)
    return path


class ShippedFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(RULES_PATH, "r", encoding="utf-8") as fh:
            cls.rules = json.load(fh)

    def test_shipped_file_loads_strictly(self):
        loaded = rules_loader.load_rules_strict(RULES_PATH)
        self.assertEqual(loaded["rules_version"], self.rules["rules_version"])

    def test_engine_validators_pass_on_shipped_file(self):
        self.assertTrue(engine.validate_rules(copy.deepcopy(self.rules)))

    def test_hidden_keys_present_with_engine_default_values(self):
        for (section, key), value in HIDDEN_KEYS.items():
            self.assertIn(key, self.rules[section],
                          f"{section}.{key} missing from the shipped file")
            self.assertEqual(self.rules[section][key], value)
        self.assertEqual(self.rules["start_reveals"], 2)

    def test_shipped_file_matches_the_source_rules_except_additions(self):
        source = load(os.path.join(os.path.dirname(RULES_PATH), "..", "..",
                                   "rules_v0102_bigboard.json"))
        expected = copy.deepcopy(source)
        for (section, key), value in HIDDEN_KEYS.items():
            expected[section][key] = value
        self.assertEqual(self.rules, expected)


class StrictRejectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(RULES_PATH, "r", encoding="utf-8") as fh:
            cls.base = json.load(fh)

    def test_removing_any_hidden_key_is_an_error(self):
        for (section, key) in HIDDEN_KEYS:
            rules = copy.deepcopy(self.base)
            del rules[section][key]
            path = write_tmp(rules)
            with self.assertRaisesRegex(
                    rules_loader.RulesError,
                    f"missing key '{key}' in {section}"):
                rules_loader.load_rules_strict(path)
            os.unlink(path)

    def test_removing_a_top_level_key_is_an_error(self):
        rules = copy.deepcopy(self.base)
        del rules["succession"]
        path = write_tmp(rules)
        with self.assertRaisesRegex(rules_loader.RulesError,
                                    "missing key 'succession'"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)

    def test_unknown_top_level_key_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["succesion"] = {}
        path = write_tmp(rules)
        with self.assertRaisesRegex(rules_loader.RulesError,
                                    "unknown key 'succesion'"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)

    def test_typoed_nested_key_names_the_key_and_parent(self):
        rules = copy.deepcopy(self.base)
        rules["succession"]["procalm_cost"] = 0
        path = write_tmp(rules)
        with self.assertRaisesRegex(
                rules_loader.RulesError,
                r"unknown key 'procalm_cost' in succession"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)

    def test_unknown_nested_key_in_combat_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["combat"]["duel_glory_theft"] = True
        path = write_tmp(rules)
        with self.assertRaisesRegex(
                rules_loader.RulesError,
                r"unknown key 'duel_glory_theft' in combat"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)

    def test_wrong_type_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["succession"]["proclaim_cost"] = "zero"
        path = write_tmp(rules)
        with self.assertRaisesRegex(
                rules_loader.RulesError, r"proclaim_cost must be"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)

    def test_out_of_range_value_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["succession"]["gate_rotation"] = 9
        path = write_tmp(rules)
        with self.assertRaisesRegex(
                rules_loader.RulesError, r"gate_rotation must be"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)

    def test_players_is_fixed_at_four(self):
        rules = copy.deepcopy(self.base)
        rules["players"] = 5
        path = write_tmp(rules)
        with self.assertRaisesRegex(
                rules_loader.RulesError, r"players must be"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)

    def test_invalid_json_is_an_error(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        with self.assertRaisesRegex(rules_loader.RulesError,
                                    "not valid JSON"):
            rules_loader.load_rules_strict(path)
        os.unlink(path)


if __name__ == "__main__":
    unittest.main()
