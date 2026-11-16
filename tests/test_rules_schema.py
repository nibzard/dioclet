# ABOUTME: Schema-vs-validator parity tests for the rules contract:
# ABOUTME: jsonschema accepts exactly what engine.validate_rules accepts.
"""The rules schema and the engine validator agree on every key.

rules/rules.schema.json states the shape; engine.validate_rules mirrors
it and adds the geometry and arithmetic checks a schema cannot state.
These tests keep the two in lockstep: the adopted file passes both, and
for every object in it, dropping a key or adding an unknown key makes
BOTH reject.
"""
import copy
import json
import os
import unittest

from jsonschema import Draft202012Validator, ValidationError

import engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")
SCHEMA_PATH = os.path.join(ROOT, "rules", "rules.schema.json")


def objects(node, path=()):
    """Yield (path, dict) for every object in the instance, top-down."""
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from objects(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from objects(value, path + (index,))


class SchemaContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(RULES_PATH, encoding="utf-8") as fh:
            cls.rules = json.load(fh)
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            cls.schema = json.load(fh)
        cls.validator = Draft202012Validator(cls.schema)

    def schema_ok(self, instance):
        try:
            self.validator.validate(instance)
            return True
        except ValidationError:
            return False

    def engine_ok(self, instance):
        try:
            engine.validate_rules(instance)
            return True
        except engine.EngineError:
            return False

    def broken_copy(self, path, mutate):
        broken = copy.deepcopy(self.rules)
        container = broken
        for step in path:
            container = container[step]
        mutate(container)
        return broken

    def test_schema_is_valid_draft_2020_12(self):
        Draft202012Validator.check_schema(self.schema)

    def test_adopted_file_passes_both(self):
        self.assertTrue(self.schema_ok(self.rules))
        self.assertTrue(self.engine_ok(self.rules))

    def test_both_reject_every_dropped_key(self):
        nodes = list(objects(self.rules))
        for path, node in nodes:
            for key in list(node):
                with self.subTest(where="/".join(map(str, path)) or "<root>", dropped=key):
                    broken = self.broken_copy(path, lambda c, k=key: c.pop(k))
                    self.assertFalse(self.schema_ok(broken),
                                     "the schema accepted a dropped key")
                    self.assertFalse(self.engine_ok(broken),
                                     "the engine accepted a dropped key")

    def test_both_reject_every_unknown_key(self):
        for path, _node in list(objects(self.rules)):
            with self.subTest(where="/".join(map(str, path)) or "<root>"):
                broken = self.broken_copy(
                    path, lambda c: c.__setitem__("zz_unknown_key_sentinel", 1))
                self.assertFalse(self.schema_ok(broken),
                                 "the schema accepted an unknown key")
                self.assertFalse(self.engine_ok(broken),
                                 "the engine accepted an unknown key")


if __name__ == "__main__":
    unittest.main()
