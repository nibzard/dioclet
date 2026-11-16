# ABOUTME: Rules loader for Arena: it checks a rules file against the shared
# ABOUTME: schema, then against the engine validator as the final gate.

"""Load a rules file under the shared rules schema.

`rules/rules.schema.json` in the repository root states the structural
contract: every key required, no unknown keys, and a range for every
value. This module applies that schema with `jsonschema` and reports a
violation as `RulesError`, so match configuration can name the file, not
the engine, as the problem. Semantic checks that a schema cannot state
(map geometry, reachability, arithmetic between sections) stay in
`engine.validate_rules`, which runs as the final gate.
"""

import json
import os

import jsonschema

import engine

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(REPO_ROOT, "rules", "rules.schema.json")


class RulesError(Exception):
    """A rules file breaks the rules contract."""


def _load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        try:
            schema = json.load(fh)
        except json.JSONDecodeError as exc:
            raise RulesError(
                f"{SCHEMA_PATH} is not valid JSON: {exc}") from None
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _where(error):
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "the document root"


def _check_schema(rules):
    validator = jsonschema.Draft202012Validator(_load_schema())
    errors = sorted(validator.iter_errors(rules),
                    key=lambda err: [str(p) for p in err.absolute_path])
    if errors:
        first = errors[0]
        raise RulesError(f"{_where(first)}: {first.message}")


def load_rules_strict(path):
    """Load a rules file and validate it against the shared schema.

    Raises RulesError for a structural violation and EngineError for a
    semantic violation caught by the engine validator.
    """
    with open(path, "r", encoding="utf-8") as fh:
        try:
            rules = json.load(fh)
        except json.JSONDecodeError as exc:
            raise RulesError(f"{path} is not valid JSON: {exc}") from None
    _check_schema(rules)
    engine.validate_rules(rules)
    return rules
