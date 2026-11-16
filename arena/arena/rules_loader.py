# ABOUTME: Strict loader for Dioclet succession rules JSON files used by Arena.
# ABOUTME: It requires every key, rejects unknown keys, then defers to the engine validators.

"""Load a rules file under a strict structural contract.

The engine validators accept partial files and apply in-code defaults for
absent keys, so a typo silently changes the game. This module removes that
gap for Arena: every key the engine reads must be present in the file, and
any key the contract does not name is an error. Semantic checks (ranges,
reachability, layout) stay in `engine.validate_rules` and
`succession.validate_rules`, which run as the final gate.
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
_CELL = ("cell",)
_BOOL = ("bool",)
_INT = ("int",)
_STR = ("str",)

_board = {
    "width": _INT, "height": _INT,
    "gates": ("map", _CELL, 4, 4),
    "districts": ("map", _CELL, 6, 6),
    "checkpoint": _CELL,
    "glory_posts": ("array", _CELL, 4, 4),
    "level2_sites": ("obj", {
        "cellars": _CELL, "guard_barracks": _CELL, "peristyle": _CELL,
        "emperor": _CELL, "retreat": _CELL,
    }, {}),
    "blocked": ("array", _CELL, 0, None),
    "buildings": ("array", ("obj", {
        "name": _STR, "district": _STR,
        "x0": _INT, "x1": _INT, "y0": _INT, "y1": _INT,
    }, {}), 0, None),
    "streets": ("map", ("obj", {"axis": _STR, "coordinate": _INT}, {}), 0, None),
}

_BOARD_LEVEL2 = {
    "width": _INT, "height": _INT,
    "gates": ("map", _CELL, 4, 4),
    "checkpoint": _CELL,
    "glory_posts": ("array", _CELL, 0, None),
    "support_sites": ("array", _CELL, 3, None),
    "blocked": ("array", _CELL, 0, None),
}

SPEC = ("obj", {
    "rules_version": _STR,
    "game_name": _STR,
    "gameplay_mode": ("const", "succession-v1"),
    "players": ("const", 4),
    "start_reveals": ("int_range", 0, 6),
    "equipment": ("array", _STR, 6, 6),
    "board": ("obj", _board, {}),
    "board_level2": ("obj", _BOARD_LEVEL2, {}),
    "movement": ("obj", {
        "die_sides": _INT,
        "dice_count": ("int_range", 1, None),
        "duel_range": ("int_range", 0, None),
        "die_is_max_steps": _BOOL,
        "allow_early_stop": _BOOL,
        "pass_through_players": _BOOL,
        "allow_stationary_special_actions": _BOOL,
    }, {}),
    "glory": ("obj", {
        "cap": ("int_range", 0, None),
        "duel_win_reward": ("int_range", 0, None),
        "guard_post_reward": ("int_range", 0, None),
        "first_challenger_reward": ("int_range", 0, None),
        "guard_post_success_min_roll": _INT,
        "set_completion_reward": ("int_range", 0, None),
    }, {}),
    "combat": ("obj", {
        "equipment_bonus_tiers": ("array", ("obj", {
            "min_count": _INT, "max_count": _INT, "bonus": _INT,
        }, {}), 1, None),
        "tie_goes_to_defender": _BOOL,
        "imperial_guard_bonus": ("int_range", 0, None),
        "emperor_bonus": ("int_range", 0, None),
        "glory_attack_bonus": ("int_range", 0, None),
        "emperor_hits_to_win": ("int_range", 1, None),
        "abilities": ("map", ("obj", {"type": _STR, "value": _INT}, {}),
                      0, None),
        "ability_stacking": ("enum", ("best", "sum")),
    }, {}),
    "level1": ("obj", {
        "max_rounds": ("int_range", 1, None),
        "grace_full_rounds": ("int_range", 0, None),
        "auto_equip_at_transition": ("const", False),
        "claim_required_equipment": ("int_range", 1, 6),
    }, {}),
    "level2": ("obj", {
        "max_rounds": ("int_range", 1, None),
        "required_distinct_seals": ("int_range", 1, 3),
        "cellars_success_min_roll": _INT,
        "peristyle_success_min_roll": _INT,
        "peristyle_glory_cost": ("int_range", 0, None),
    }, {}),
    "succession": ("obj", {
        "support_cost": ("int_range", 1, None),
        "required_support": ("int_range", 1, None),
        "support_in_city": _BOOL,
        "challenge_cost": ("int_range", 1, None),
        "challenge_bonus": ("int_range", 0, None),
        "contest_cost": ("int_range", 0, None),
        "reset_positions": _BOOL,
        "gate_assignment": ("enum", ("random", "manual", "rotation")),
        "gate_rotation": ("int_range", 0, 3),
        "factions": ("map", _CELL, 3, 3),
        "claim_window_rounds": ("int_range", 0, 6),
        "challenge_radius": ("int_range", 0, 8),
        "duel_loser_cost": ("int_range", 0, 3),
        "proclaim_cost": ("int_range", 0, 3),
        "blind_support": _BOOL,
    }, {"gate_order": ("array", _STR, 4, 4)}),
    "turns": ("obj", {"rotate_first_player_each_round": _BOOL}, {}),
    "logging": ("obj", {
        "save_full_batch_logs": _BOOL,
        "sample_games_per_batch": ("int_range", 0, None),
        "save_anomalous_game_logs": _BOOL,
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
