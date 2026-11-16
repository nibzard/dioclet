# ABOUTME: The Imperial Rivals succession game engine: rules validation,
# ABOUTME: state, legal actions, resolution, events, bots, and run files.
"""Deterministic engine for the succession game (V0.10 lineage).

The engine is a pure state machine. `apply_action(state, ...)` mutates the
state in place and returns the event record for that turn. All randomness
flows through five named xorshift32 streams (gates, order, equipment,
movement, combat) whose states are serialized inside the game state, so a
(rules, seed, action sequence) triple reproduces a game exactly. Finished
or interrupted games persist to run directories through `write_run` and
`load_run`.
"""

import copy
import hashlib
import json
import os
import random
import tempfile
import time

from board import (Board, ENGINE_VERSION, GATE_NAMES, validate_six_block_layout,
                   gate_cells)

MODE = "succession-v1"
VERSION = "succession-0.9.1-experiment"
POLICY_VERSION = "succession-policies-0.9.0"
# V0.9 simplified ability set (C2): every card is one line, and at most one
# equipment bonus applies per duel side (the best one, never the sum).
ABILITY_TYPES = ("attack_bonus", "defense_bonus", "attack_vs_claimant",
                 "win_ties", "reveal_district", "prevent_displacement")
POLICY_NAMES = ("balanced", "balanced_se", "greedy", "aggressive", "random",
                "tactical", "collector", "early_support", "prestige_farmer", "counterleader")
SALTS = {"gates": 0xA5A5A5A5, "order": 0x243F6A88,
         "equipment": 0x9E3779B9, "movement": 0xB7E15162, "combat": 0xDEADBEEF}
# Frozen per-profile item preferences for the V0.9 design experiment. Applied
# identically in every arm so revealed item identity can steer routing. Weight
# 1 means: prefer this item unless it costs more than four extra street steps.
ITEM_PREFERENCES = {
    "collector": {"lorica_segmentata": 1, "scutum": 1},
    "early_support": {"galea": 1, "pugio": 1},
    "prestige_farmer": {"gladius": 1, "pugio": 1},
    "counterleader": {"pilum": 1, "gladius": 1},
}
IDS = ("P0", "P1", "P2", "P3")
ITEMS = ("pugio", "pilum", "galea", "scutum", "gladius", "lorica_segmentata")
FACTION_NAMES = ("army", "officials", "elites")
TREASURE_ENTRY_NAMES = ("A", "B", "C", "D", "E", "F")
_BOARDS = {}

# Top-level keys every rules file must state, and nothing more.
REQUIRED_KEYS = {"game", "turns", "movement", "treasures", "prestige",
                 "duels", "palace", "succession"}


class EngineError(Exception):
    """Rule or protocol violation; carries a machine-readable code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Rules loading and validation
# ---------------------------------------------------------------------------

def rules_hash(rules):
    canonical = json.dumps(rules, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_rules(path):
    with open(path, "r", encoding="utf-8") as fh:
        rules = json.load(fh)
    validate_rules(rules)
    return rules


def _error(code, message):
    raise EngineError(code, message)


def _exact_keys(obj, where, keys):
    """Every key in `keys` must be present; no other key may be."""
    if not isinstance(obj, dict):
        _error("invalid_rules", f"{where} must be an object")
    missing = set(keys) - set(obj)
    if missing:
        _error("invalid_rules", f"missing {where} keys: {sorted(missing)}")
    unknown = set(obj) - set(keys)
    if unknown:
        _error("invalid_rules", f"unknown {where} keys: {sorted(unknown)}")


def _require_int(value, where, low=None, high=None):
    """A plain integer (bool does not count) inside the given bounds."""
    bounds = "" if low is None and high is None else f" from {low} to {high}"
    if type(value) is not int:
        _error("invalid_rules", f"{where} must be an integer{bounds}")
    if low is not None and value < low or high is not None and value > high:
        _error("invalid_rules", f"{where} must be an integer{bounds}")


def _require_bool(value, where):
    if not isinstance(value, bool):
        _error("invalid_rules", f"{where} must be true or false")


def _require_cell(cell, where, width, height, blocked=frozenset()):
    if (not isinstance(cell, list) or len(cell) != 2
            or any(type(v) is not int or v < 0 for v in cell)):
        _error("invalid_rules", f"{where} must be an [x, y] cell of nonnegative integers")
    if cell[0] >= width or cell[1] >= height:
        _error("invalid_rules", f"{where} out of bounds")
    if tuple(cell) in blocked:
        _error("invalid_rules", f"{where} sits on a blocked cell")


def _require_gates(gates, where, width, height, blocked):
    _exact_keys(gates, f"{where}.gates", GATE_NAMES)
    for name in GATE_NAMES:
        _require_cell(gates[name], f"{where}.gates.{name}", width, height, blocked)
    if len({tuple(c) for c in gates.values()}) != 4:
        _error("invalid_rules", f"{where}.gates must be distinct")


def _validate_abilities(abilities):
    _exact_keys(abilities, "treasures.abilities", ITEMS)
    for item, spec in sorted(abilities.items()):
        _exact_keys(spec, f"treasures.abilities.{item}", ("type", "value"))
        if spec["type"] not in ABILITY_TYPES:
            _error("invalid_rules",
                   f"treasures.abilities.{item}.type must be one of: {', '.join(ABILITY_TYPES)}")
        _require_int(spec["value"], f"treasures.abilities.{item}.value", 0, 3)


def _validate_palace_map(rules):
    """The palace map carries the six-block contract and its own gates."""
    board_map = rules["palace"]["map"]
    _exact_keys(board_map, "palace.map",
                ("width", "height", "streets", "blocked", "buildings", "gates",
                 "checkpoint", "guard_posts", "treasure_entries"))
    width, height = board_map["width"], board_map["height"]
    _require_int(width, "palace.map.width", 5)
    _require_int(height, "palace.map.height", 5)
    blocked = _validate_blocked(board_map["blocked"], "palace.map.blocked")
    _require_gates(board_map["gates"], "palace.map", width, height, blocked)
    _require_cell(board_map["checkpoint"], "palace.map.checkpoint", width, height, blocked)

    streets = board_map["streets"]
    _exact_keys(streets, "palace.map.streets", ("cardo", "decumanus", "secondary"))
    for name in ("cardo", "decumanus", "secondary"):
        street = streets[name]
        _exact_keys(street, f"palace.map.streets.{name}", ("axis", "coordinate"))
        if street["axis"] not in ("north-south", "east-west"):
            _error("invalid_rules",
                   f"palace.map.streets.{name}.axis must be north-south or east-west")
        _require_int(street["coordinate"], f"palace.map.streets.{name}.coordinate", 0)

    buildings = board_map["buildings"]
    if not isinstance(buildings, list) or len(buildings) != 6:
        _error("invalid_rules", "palace.map.buildings must list six blocks")
    for i, building in enumerate(buildings):
        where = f"palace.map.buildings[{i}]"
        _exact_keys(building, where,
                    ("name", "district", "x0", "x1", "y0", "y1"))
        if not isinstance(building["name"], str) or not building["name"]:
            _error("invalid_rules", f"{where}.name must be a nonempty string")
        if building["district"] not in TREASURE_ENTRY_NAMES:
            _error("invalid_rules", f"{where}.district must be one of {list(TREASURE_ENTRY_NAMES)}")
        for key in ("x0", "x1", "y0", "y1"):
            _require_int(building[key], f"{where}.{key}", 0)

    posts = board_map["guard_posts"]
    if not isinstance(posts, list) or not posts:
        _error("invalid_rules", "palace.map.guard_posts must be a nonempty list")
    for i, cell in enumerate(posts):
        _require_cell(cell, f"palace.map.guard_posts[{i}]", width, height, blocked)

    entries = board_map["treasure_entries"]
    if not isinstance(entries, dict):
        _error("invalid_rules", "palace.map.treasure_entries must be an object")
    _exact_keys(entries, "palace.map.treasure_entries", TREASURE_ENTRY_NAMES)
    for name in TREASURE_ENTRY_NAMES:
        _require_cell(entries[name], f"palace.map.treasure_entries.{name}",
                      width, height, blocked)


def _validate_blocked(blocked, where):
    if not isinstance(blocked, list):
        _error("invalid_rules", f"{where} must be a list")
    for i, cell in enumerate(blocked):
        if (not isinstance(cell, list) or len(cell) != 2
                or any(type(v) is not int or v < 0 for v in cell)):
            _error("invalid_rules", f"{where}[{i}] must be an [x, y] cell of nonnegative integers")
    return {tuple(c) for c in blocked}


def _validate_succession_map(rules):
    """The succession map: four gates, a checkpoint, guard posts, and the
    face-down faction card spaces. No districts and no six-block contract
    (that layout is the palace map's)."""
    board_map = rules["succession"]["map"]
    _exact_keys(board_map, "succession.map",
                ("width", "height", "blocked", "gates", "checkpoint",
                 "guard_posts", "card_spaces"))
    width, height = board_map["width"], board_map["height"]
    _require_int(width, "succession.map.width", 5)
    _require_int(height, "succession.map.height", 5)
    blocked = _validate_blocked(board_map["blocked"], "succession.map.blocked")
    gates = board_map["gates"]
    _require_gates(gates, "succession.map", width, height, blocked)
    for pid, cell in gates.items():
        if tuple(cell) == tuple(board_map["checkpoint"]):
            _error("invalid_rules", f"succession.map gate {pid} sits on the checkpoint")
    _require_cell(board_map["checkpoint"], "succession.map.checkpoint", width, height, blocked)

    posts = board_map["guard_posts"]
    if not isinstance(posts, list) or not posts:
        _error("invalid_rules", "succession.map.guard_posts must be a nonempty list")
    for i, cell in enumerate(posts):
        _require_cell(cell, f"succession.map.guard_posts[{i}]", width, height, blocked)

    # Blind faction cards: three factions and blanks dealt face down onto
    # these street cells at the transition.
    sites = board_map["card_spaces"]
    if not isinstance(sites, list) or len(sites) < 3:
        _error("invalid_rules", "succession.map.card_spaces must list at least three cells")
    for i, cell in enumerate(sites):
        _require_cell(cell, f"succession.map.card_spaces[{i}]", width, height, blocked)
    if len({tuple(c) for c in sites}) != len(sites):
        _error("invalid_rules", "succession.map.card_spaces must be distinct")
    occupied = {tuple(c) for c in gates.values()} | {tuple(board_map["checkpoint"])}
    for cell in sites:
        if tuple(cell) in occupied:
            _error("invalid_rules",
                   "succession.map card space cannot be a gate or the checkpoint")
    for cell in posts:
        if tuple(cell) in {tuple(c) for c in gates.values()}:
            _error("invalid_rules", "succession.map gate sits on a guard post")

    b = Board(rules, "succession")
    reach = b.distances(b.gates["P0"])
    for cell in sites:
        if tuple(cell) not in reach:
            _error("invalid_rules", "succession.map card space must be a reachable street")
    for cell in b.guard_posts:
        if cell not in reach:
            _error("invalid_rules", "succession.map guard post must be reachable")
    for pid, gate in b.gates.items():
        if b.checkpoint not in b.distances(gate):
            _error("invalid_rules", f"succession.map checkpoint unreachable from gate {pid}")


def validate_rules(rules):
    """Reject rules that deviate from the Imperial Rivals contract.

    This walk mirrors rules/rules.schema.json: every key the engine reads
    must be present, and no other key may exist. Geometry and arithmetic
    checks that a schema cannot state run last.
    """
    if not isinstance(rules, dict):
        _error("invalid_rules", "rules must be a JSON object")
    _exact_keys(rules, "top-level", REQUIRED_KEYS)

    game = rules["game"]
    _exact_keys(game, "game", ("name", "rules_version", "players"))
    for key in ("name", "rules_version"):
        if not isinstance(game[key], str) or not game[key]:
            _error("invalid_rules", f"game.{key} must be a nonempty string")
    if game["players"] != 4:
        _error("invalid_rules", "game.players must be 4")

    turns = rules["turns"]
    _exact_keys(turns, "turns", ("rotate_first_player_each_round",))
    _require_bool(turns["rotate_first_player_each_round"], "turns.rotate_first_player_each_round")

    movement = rules["movement"]
    _exact_keys(movement, "movement",
                ("dice", "die_sides", "allow_early_stop", "pass_through_pawns",
                 "allow_stationary_special_actions"))
    _require_int(movement["dice"], "movement.dice", 1, 4)
    _require_int(movement["die_sides"], "movement.die_sides", 2, 12)
    for key in ("allow_early_stop", "pass_through_pawns",
                "allow_stationary_special_actions"):
        _require_bool(movement[key], f"movement.{key}")

    treasures = rules["treasures"]
    _exact_keys(treasures, "treasures",
                ("items", "start_face_up", "abilities", "bonus_per_side"))
    if not isinstance(treasures["items"], list) or sorted(treasures["items"]) != sorted(ITEMS):
        _error("invalid_rules", f"treasures.items must list each of {list(ITEMS)} once")
    _require_int(treasures["start_face_up"], "treasures.start_face_up", 0, 6)
    _validate_abilities(treasures["abilities"])
    if treasures["bonus_per_side"] != "best":
        _error("invalid_rules", 'treasures.bonus_per_side must be "best"')

    prestige = rules["prestige"]
    _exact_keys(prestige, "prestige",
                ("cap", "guard_post_min_roll", "guard_post_reward",
                 "duel_win_reward", "duel_loss_penalty"))
    cap = prestige["cap"]
    if cap is not None:
        _require_int(cap, "prestige.cap", 0)
    _require_int(prestige["guard_post_min_roll"], "prestige.guard_post_min_roll", 1, 12)
    _require_int(prestige["guard_post_reward"], "prestige.guard_post_reward", 0)
    _require_int(prestige["duel_win_reward"], "prestige.duel_win_reward", 0)
    _require_int(prestige["duel_loss_penalty"], "prestige.duel_loss_penalty", 0, 3)

    duels = rules["duels"]
    _exact_keys(duels, "duels", ("range", "tie_winner"))
    _require_int(duels["range"], "duels.range", 0, 8)
    if duels["tie_winner"] not in ("attacker", "defender"):
        _error("invalid_rules", 'duels.tie_winner must be "attacker" or "defender"')

    palace = rules["palace"]
    _exact_keys(palace, "palace",
                ("max_rounds", "checkpoint_items_required", "rounds_after_checkpoint", "map"))
    _require_int(palace["max_rounds"], "palace.max_rounds", 1)
    _require_int(palace["checkpoint_items_required"], "palace.checkpoint_items_required", 1, 6)
    _require_int(palace["rounds_after_checkpoint"], "palace.rounds_after_checkpoint", 0)
    if not isinstance(palace["map"], dict):
        _error("invalid_rules", "palace.map must be an object")

    config = rules["succession"]
    _exact_keys(config, "succession",
                ("max_rounds", "support_cost", "factions_to_proclaim", "contest_fee",
                 "claim_window_rounds", "proclaim_cost", "faction_cards",
                 "gate_assignment", "map"))
    _require_int(config["max_rounds"], "succession.max_rounds", 1)
    _require_int(config["support_cost"], "succession.support_cost", 1)
    _require_int(config["factions_to_proclaim"], "succession.factions_to_proclaim", 1, 3)
    _require_int(config["contest_fee"], "succession.contest_fee", 0)
    _require_int(config["claim_window_rounds"], "succession.claim_window_rounds", 0, 6)
    _require_int(config["proclaim_cost"], "succession.proclaim_cost", 0, 3)
    if config["gate_assignment"] != "random":
        _error("invalid_rules", 'succession.gate_assignment must be "random"')
    cards = config["faction_cards"]
    _exact_keys(cards, "succession.faction_cards", ("factions", "empty"))
    if (not isinstance(cards["factions"], list)
            or sorted(cards["factions"]) != sorted(FACTION_NAMES)):
        _error("invalid_rules",
               f"succession.faction_cards.factions must list each of {list(FACTION_NAMES)} once")
    _require_int(cards["empty"], "succession.faction_cards.empty", 0)
    if not isinstance(config["map"], dict):
        _error("invalid_rules", "succession.map must be an object")

    if cap is not None and cap < config["support_cost"]:
        _error("invalid_rules",
               "Prestige cap must cover at least one support purchase, or be null")
    try:
        _validate_palace_map(rules)
        validate_six_block_layout(rules)
        _validate_succession_map(rules)
    except (KeyError, TypeError, ValueError) as exc:
        _error("invalid_rules", f"invalid map layout: {exc}")
    return True


# ---------------------------------------------------------------------------
# RNG streams
# ---------------------------------------------------------------------------

def _random(state, stream):
    x = state["rng"][stream]
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    x &= 0xFFFFFFFF
    state["rng"][stream] = x
    return x / 4294967296


def _shuffle(state, values, stream):
    result = list(values)
    for i in range(len(result) - 1, 0, -1):
        j = int(_random(state, stream) * (i + 1))
        result[i], result[j] = result[j], result[i]
    return result


def _die(state, stream):
    return 1 + int(_random(state, stream) * state["rules"]["movement"]["die_sides"])


def _rng_from_seed(seed, stream):
    return random.Random(f"{seed}:{stream}")


def _dump_rng(rng):
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def _load_rng(state_blob):
    version, internal, gauss = state_blob
    rng = random.Random()
    rng.setstate((version, tuple(internal), gauss))
    return rng


# ---------------------------------------------------------------------------
# Board helpers
# ---------------------------------------------------------------------------

def _board(rules, phase=1):
    """The active Board: the palace map, or the succession map in
    the succession phase."""
    section = "succession" if phase == 2 else "palace"
    key = json.dumps([section, rules[section]["map"]],
                     sort_keys=True, separators=(",", ":"))
    if key not in _BOARDS:
        b = Board(rules, section)
        b._succ_distances = {}
        b._succ_paths = {}
        _BOARDS[key] = b
    return _BOARDS[key]


def _gate_cell(state, player, phase=None):
    """The player's gate on the ACTIVE board (the gates move to the
    succession map in the succession phase)."""
    phase = state["phase"] if phase is None else phase
    section = "succession" if phase == 2 else "palace"
    return list(gate_cells(state["rules"][section]["map"])[player["gate_id"]])


def _distances(b, start):
    start = tuple(start)
    if start not in b._succ_distances:
        b._succ_distances[start] = b.distances(start)
    return b._succ_distances[start]


def _path(b, start, end):
    start, end = tuple(start), tuple(end)
    cachekey = (start, end)
    if cachekey not in b._succ_paths:
        distances = _distances(b, end)
        path, current = [start], start
        while current != end:
            current = next(n for n in b.neighbors(current)
                           if distances[n] < distances[current])
            path.append(current)
        b._succ_paths[cachekey] = path
    return [list(c) for c in b._succ_paths[cachekey]]


def _faction_cells(rules):
    """Faction name to meeting-place cell, for succession-phase states
    built without the blind deal (the dealt layout otherwise defines
    the cells). The first three card spaces hold the factions."""
    cards = rules["succession"]["faction_cards"]["factions"]
    spaces = rules["succession"]["map"]["card_spaces"][:len(cards)]
    return dict(zip(sorted(cards), (list(c) for c in spaces)))


def _usable_ability(player, rules, ability_type):
    """Return (item, spec) for an owned, unused, nonzero ability of this type."""
    for item in player["equipment"]:
        spec = rules["treasures"]["abilities"].get(item)
        if (spec and spec["type"] == ability_type and spec["value"] > 0
                and not player["abilities_used"].get(ability_type)):
            return item, spec
    return None, None


def _ability_total(player, rules, ability_type):
    """Public rule fact: total value of owned abilities of this type."""
    total = 0
    for item in player["equipment"]:
        spec = rules["treasures"]["abilities"].get(item)
        if spec and spec["type"] == ability_type and spec["value"] > 0:
            total += spec["value"]
    return total


def current_order(state):
    start = state["round_start"] if state["rotate_first"] else 0
    return state["turn_order"][start:] + state["turn_order"][:start]


def _stats():
    return {name: 0 for name in (
        "prestige_earned", "prestige_spent", "prestige_wasted_at_cap",
        "equipment_collected", "explores", "explore_no_gain", "guard_post_attempts",
        "guard_post_successes", "duels_initiated", "duels_won_attacker",
        "duels_won_defender", "duels_defended", "support_gained", "claims_made",
        "claims_cancelled", "claims_cancelled_by", "claims_survived", "response_turns",
        "idle_moves", "challenge_boosts", "times_displaced", "checkpoint_claims", "contest_prestige_spent",
        "attack_bonus_uses", "defense_bonus_uses", "pilum_uses", "pugio_tiebreaks",
        "galea_reveals", "lorica_saves", "set_completion_awards",
        "site_searches", "shame_prestige_paid", "proclaims_paid")}


# ---------------------------------------------------------------------------
# Game creation
# ---------------------------------------------------------------------------

def new_game(rules, seed, game_id, policies=None):
    validate_rules(rules)
    state = {
        "gameplay_mode": MODE, "engine_version": VERSION,
        "rules": copy.deepcopy(rules), "rules_hash": rules_hash(rules),
        "game_id": game_id, "seed": seed,
        "rng": {name: ((int(seed) & 0xFFFFFFFF) ^ salt) or 1 for name, salt in SALTS.items()},
        "players": {}, "turn_order": [], "round_start": 0, "turn_index": 0,
        "rotate_first": rules["turns"]["rotate_first_player_each_round"],
        "turn_id": 0, "round": 1, "phase": 1, "current_roll": None,
        "pending_claim": None, "first_challenger": None, "trigger_round": None,
        "district_equipment": {}, "revealed": {}, "equipment_at_transition": {},
        "faction_sites": None, "faction_sites_revealed": None,
        "palace_timeout": False, "succession_timeout": False, "rounds_palace": None,
        "status": "in_progress", "winner": None, "end_reason": None,
        "event_seq": 0, "events": [], "policies": dict(policies or {}),
        "policy_version": POLICY_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    gate_order = _shuffle(state, IDS, "gates")
    state["gate_assignments"] = dict(zip(IDS, gate_order))
    palace_gates = gate_cells(rules["palace"]["map"])
    for pid, gateid in state["gate_assignments"].items():
        gate = list(palace_gates[gateid])
        state["players"][pid] = {"gate_id": gateid, "gate": gate, "pos": gate[:],
                                 "equipment": [], "prestige": 0, "support": [],
                                 "turns": 0, "stats": _stats(),
                                 "abilities_used": {}}
    state["turn_order"] = _shuffle(state, IDS, "order")
    equipment = _shuffle(state, rules["treasures"]["items"], "equipment")
    entries = rules["palace"]["map"]["treasure_entries"]
    state["district_equipment"] = dict(zip(sorted(entries), equipment))
    # Start-of-game public reveals (variant B). Drawn from the equipment stream
    # AFTER the district shuffle: no other code consumes that stream, so gates,
    # turn order, the district mapping, and every die stay identical across
    # arms on matched seeds.
    reveal_count = rules["treasures"]["start_face_up"]
    if reveal_count:
        for name in _shuffle(state, sorted(entries), "equipment")[:reveal_count]:
            state["revealed"][name] = state["district_equipment"][name]
        state["setup_reveals"] = sorted(state["revealed"])
    else:
        state["setup_reveals"] = []
    _start_turn(state)
    return state


def _start_turn(state):
    state["active_player"] = current_order(state)[state["turn_index"]]
    movement = state["rules"]["movement"]
    state["current_dice"] = [_die(state, "movement") for _ in range(movement["dice"])]
    state["current_roll"] = sum(state["current_dice"])
    state["turn_id"] += 1
    state["players"][state["active_player"]]["turns"] += 1


def legal_actions(state):
    if state["status"] != "in_progress":
        return []
    rules = state["rules"]
    config = rules["succession"]
    b = _board(rules, state["phase"])
    pid = state["active_player"]
    me = state["players"][pid]
    pos = tuple(me["pos"])
    distances = _distances(b, pos)
    cap = rules["prestige"]["cap"]
    actions = []

    def add(kind, dest, **extra):
        actions.append({"kind": kind, "destination": list(dest),
                        "path": _path(b, pos, dest), **extra})

    for dest, distance in distances.items():
        if distance > state["current_roll"]:
            continue
        moved = distance > 0
        if moved:
            add("move", dest)
        if moved or rules["movement"]["allow_stationary_special_actions"]:
            district = b.district_at.get(dest)
            if district is not None and (district not in state["revealed"] or
                    state["district_equipment"][district] not in me["equipment"]):
                add("explore", dest)
            if state["phase"] == 2:
                if state["faction_sites"] is not None:
                    # Blind faction cards: search unrevealed cells (the offer
                    # never depends on the hidden faction - DECISIONS.md D1),
                    # buy support only at revealed card spaces that hold
                    # a faction.
                    key = f"{dest[0]},{dest[1]}"
                    if key in state["faction_sites"] and key not in state["faction_sites_revealed"]:
                        add("search_site", dest)
                    revealed = state["faction_sites_revealed"]
                    if revealed.get(key) and revealed[key] not in me["support"] and me["prestige"] >= config["support_cost"]:
                        add("gain_support", dest, faction=revealed[key])
                else:
                    for faction, location in sorted(_faction_cells(rules).items()):
                        if tuple(location) == dest and faction not in me["support"] and me["prestige"] >= config["support_cost"]:
                            add("gain_support", dest, faction=faction)
            if dest == b.checkpoint:
                if (state["phase"] == 1 and state["first_challenger"] is None
                        and len(me["equipment"]) >= rules["palace"]["checkpoint_items_required"]):
                    add("claim_checkpoint", dest)
                if (state["phase"] == 2 and state["pending_claim"] is None
                        and len(me["support"]) >= config["factions_to_proclaim"]
                        and me["prestige"] >= config["proclaim_cost"]):
                    add("proclaim", dest)
        if moved:
            if dest in b.guard_posts and (cap is None or me["prestige"] < cap):
                add("guard_post", dest)
            for other, target in sorted(state["players"].items()):
                if other == pid or _distances(b, dest)[tuple(target["pos"])] > rules["duels"]["range"]:
                    continue
                pending = state["pending_claim"]
                contest_cost = config["contest_fee"] if pending and pending["player"] == other else 0
                if me["prestige"] < contest_cost:
                    continue
                add("duel", dest, target=other, spend_prestige=False, contest_cost=contest_cost)
    # Galea: a stationary, once-per-game public reveal of any unexplored
    # district. The offer never depends on the hidden item (DECISIONS.md D1).
    if rules["movement"]["allow_stationary_special_actions"]:
        if _usable_ability(me, rules, "reveal_district")[0]:
            for name in sorted(rules["palace"]["map"]["treasure_entries"]):
                if name not in state["revealed"]:
                    add("inspect", pos, district=name)
    pending = state["pending_claim"]
    if pending and pending["player"] == pid and pos == b.checkpoint:
        add("maintain_claim", pos)
    actions.sort(key=lambda a: (a["kind"], *a["destination"], a.get("target", ""),
                                bool(a.get("spend_prestige")), a.get("faction", "")))
    for i, action in enumerate(actions):
        action["action_id"] = f"a{i + 1:04d}"
    return actions


def observe(state, player):
    if state["status"] != "in_progress":
        _error("game_over", "the game has finished; no observation")
    if player != state["active_player"]:
        _error("not_your_turn", f"it is {state['active_player']}'s turn, not {player}'s")
    rules = state["rules"]
    config = rules["succession"]
    b = _board(rules, state["phase"])
    players = {}
    for pid, pdata in sorted(state["players"].items()):
        players[pid] = {"gate": list(pdata["gate"]), "gate_id": pdata["gate_id"],
                        "position": list(pdata["pos"]), "equipment": sorted(pdata["equipment"]),
                        "equipment_count": len(pdata["equipment"]),
                        "attack_bonus": _ability_total(pdata, rules, "attack_bonus"),
                        "defense_bonus": _ability_total(pdata, rules, "defense_bonus"),
                        "attack_vs_claimant_bonus": _ability_total(pdata, rules, "attack_vs_claimant"),
                        "prestige": pdata["prestige"], "support": sorted(pdata["support"]),
                        "turns": pdata["turns"]}
    progress = {"first_challenger": state["first_challenger"],
                "players_with_full_equipment": [p for p in IDS
                                                if len(state["players"][p]["equipment"]) >= rules["palace"]["checkpoint_items_required"]],
                "claim_required_equipment": rules["palace"]["checkpoint_items_required"],
                "palace_max_rounds": rules["palace"]["max_rounds"],
                "succession_max_rounds": rules["succession"]["max_rounds"],
                "grace_full_rounds": rules["palace"]["rounds_after_checkpoint"],
                "support_cost": config["support_cost"],
                "required_support": config["factions_to_proclaim"],
                "contest_cost": config["contest_fee"],
                "claim_window_rounds": config["claim_window_rounds"],
                "proclaim_cost": config["proclaim_cost"],
                "duel_loser_cost": rules["prestige"]["duel_loss_penalty"]}
    if state["first_challenger"] is not None:
        progress["transition_after_round"] = min(state["trigger_round"] + rules["palace"]["rounds_after_checkpoint"], rules["palace"]["max_rounds"])
    return {"gameplay_mode": MODE, "game_id": state["game_id"], "seed": state["seed"],
            "engine_version": VERSION, "status": state["status"], "phase": state["phase"],
            "round": state["round"], "turn_id": state["turn_id"],
            "active_player": state["active_player"], "viewer": player,
            "movement_die": state["current_roll"], "movement_dice": state["current_dice"][:],
            "turn_order": current_order(state),
            "gate_assignments": dict(state["gate_assignments"]),
            "board": {"width": b.width, "height": b.height,
                      "blocked": [list(c) for c in sorted(b.blocked)],
                      "gates": {p: list(c) for p, c in b.gates.items()},
                      "districts": {n: list(c) for n, c in b.districts.items()},
                      "guard_posts": [list(c) for c in b.guard_posts],
                      "checkpoint": list(b.checkpoint),
                      **({"card_spaces": {"candidates": [[int(x) for x in k.split(",")] for k in sorted(state["faction_sites"])],
                                          "revealed": {k: v for k, v in sorted(state["faction_sites_revealed"].items())}}}
                         if state["faction_sites"] is not None
                         else {"factions": ({} if state["phase"] == 1
                                            else copy.deepcopy(_faction_cells(rules)))})},
            "revealed_districts": dict(sorted(state["revealed"].items())),
            "prestige_cap": rules["prestige"]["cap"], "equipment_names": sorted(rules["treasures"]["items"]),
            "players": players, "pending_claim": copy.deepcopy(state["pending_claim"]),
            "progress": progress, "legal_actions": legal_actions(state)}


# ---------------------------------------------------------------------------
# Action resolution
# ---------------------------------------------------------------------------

def _award(state, pid, amount, cause, events):
    player = state["players"][pid]
    cap = state["rules"]["prestige"]["cap"]
    got = amount if cap is None else min(amount, max(0, cap - player["prestige"]))
    player["prestige"] += got
    player["stats"]["prestige_earned"] += got
    player["stats"]["prestige_wasted_at_cap"] += amount - got
    events.append({"type": "prestige_earned", "player": pid, "amount": got,
                   "wasted": amount - got, "cause": cause})


def _spend(state, pid, amount, purpose, events):
    player = state["players"][pid]
    player["prestige"] -= amount
    player["stats"]["prestige_spent"] += amount
    events.append({"type": "prestige_spent", "player": pid, "amount": amount, "purpose": purpose})


def _cancel(state, cause, events, attacker=None):
    pending = state["pending_claim"]
    claimant = pending["player"]
    state["players"][claimant]["stats"]["claims_cancelled"] += 1
    if attacker is not None:
        state["players"][attacker]["stats"]["claims_cancelled_by"] += 1
    events.append({"type": "claim_cancelled", "player": claimant,
                   "claim_id": pending["claim_id"], "cause": cause, "attacker": attacker})
    state["pending_claim"] = None


def apply_action(state, player, turn_id, action_id, reason=None):
    if state["status"] != "in_progress":
        _error("game_over", "the game has finished; no actions")
    if player != state["active_player"]:
        _error("not_your_turn", f"it is {state['active_player']}'s turn")
    if turn_id != state["turn_id"]:
        _error("stale_turn_id", f"expected turn_id {state['turn_id']}, got {turn_id}")
    available = {a["action_id"]: a for a in legal_actions(state)}
    if action_id not in available:
        _error("legal_action_error", f"unknown or illegal action_id {action_id!r}")
    action = available[action_id]
    rules, config = state["rules"], state["rules"]["succession"]
    b = _board(rules, state["phase"])
    me = state["players"][player]
    events, dice_used = [], []
    pending_before = copy.deepcopy(state["pending_claim"])
    kind = action["kind"]
    me["pos"] = action["destination"][:]
    if pending_before and pending_before["player"] == player and tuple(me["pos"]) != b.checkpoint:
        _cancel(state, "left_peristyle", events)

    def die():
        roll = _die(state, "combat")
        dice_used.append(roll)
        return roll

    if kind == "move":
        me["stats"]["idle_moves"] += 1
    elif kind == "explore":
        district = b.district_at[tuple(me["pos"])]
        item = state["district_equipment"][district]
        me["stats"]["explores"] += 1
        if district not in state["revealed"]:
            state["revealed"][district] = item
            events.append({"type": "district_revealed", "district": district, "item": item})
        if item not in me["equipment"]:
            me["equipment"].append(item)
            me["stats"]["equipment_collected"] += 1
            events.append({"type": "equipment_collected", "player": player, "district": district, "item": item})
        else:
            me["stats"]["explore_no_gain"] += 1
            events.append({"type": "explore_no_gain", "player": player, "district": district})
    elif kind == "inspect":
        # Galea: turn one hidden district face-up for everyone. Uses the same
        # reveal mechanic as exploration; no private channel exists.
        district = action["district"]
        item, _spec = _usable_ability(me, rules, "reveal_district")
        state["revealed"][district] = state["district_equipment"][district]
        me["abilities_used"]["reveal_district"] = item
        me["stats"]["galea_reveals"] += 1
        events.append({"type": "district_revealed", "district": district,
                       "item": state["district_equipment"][district]})
        events.append({"type": "ability_used", "player": player,
                       "ability": item, "district": district})
    elif kind == "guard_post":
        me["stats"]["guard_post_attempts"] += 1
        roll = die()
        success = roll >= rules["prestige"]["guard_post_min_roll"]
        events.append({"type": "guard_post", "player": player, "roll": roll, "success": success})
        if success:
            me["stats"]["guard_post_successes"] += 1
            _award(state, player, rules["prestige"]["guard_post_reward"], "guard_post", events)
    elif kind == "search_site":
        key = f"{me['pos'][0]},{me['pos'][1]}"
        faction = state["faction_sites"][key]
        state["faction_sites_revealed"][key] = faction
        me["stats"]["site_searches"] += 1
        events.append({"type": "card_space_revealed", "player": player,
                       "cell": list(me["pos"]), "faction": faction})
    elif kind == "gain_support":
        _spend(state, player, config["support_cost"], "faction_support", events)
        me["support"].append(action["faction"])
        me["support"].sort()
        me["stats"]["support_gained"] += 1
        events.append({"type": "support_gained", "player": player, "faction": action["faction"]})
    elif kind == "claim_checkpoint":
        state["first_challenger"] = player
        state["trigger_round"] = state["round"]
        me["stats"]["checkpoint_claims"] += 1
        events.append({"type": "first_challenger", "player": player})
    elif kind == "proclaim":
        state["pending_claim"] = {"player": player, "claim_id": turn_id, "responded": [],
                                  "round": state["round"]}
        if config["proclaim_cost"]:
            _spend(state, player, config["proclaim_cost"], "proclaim", events)
            me["stats"]["proclaims_paid"] += 1
        me["stats"]["claims_made"] += 1
        events.append({"type": "claim_proclaimed", "player": player, "claim_id": turn_id})
    elif kind == "maintain_claim":
        events.append({"type": "claim_maintained", "player": player})
    elif kind == "duel":
        target = action["target"]
        them = state["players"][target]
        me["stats"]["duels_initiated"] += 1
        them["stats"]["duels_defended"] += 1
        if action["contest_cost"]:
            _spend(state, player, action["contest_cost"], "claim_contest", events)
            me["stats"]["contest_prestige_spent"] += action["contest_cost"]
        attack_roll, defense_roll = die(), die()
        abilities = rules["treasures"]["abilities"]
        # At most one ability modifier applies per duel side: the best
        # one, never the sum (DECISIONS.md D42).
        attack_mods = []
        for item in me["equipment"]:
            spec = abilities.get(item)
            if not spec or spec["value"] <= 0:
                continue
            if spec["type"] == "attack_bonus":
                attack_mods.append(spec["value"])
                me["stats"]["attack_bonus_uses"] += 1
            elif (spec["type"] == "attack_vs_claimant" and state["pending_claim"]
                    and state["pending_claim"]["player"] == target):
                attack_mods.append(spec["value"])
                me["stats"]["pilum_uses"] += 1
        defense_mods = []
        for item in them["equipment"]:
            spec = abilities.get(item)
            if spec and spec["type"] == "defense_bonus" and spec["value"] > 0:
                defense_mods.append(spec["value"])
                them["stats"]["defense_bonus_uses"] += 1
        attack_bonus = max(attack_mods) if attack_mods else 0
        defense_bonus = max(defense_mods) if defense_mods else 0
        attack_score, defense_score = attack_roll + attack_bonus, defense_roll + defense_bonus
        # Pugio: the holder wins tied duels. If both hold one, the base tie
        # rule decides.
        attacker_pugio = _ability_total(me, rules, "win_ties") > 0
        defender_pugio = _ability_total(them, rules, "win_ties") > 0
        if attack_score != defense_score:
            won = attack_score > defense_score
        elif attacker_pugio != defender_pugio:
            won = attacker_pugio
            state["players"][player if attacker_pugio else target]["stats"]["pugio_tiebreaks"] += 1
            events.append({"type": "ability_used",
                           "player": player if attacker_pugio else target,
                           "ability": next(i for i in (me if attacker_pugio else them)["equipment"]
                                           if abilities.get(i, {}).get("type") == "win_ties")})
        else:
            won = rules["duels"]["tie_winner"] == "attacker"
        winner = player if won else target
        state["players"][winner]["stats"]["duels_won_attacker" if won else "duels_won_defender"] += 1
        events.append({"type": "duel", "attacker": player, "defender": target,
                       "winner": winner, "attacker_roll": attack_roll, "defender_roll": defense_roll,
                       "attacker_bonus": attack_bonus, "defender_bonus": defense_bonus,
                       "attacker_score": attack_score, "defender_score": defense_score,
                       "spend_prestige": False})
        _award(state, winner, rules["prestige"]["duel_win_reward"], "duel", events)
        # The beaten duelist is shamed and pays the bank up to one Prestige
        # of what they hold.
        shame = rules["prestige"]["duel_loss_penalty"]
        if shame:
            loser = target if won else player
            lplayer = state["players"][loser]
            paid = min(shame, lplayer["prestige"])
            if paid:
                _spend(state, loser, paid, "duel_shame", events)
                lplayer["stats"]["shame_prestige_paid"] += paid
        if won and state["pending_claim"] and state["pending_claim"]["player"] == target:
            _cancel(state, "challenge_won", events, attacker=player)
            # Lorica: once per game the beaten claimant keeps their position.
            # The claim is still cancelled; only the reset to the gate is saved.
            lorica_item, _spec = _usable_ability(them, rules, "prevent_displacement")
            if lorica_item:
                them["abilities_used"]["prevent_displacement"] = lorica_item
                them["stats"]["lorica_saves"] += 1
                events.append({"type": "ability_used", "player": target, "ability": lorica_item})
            else:
                them["pos"] = _gate_cell(state, them)
                them["stats"]["times_displaced"] += 1
    else:
        _error("legal_action_error", f"unknown succession action {kind}")

    pending = state["pending_claim"]
    if pending_before and pending and pending["claim_id"] == pending_before["claim_id"] and player != pending["player"]:
        if player not in pending["responded"]:
            pending["responded"].append(player)
            me["stats"]["response_turns"] += 1
            events.append({"type": "claim_response", "player": player, "claim_id": pending["claim_id"]})
        if len(set(pending["responded"])) == 3 and not config["claim_window_rounds"]:
            # Under a claim window the rivals must act inside the window
            # (challenge or cancel); mere responses no longer crown.
            claimant = pending["player"]
            state["winner"], state["status"], state["end_reason"] = claimant, "finished", "acclamation"
            state["players"][claimant]["stats"]["claims_survived"] += 1
            events.append({"type": "game_won", "player": claimant, "cause": "acclamation"})
    record = {"event_seq": state["event_seq"] + 1, "turn_id": turn_id,
              "round": state["round"], "phase": state["phase"], "player": player,
              "movement_die": state["current_roll"], "movement_dice": state["current_dice"][:],
              "action_id": action_id, "action": {k: v for k, v in action.items() if k != "action_id"},
              "dice_used": dice_used, "events": events, "position_after": me["pos"][:],
              "prestige_after": me["prestige"],
              "equipment_count_after": len(me["equipment"])}
    if reason is not None:
        record["reason"] = reason
    state["event_seq"] += 1
    state["events"].append(record)
    _advance(state)
    return record


def _advance(state):
    if state["status"] != "in_progress":
        return
    state["turn_index"] += 1
    if state["turn_index"] >= 4:
        state["turn_index"] = 0
        state["round"] += 1
        if state["rotate_first"]:
            state["round_start"] = (state["round_start"] + 1) % 4
        rules = state["rules"]
        window = rules["succession"]["claim_window_rounds"]
        pending = state["pending_claim"]
        if (window and state["phase"] == 2 and pending
                and state["round"] - pending["round"] > window):
            # A claim proclaimed in round R wins when the last turn of
            # round R + window ends, so it survives window full rounds
            # (end_reason survived_window). The event rides the last
            # turn record, like phase_transition and game_draw.
            claimant = pending["player"]
            state["winner"], state["status"], state["end_reason"] = claimant, "finished", "survived_window"
            state["players"][claimant]["stats"]["claims_survived"] += 1
            state["events"][-1]["events"].append({"type": "game_won", "player": claimant,
                                                  "cause": "survived_window"})
            state["current_roll"] = None
            return
        if state["phase"] == 1:
            end = rules["palace"]["max_rounds"]
            if state["first_challenger"] is not None:
                end = min(end, state["trigger_round"] + rules["palace"]["rounds_after_checkpoint"])
            if state["round"] > end:
                state["rounds_palace"] = state["round"] - 1
                state["palace_timeout"] = state["first_challenger"] is None
                state["equipment_at_transition"] = {p: len(d["equipment"]) for p, d in state["players"].items()}
                # The succession map takes over and every seat returns to
                # its gate on that map (the playtest's table rule, now
                # structural). Phase is set first so the gate lookup sees
                # the new map.
                state["phase"] = 2
                for player in state["players"].values():
                    player["pos"] = _gate_cell(state, player)
                state["round"], state["round_start"] = 1, 0
                # The three faction cards are dealt blind onto the
                # succession map's card spaces; the rest are blanks.
                # Drawn from the order stream, which nothing uses after
                # setup, so matched seeds stay aligned across arms.
                cells = sorted(list(c) for c in rules["succession"]["map"]["card_spaces"])
                state["faction_sites"] = {f"{c[0]},{c[1]}": None for c in cells}
                for cell, name in zip(_shuffle(state, cells, "order")[:3],
                                      sorted(rules["succession"]["faction_cards"]["factions"])):
                    state["faction_sites"][f"{cell[0]},{cell[1]}"] = name
                state["faction_sites_revealed"] = {}
                state["events"][-1]["events"].append({"type": "phase_transition", "from_phase": 1,
                    "to_phase": 2, "palace_timeout": state["palace_timeout"]})
        elif state["round"] > rules["succession"]["max_rounds"]:
            state["status"], state["winner"], state["end_reason"] = "finished", None, "succession_timeout"
            state["succession_timeout"] = True
            state["round"] = rules["succession"]["max_rounds"]
            state["current_roll"] = None
            state["events"][-1]["events"].append({"type": "game_draw", "reason": "succession_timeout"})
            return
    _start_turn(state)


def is_finished(state):
    return state["status"] != "in_progress"


def result(state):
    metrics = {}
    for pid, player in state["players"].items():
        stats = dict(player["stats"])
        districts = {tuple(r["action"]["destination"]) for r in state["events"] if r["player"] == pid and r["action"]["kind"] == "explore"}
        metrics[pid] = {**stats, "gate": player["gate"][:], "gate_id": player["gate_id"],
            "turns": player["turns"], "prestige_final": player["prestige"],
            "equipment_final": player["equipment"][:], "support": player["support"][:],
            "abilities_used": dict(player["abilities_used"]),
            "equipment_at_transition": state["equipment_at_transition"].get(pid),
            "districts_explored": len(districts)}
    turns1 = sum(r["phase"] == 1 for r in state["events"])
    first = state["first_challenger"]
    return {"gameplay_mode": MODE, "game_id": state["game_id"], "seed": state["seed"],
        "rules_hash": state["rules_hash"], "engine_version": VERSION, "policy_version": POLICY_VERSION,
        "outcome": "win" if state["winner"] else "draw", "winner": state["winner"],
        "end_reason": state["end_reason"], "first_challenger": first,
        "setup_reveals": list(state.get("setup_reveals", [])),
        "first_challenger_won": first == state["winner"] if first else None,
        "comeback_win": first != state["winner"] if first and state["winner"] else None,
        "palace_timeout": state["palace_timeout"], "succession_timeout": state["succession_timeout"],
        "rounds_palace": state["rounds_palace"], "rounds_succession": state["round"] if state["phase"] == 2 else 0,
        "turns_palace": turns1, "turns_succession": len(state["events"]) - turns1,
        "total_turns": len(state["events"]),
        "total_rounds": (state["rounds_palace"] or 0) + (state["round"] if state["phase"] == 2 else 0),
        "policies": dict(state["policies"]), "turn_order": current_order(state),
        "gate_assignments": dict(state["gate_assignments"]), "players": metrics,
        "high_impact_events": [{"turn_id": r["turn_id"], "round": r["round"], "phase": r["phase"], **ev}
            for r in state["events"] for ev in r["events"]
            if ev["type"] in {"duel", "support_gained", "claim_proclaimed", "claim_cancelled", "claim_response", "game_won", "phase_transition", "game_draw", "ability_used"}]}


def check_invariants(state):
    b = _board(state["rules"], state["phase"])
    cap = state["rules"]["prestige"]["cap"]
    for pid, player in state["players"].items():
        assert tuple(player["pos"]) in _distances(b, _gate_cell(state, player)), f"{pid} outside street graph"
        assert player["prestige"] >= 0 and (cap is None or player["prestige"] <= cap), "invalid Prestige"
        assert len(set(player["equipment"])) == len(player["equipment"]), "duplicate equipment"
        assert set(player["equipment"]) <= set(state["rules"]["treasures"]["items"]), "unknown equipment"
        assert len(set(player["support"])) == len(player["support"]), "duplicate support"
        assert set(player["support"]) <= set(state["rules"]["succession"]["faction_cards"]["factions"]), "unknown support"
        assert set(player["abilities_used"]) <= set(ABILITY_TYPES), "unknown ability type used"
        assert set(player["abilities_used"].values()) <= set(state["rules"]["treasures"]["items"]), "unknown ability item"
    assert sorted(state["gate_assignments"].values()) == list(IDS), "gate assignment not a permutation"
    pending = state["pending_claim"]
    if pending:
        assert tuple(state["players"][pending["player"]]["pos"]) == b.checkpoint, "claimant left Peristyle"
        assert pending["player"] not in pending["responded"], "claimant counted as responder"
        assert len(pending["responded"]) == len(set(pending["responded"])), "duplicate response"
    if state["winner"]:
        if state["end_reason"] == "survived_window":
            assert pending, "window win without a pending claim"
            window = state["rules"]["succession"]["claim_window_rounds"]
            assert window and state["round"] - pending["round"] > window, "claim window not actually survived"
        else:
            assert state["end_reason"] == "acclamation" and pending and len(pending["responded"]) == 3, "incomplete acclamation"
    if state["faction_sites"]:
        names = set(state["rules"]["succession"]["faction_cards"]["factions"])
        held = sorted(f for f in state["faction_sites"].values() if f)
        assert held == sorted(names), "blind card spaces must hold each faction exactly once"
        assert set(state["faction_sites_revealed"]) <= set(state["faction_sites"]), "revealed site is not a candidate"
        for key, faction in state["faction_sites_revealed"].items():
            assert state["faction_sites"][key] == faction, "revealed site mismatches the hidden deal"
    for record in state["events"]:
        assert len(record["action"]["path"]) - 1 <= record["movement_die"], "movement exceeds roll"
    return True


# ---------------------------------------------------------------------------
# Run-directory persistence
# ---------------------------------------------------------------------------

def _atomic_write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_run(run_dir, state):
    os.makedirs(run_dir, exist_ok=True)
    _atomic_write_json(os.path.join(run_dir, "rules.snapshot.json"), state["rules"])
    _atomic_write_json(os.path.join(run_dir, "metadata.json"), {
        "game_id": state["game_id"], "seed": state["seed"],
        "rules_hash": state["rules_hash"],
        "turn_order": state["turn_order"],
        "policies": state.get("policies", {}),
        "engine_version": state["engine_version"],
        "created": state["created"],
    })
    _atomic_write_json(os.path.join(run_dir, "state.json"), state)
    events_path = os.path.join(run_dir, "events.jsonl")
    persisted = 0
    if os.path.exists(events_path):
        with open(events_path, "r", encoding="utf-8") as fh:
            persisted = sum(1 for line in fh if line.strip())
    if persisted > len(state["events"]):  # stale file: rewrite from state
        persisted = 0
        mode = "w"
    else:
        mode = "a"
    with open(events_path, mode, encoding="utf-8") as fh:
        for record in state["events"][persisted:]:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    if is_finished(state):
        _atomic_write_json(os.path.join(run_dir, "result.json"), result(state))


def reset_events_file(run_dir, state):
    """Truncate events.jsonl to match state (robust replay after interrupts)."""
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "events.jsonl"), "w", encoding="utf-8") as fh:
        for record in state["events"]:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def load_run(run_dir):
    with open(os.path.join(run_dir, "state.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Built-in bots (observation-only; never inspect engine state)
# ---------------------------------------------------------------------------

_PUBLIC_DISTANCES = {}


def _public_distances(obs, source):
    board = obs["board"]
    blocked = frozenset(map(tuple, board["blocked"]))
    cachekey = (board["width"], board["height"], blocked, tuple(source))
    if cachekey not in _PUBLIC_DISTANCES:
        distances, todo = {tuple(source): 0}, [tuple(source)]
        for x, y in todo:
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                n = (x + dx, y + dy)
                if 0 <= n[0] < board["width"] and 0 <= n[1] < board["height"] and n not in blocked and n not in distances:
                    distances[n] = distances[(x, y)] + 1
                    todo.append(n)
        _PUBLIC_DISTANCES[cachekey] = distances
    return _PUBLIC_DISTANCES[cachekey]


def choose_policy(policy_name, obs, rng=None):
    """Choose only from the public legal list; never inspect engine state."""
    if policy_name not in POLICY_NAMES:
        raise ValueError(f"unknown succession policy {policy_name!r}")
    import random
    rng = rng or random.Random(0)
    actions = obs["legal_actions"]
    if not actions:
        raise ValueError("no legal succession actions")
    if policy_name == "random":
        weights = {"proclaim": 6, "maintain_claim": 6, "claim_checkpoint": 4,
                   "gain_support": 4, "explore": 3, "guard_post": 2, "duel": 2, "move": 1}
        kinds = sorted({a["kind"] for a in actions})
        kind = rng.choices(kinds, weights=[weights.get(k, 1) for k in kinds], k=1)[0]
        picked = rng.choice([a for a in actions if a["kind"] == kind])
        return picked["action_id"], f"{POLICY_VERSION}: random {kind}"
    me = obs["players"][obs["viewer"]]
    checkpoint = obs["board"]["checkpoint"]
    progress = obs["progress"]
    pending = obs["pending_claim"]
    prestige = me["prestige"]
    cap = obs["prestige_cap"]
    has_room = cap is None or prestige < cap
    bykind = lambda kind: [a for a in actions if a["kind"] == kind]
    tie_direction = -1 if policy_name == "balanced_se" else 1

    def nearest(pool):
        return min(pool, key=lambda a: (len(a["path"]), tie_direction * a["destination"][0],
                                         tie_direction * a["destination"][1], a["action_id"]))

    def select(action, reason):
        return action["action_id"], f"{POLICY_VERSION}: {reason}"

    def toward(target, reason):
        distances = _public_distances(obs, target)
        pool = bykind("move")
        action = min(pool, key=lambda a: (distances[tuple(a["destination"])],
                         len(a["path"]), tie_direction * a["destination"][0], tie_direction * a["destination"][1]))
        return select(action, reason)

    def duel_key(action):
        other = obs["players"][action["target"]]
        edge = me.get("attack_bonus", 0) - other.get("defense_bonus", 0)
        if pending and pending["player"] == action["target"]:
            edge += me.get("attack_vs_claimant_bonus", 0)
        wins = sum(1 for a in range(1, 7) for d in range(1, 7) if a + edge >= d)
        return (-wins, bool(action["spend_prestige"]), len(action["path"]), action["action_id"])

    if pending and pending["player"] == obs["viewer"] and bykind("maintain_claim"):
        return select(bykind("maintain_claim")[0], "maintain the pending claim")
    if pending and pending["player"] != obs["viewer"]:
        challenges = [a for a in bykind("duel") if a["target"] == pending["player"]]
        if challenges:
            return select(min(challenges, key=duel_key), "challenge the claimant")
        if prestige < progress["contest_cost"]:
            if bykind("guard_post"):
                return select(nearest(bykind("guard_post")), "earn Prestige for a future contest")
            available_duels = [a for a in bykind("duel") if not a["spend_prestige"]]
            if available_duels:
                return select(min(available_duels, key=duel_key), "earn Prestige for a future contest")
            public_dist = _public_distances(obs, me["position"])
            posts = obs["board"]["guard_posts"]
            if posts:
                guard = min(posts, key=lambda c: (public_dist[tuple(c)], c))
                return toward(guard, "seek Prestige for a future contest")
            return toward(checkpoint, "approach the claimant")
        return toward(checkpoint, "approach the claimant")
    if bykind("proclaim"):
        return select(bykind("proclaim")[0], "proclaim a supported claim")
    if bykind("claim_checkpoint"):
        return select(bykind("claim_checkpoint")[0], "open succession with a completed set")

    collector = policy_name in ("greedy", "collector")
    farmer = policy_name == "prestige_farmer"
    aggressive = policy_name == "aggressive"
    supports_needed = len(me["support"]) < progress["required_support"]
    faction_accessible = obs["phase"] == 2
    # Gear targets read the rule parameters (D41/D43): collectors rush to the
    # checkpoint requirement; other profiles stop at three items.
    claim_requirement = progress["claim_required_equipment"]
    set_target = 3
    gear_needed = len(me["equipment"]) < (claim_requirement if collector else set_target)
    explores = bykind("explore")
    public_dist = _public_distances(obs, me["position"])
    revealed, owned = obs["revealed_districts"], set(me["equipment"])
    useful = [(name, cell) for name, cell in obs["board"]["districts"].items()
              if name in revealed and revealed[name] not in owned]
    preferences = ITEM_PREFERENCES.get(policy_name, {})
    if useful:
        explore_target = min(useful, key=lambda t: (
            public_dist[tuple(t[1])] - 4 * preferences.get(revealed[t[0]], 0), t[1], t[0]))[1]
    else:
        district_targets = [cell for name, cell in obs["board"]["districts"].items()
                            if name not in revealed or revealed[name] not in owned]
        explore_target = min(district_targets, key=lambda c: (public_dist[tuple(c)], c)) if district_targets else None
    if "card_spaces" in obs["board"]:
        # Blind card spaces: target revealed faction spaces, else hunt
        # the nearest unrevealed candidate cell.
        sites = obs["board"]["card_spaces"]
        revealed = sites["revealed"]
        useful_sites = [(tuple(int(v) for v in k.split(",")), f)
                        for k, f in revealed.items() if f and f not in me["support"]]
        factions = [(f, list(c)) for c, f in useful_sites]
        unknown_sites = [tuple(c) for c in sites["candidates"]
                         if f"{c[0]},{c[1]}" not in revealed]
    else:
        factions = [(name, cell) for name, cell in obs["board"]["factions"].items() if name not in me["support"]]
        unknown_sites = []
    faction_target = min(factions, key=lambda f: (public_dist[tuple(f[1])], f[0]))[1] if factions else None
    search_target = min(unknown_sites, key=lambda c: (public_dist[c], c)) if unknown_sites else None
    guards = bykind("guard_post")
    duels = [a for a in bykind("duel") if not a["spend_prestige"]]
    guard_target = (min(obs["board"]["guard_posts"], key=lambda c: (public_dist[tuple(c)], c))
                    if obs["board"]["guard_posts"] else None)
    # Distinct probes stress the economy without changing the core rules.
    if policy_name == "early_support":
        gear_needed = False
    inspects = bykind("inspect")
    if inspects and gear_needed and not useful:
        # Spend the galea on the nearest unknown district instead of
        # blind-walking toward one.
        district_cells = obs["board"]["districts"]
        pick = min(inspects, key=lambda a: (public_dist[tuple(district_cells[a["district"]])], a["district"]))
        return select(pick, "privately inspect a district with the galea")
    if policy_name == "counterleader" and duels and has_room:
        leader = max((pid for pid in obs["players"] if pid != obs["viewer"]),
                     key=lambda pid: (len(obs["players"][pid]["support"]), obs["players"][pid]["equipment_count"]))
        leader_duels = [a for a in duels if a["target"] == leader]
        if leader_duels and len(obs["players"][leader]["support"]) >= progress["required_support"]:
            return select(min(leader_duels, key=duel_key), "contest the leading rival while earning Prestige")
    if collector and gear_needed:
        if explores:
            return select(nearest(explores), "collect equipment for lasting strength")
        if explore_target:
            return toward(explore_target, "seek missing equipment")
    if gear_needed and policy_name not in ("early_support", "prestige_farmer") and explores:
        return select(nearest(explores), "reach the next equipment bonus")
    funding_target = max(progress["support_cost"], (cap if cap is not None else 5)) if farmer else progress["support_cost"]
    want_funding = prestige < funding_target and has_room and (supports_needed or farmer)
    if supports_needed and faction_accessible and not (farmer and want_funding):
        if bykind("gain_support"):
            return select(nearest(bykind("gain_support")), "secure a distinct faction's support")
        if bykind("search_site"):
            return select(nearest(bykind("search_site")), "search a card space")
        if search_target:
            return toward(search_target, "hunt a hidden meeting place")
        if prestige >= progress["support_cost"] and faction_target:
            return toward(faction_target, "visit a faction meeting place")
    if want_funding:
        if aggressive and duels:
            return select(min(duels, key=duel_key), "earn Prestige through combat")
        if guards:
            return select(nearest(guards), "earn Prestige through guard duty")
        if duels:
            return select(min(duels, key=duel_key), "earn Prestige from an available duel")
        if gear_needed and explores:
            return select(nearest(explores), "collect while seeking Prestige")
        if guard_target is not None:
            return toward(guard_target, "reach a source of Prestige")
        if obs["phase"] == 2:
            return toward(checkpoint, "contest the succession at the Peristyle")
        return toward(checkpoint, "converge on the Peristyle")
    if obs["phase"] == 2 and not supports_needed:
        return toward(checkpoint, "take supported authority to the Peristyle")
    if explores:
        return select(nearest(explores), "collect remaining equipment")
    if explore_target:
        return toward(explore_target, "complete the equipment set")
    return toward(checkpoint, "return to the crossing")
