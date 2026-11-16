# ABOUTME: Tests for the strict Arena rules loader and the shared rules file.
# ABOUTME: They cover missing keys, unknown keys, wrong types, and engine validation.

import copy
import json
import os
import tempfile
import unittest

import engine
from arena import rules_loader

RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "..",
                          "rules", "imperial-rivals-v0.10.2.json")


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
        self.assertEqual(loaded["game"]["rules_version"],
                         self.rules["game"]["rules_version"])

    def test_engine_validator_passes_on_shipped_file(self):
        self.assertTrue(engine.validate_rules(copy.deepcopy(self.rules)))

    def test_strict_loader_returns_the_document_unchanged(self):
        loaded = rules_loader.load_rules_strict(RULES_PATH)
        self.assertEqual(loaded, self.rules)

    def test_null_prestige_cap_is_accepted(self):
        rules = copy.deepcopy(self.rules)
        rules["prestige"]["cap"] = None
        path = write_tmp(rules)
        try:
            self.assertIsNone(rules_loader.load_rules_strict(path)
                              ["prestige"]["cap"])
        finally:
            os.unlink(path)


class StrictRejectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(RULES_PATH, "r", encoding="utf-8") as fh:
            cls.base = json.load(fh)

    def test_removing_a_nested_key_is_an_error(self):
        rules = copy.deepcopy(self.base)
        del rules["succession"]["contest_fee"]
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(
                    rules_loader.RulesError,
                    "missing key 'contest_fee' in succession"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_removing_a_top_level_key_is_an_error(self):
        rules = copy.deepcopy(self.base)
        del rules["succession"]
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(rules_loader.RulesError,
                                        "missing key 'succession'"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_unknown_top_level_key_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["succesion"] = {}
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(rules_loader.RulesError,
                                        "unknown key 'succesion'"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_typoed_nested_key_names_the_key_and_parent(self):
        rules = copy.deepcopy(self.base)
        rules["succession"]["procalm_cost"] = 0
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(
                    rules_loader.RulesError,
                    r"unknown key 'procalm_cost' in succession"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_unknown_nested_key_in_prestige_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["prestige"]["duel_prestige_theft"] = True
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(
                    rules_loader.RulesError,
                    r"unknown key 'duel_prestige_theft' in prestige"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_wrong_type_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["succession"]["proclaim_cost"] = "zero"
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(
                    rules_loader.RulesError, r"proclaim_cost must be"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_out_of_range_value_is_an_error(self):
        rules = copy.deepcopy(self.base)
        rules["duels"]["range"] = 9
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(
                    rules_loader.RulesError, r"duels.range must be"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_players_is_fixed_at_four(self):
        rules = copy.deepcopy(self.base)
        rules["game"]["players"] = 5
        path = write_tmp(rules)
        try:
            with self.assertRaisesRegex(
                    rules_loader.RulesError, r"game.players must be"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)

    def test_invalid_json_is_an_error(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        try:
            with self.assertRaisesRegex(rules_loader.RulesError,
                                        "not valid JSON"):
                rules_loader.load_rules_strict(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
