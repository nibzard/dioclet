# ABOUTME: Structural loader for the Dioclet rules file used by Arena.
# ABOUTME: It states the key contract with its own error, then defers to the engine validator.

"""Load a rules file under a structural contract.

`rules/rules.schema.json` and `engine.validate_rules` state the full
contract; this module gives Arena an importable, dependency-free statement
of the same key sets, enums, and ranges, and reports structural breaks as
`RulesError` so match configuration can name the file, not the engine, as
the problem. Semantic checks (map geometry, reachability, arithmetic
between sections) stay in `engine.validate_rules`, which runs as the final
gate.
"""

import json

import engine


class RulesError(Exception):
    """A rules file breaks the strict structural contract."""


# A spec node is a tuple:
#   ("obj", required, optional)   object; required/optional map key -> spec
#   ("array", item_spec, min, max)
#   ("map", value_spec, min, max) object with free string keys
#   ("cell",)                     [x, y] integer pair
#   ("bool",) ("int",) ("str",)
#   ("int_range", lo, hi)         inclusive integer range
#   ("const", value) ("enum", values)
#   ("nullable", inner)           null, or whatever the inner spec accepts
_CELL = ("cell",)
_BOOL = ("bool",)
_INT = ("int",)
_STR = ("str",)

_TREASURE = ("enum", ("pugio", "pilum", "galea", "scutum", "gladius",
                      "lorica_segmentata"))
_ABILITY = ("obj", {
    "type": ("enum", ("attack_bonus", "defense_bonus", "attack_vs_claimant",
                      "win_ties", "reveal_district", "prevent_displacement")),
    "value": ("int_range", 0, 3),
}, {})
_GATES = ("obj", {name: _CELL for name in ("north", "east", "south", "west")}, {})
_STREET = ("obj", {"axis": ("enum", ("north-south", "east-west")),
                   "coordinate": ("int_range", 0, None)}, {})
_BUILDING = ("obj", {
    "name": _STR, "district": ("enum", ("A", "B", "C", "D", "E", "F")),
    "x0": _INT, "x1": _INT, "y0": _INT, "y1": _INT,
}, {})

_PALACE_MAP = ("obj", {
    "width": ("int_range", 5, None), "height": ("int_range", 5, None),
    "streets": ("obj", {"cardo": _STREET, "decumanus": _STREET,
                        "secondary": _STREET}, {}),
    "blocked": ("array", _CELL, 0, None),
    "buildings": ("array", _BUILDING, 6, 6),
    "gates": _GATES,
    "checkpoint": _CELL,
    "guard_posts": ("array", _CELL, 1, None),
    "treasure_entries": ("obj", {name: _CELL for name in "ABCDEF"}, {}),
}, {})

_SUCCESSION_MAP = ("obj", {
    "width": ("int_range", 5, None), "height": ("int_range", 5, None),
    "blocked": ("array", _CELL, 0, None),
    "gates": _GATES,
    "checkpoint": _CELL,
    "guard_posts": ("array", _CELL, 1, None),
    "card_spaces": ("array", _CELL, 3, None),
}, {})

SPEC = ("obj", {
    "game": ("obj", {"name": _STR, "rules_version": _STR,
                     "players": ("const", 4)}, {}),
    "turns": ("obj", {"rotate_first_player_each_round": _BOOL}, {}),
    "movement": ("obj", {
        "dice": ("int_range", 1, 4),
        "die_sides": ("int_range", 2, 12),
        "allow_early_stop": _BOOL,
        "pass_through_pawns": _BOOL,
        "allow_stationary_special_actions": _BOOL,
    }, {}),
    "treasures": ("obj", {
        "items": ("array", _TREASURE, 6, 6),
        "start_face_up": ("int_range", 0, 6),
        "abilities": ("map", _ABILITY, 6, 6),
        "bonus_per_side": ("const", "best"),
    }, {}),
    "prestige": ("obj", {
        "cap": ("nullable", ("int_range", 0, None)),
        "guard_post_min_roll": ("int_range", 1, 12),
        "guard_post_reward": ("int_range", 0, None),
        "duel_win_reward": ("int_range", 0, None),
        "duel_loss_penalty": ("int_range", 0, 3),
    }, {}),
    "duels": ("obj", {
        "range": ("int_range", 0, 8),
        "tie_winner": ("enum", ("attacker", "defender")),
    }, {}),
    "palace": ("obj", {
        "max_rounds": ("int_range", 1, None),
        "checkpoint_items_required": ("int_range", 1, 6),
        "rounds_after_checkpoint": ("int_range", 0, None),
        "map": _PALACE_MAP,
    }, {}),
    "succession": ("obj", {
        "max_rounds": ("int_range", 1, None),
        "support_cost": ("int_range", 1, None),
        "factions_to_proclaim": ("int_range", 1, 3),
        "contest_fee": ("int_range", 0, None),
        "claim_window_rounds": ("int_range", 0, 6),
        "proclaim_cost": ("int_range", 0, 3),
        "faction_cards": ("obj", {
            "factions": ("array", ("enum", ("army", "officials", "elites")),
                         3, 3),
            "empty": ("int_range", 0, None),
        }, {}),
        "gate_assignment": ("const", "random"),
        "map": _SUCCESSION_MAP,
    }, {}),
}, {})


def _describe(spec):
    kind = spec[0]
    if kind == "cell":
        return "an [x, y] pair of integers"
    if kind == "bool":
        return "a boolean"
    if kind == "int":
        return "an integer"
    if kind == "str":
        return "a string"
    if kind == "int_range":
        return f"an integer from {spec[1]} to {spec[2] or 'unbounded'}"
    if kind == "const":
        return f"exactly {spec[1]!r}"
    if kind == "enum":
        return f"one of {list(spec[1])}"
    if kind == "nullable":
        return f"null or {_describe(spec[1])}"
    if kind == "array":
        return "an array"
    return "an object"


def _check(value, spec, path):
    kind = spec[0]
    where = path or "the document root"
    if kind == "obj":
        required, optional = spec[1], spec[2]
        if not isinstance(value, dict):
            raise RulesError(f"{where} must be an object")
        for key in required:
            if key not in value:
                raise RulesError(f"missing key '{key}' in {where}")
        allowed = set(required) | set(optional)
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise RulesError(
                f"unknown key '{unknown[0]}' in {where} "
                f"(allowed keys: {sorted(allowed)})")
        for key, sub in {**required, **optional}.items():
            if key in value:
                _check(value[key], sub, f"{path}.{key}" if path else key)
    elif kind == "array":
        _, item, lo, hi = spec
        if not isinstance(value, list):
            raise RulesError(f"{where} must be an array")
        if lo is not None and len(value) < lo or hi is not None and len(value) > hi:
            raise RulesError(f"{where} must have {lo or 0}..{hi or 'unbounded'}"
                             f" items, found {len(value)}")
        for i, entry in enumerate(value):
            _check(entry, item, f"{where}[{i}]")
    elif kind == "map":
        _, value_spec, lo, hi = spec
        if not isinstance(value, dict):
            raise RulesError(f"{where} must be an object")
        if lo is not None and len(value) < lo or hi is not None and len(value) > hi:
            raise RulesError(f"{where} must have {lo or 0}..{hi or 'unbounded'}"
                             f" entries, found {len(value)}")
        for key, entry in value.items():
            _check(key, _STR, f"{where} key '{key}'")
            _check(entry, value_spec, f"{where}['{key}']")
    elif kind == "cell":
        if (not isinstance(value, list) or len(value) != 2
                or any(type(v) is not int for v in value)):
            raise RulesError(f"{where} must be {_describe(spec)}")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise RulesError(f"{where} must be {_describe(spec)}")
    elif kind == "int":
        if type(value) is not int:
            raise RulesError(f"{where} must be {_describe(spec)}")
    elif kind == "int_range":
        _, lo, hi = spec
        if type(value) is not int or not (lo <= value and (hi is None or value <= hi)):
            raise RulesError(f"{where} must be {_describe(spec)}")
    elif kind == "str":
        if not isinstance(value, str):
            raise RulesError(f"{where} must be {_describe(spec)}")
    elif kind == "const":
        if value != spec[1] or type(value) is not type(spec[1]):
            raise RulesError(f"{where} must be {_describe(spec)}")
    elif kind == "nullable":
        if value is None:
            return
        _check(value, spec[1], path)
    elif kind == "enum":
        if value not in spec[1]:
            raise RulesError(f"{where} must be {_describe(spec)}")
    else:  # pragma: no cover - the spec above is exhaustive
        raise RulesError(f"internal error: unknown spec kind {kind!r}")


def load_rules_strict(path):
    """Load and validate a rules file under the strict contract.

    Raises RulesError for any structural violation and EngineError for
    semantic violations caught by the engine validators.
    """
    with open(path, "r", encoding="utf-8") as fh:
        try:
            rules = json.load(fh)
        except json.JSONDecodeError as exc:
            raise RulesError(f"{path} is not valid JSON: {exc}") from None
    _check(rules, SPEC, "")
    engine.validate_rules(rules)
    return rules
