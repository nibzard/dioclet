"""Deterministic engine: rules, state, legal actions, resolution, events.

The engine is a pure state machine. `apply_action(state, ...)` mutates the
state in place and returns the event record for that turn. All randomness
flows through three named RNG streams (placement, movement, battle) whose
states are serialized inside the game state, so a (rules, seed, action
sequence) triple reproduces a game exactly.
"""

import copy
import hashlib
import json
import os
import random
import tempfile
import time

from board import Board, ENGINE_VERSION

STREAMS = ("placement", "movement", "battle")


class EngineError(Exception):
    """Rule or protocol violation; carries a machine-readable code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Rules loading and validation
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "rules_version", "game_name", "players", "equipment", "board",
    "movement", "glory", "combat", "level1", "level2", "logging",
}
# Optional keys: absent from the baseline, defaulted when missing.
OPTIONAL_KEYS = {"turns", "gameplay_mode", "succession"}


def rules_hash(rules):
    canonical = json.dumps(rules, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_rules(path):
    with open(path, "r", encoding="utf-8") as fh:
        rules = json.load(fh)
    validate_rules(rules)
    return rules


def _require(cond, message):
    if not cond:
        raise EngineError("invalid_rules", message)


def validate_rules(rules):
    """Reject invalid configurations with clear errors (SPEC §8)."""
    if not isinstance(rules, dict):
        raise EngineError("invalid_rules", "rules must be a JSON object")
    if rules.get("gameplay_mode") == "succession-v1":
        import succession
        return succession.validate_rules(rules)
    if rules.get("gameplay_mode") is not None or "succession" in rules:
        raise EngineError("invalid_rules", "unknown or incomplete gameplay mode")
    unknown = set(rules) - REQUIRED_KEYS - OPTIONAL_KEYS
    _require(not unknown, f"unknown top-level keys: {sorted(unknown)}")
    missing = REQUIRED_KEYS - set(rules)
    _require(not missing, f"missing top-level keys: {sorted(missing)}")

    _require(rules["players"] == 4, "players must be exactly 4")
    equip = rules["equipment"]
    _require(isinstance(equip, list) and len(equip) == 6,
             "equipment must list exactly 6 names")
    _require(len(set(equip)) == 6, "equipment names must be distinct")
    _require(all(isinstance(n, str) and n for n in equip),
             "equipment names must be non-empty strings")

    board = rules["board"]
    w, h = board["width"], board["height"]
    _require(isinstance(w, int) and w >= 5 and isinstance(h, int) and h >= 5,
             "board must be at least 5x5")

    def in_bounds(c):
        return (isinstance(c, list) and len(c) == 2
                and all(isinstance(v, int) for v in c)
                and 0 <= c[0] < w and 0 <= c[1] < h)

    gates = board["gates"]
    _require(set(gates) == {"P0", "P1", "P2", "P3"}, "gates must be P0..P3")
    gate_cells = []
    for pid, cell in gates.items():
        _require(in_bounds(cell), f"gate {pid} out of bounds: {cell}")
        gate_cells.append(tuple(cell))
    _require(len(set(gate_cells)) == 4, "gates must be distinct cells")

    districts = board["districts"]
    _require(len(districts) == 6, "board.districts must have 6 entries")
    _require(len(set(map(tuple, districts.values()))) == 6,
             "district cells must be distinct")
    for name, cell in districts.items():
        _require(in_bounds(cell), f"district {name} out of bounds: {cell}")

    for key in ("checkpoint",):
        _require(in_bounds(board[key]), f"{key} out of bounds")
    _require(isinstance(board["glory_posts"], list) and len(board["glory_posts"]) == 4,
             "glory_posts must list 4 cells")
    for cell in board["glory_posts"]:
        _require(in_bounds(cell), f"glory post out of bounds: {cell}")
    sites = board["level2_sites"]
    _require(set(sites) == {"cellars", "guard_barracks", "peristyle",
                            "emperor", "retreat"},
             "level2_sites must have cellars, guard_barracks, peristyle, "
             "emperor, retreat")
    for name, cell in sites.items():
        _require(in_bounds(cell), f"level2 site {name} out of bounds: {cell}")

    blocked_raw = board.get("blocked", [])
    _require(isinstance(blocked_raw, list),
             "board.blocked must be a list of [x, y] cells")
    for cell in blocked_raw:
        _require(in_bounds(cell), f"blocked cell out of bounds: {cell}")
    blocked = {tuple(c) for c in blocked_raw}

    # Reachability: every special site must be reachable from gate P0.
    probe = Board(rules)
    dist = probe.distances(probe.gates["P0"])
    special = (list(probe.districts.values()) + list(probe.gates.values())
               + [probe.checkpoint] + probe.glory_posts
               + [tuple(c) for c in sites.values()])
    for cell in special:
        _require(cell not in blocked,
                 f"site {cell} may not be a blocked cell")
        _require(cell in dist, f"site {cell} is not reachable from gate P0")

    movement = rules["movement"]
    die = movement["die_sides"]
    _require(isinstance(die, int) and die >= 2, "die_sides must be >= 2")
    dice_count = movement.get("dice_count", 1)
    _require(isinstance(dice_count, int) and dice_count >= 1,
             "dice_count must be an integer >= 1")
    _require(isinstance(movement["duel_range"], int) and movement["duel_range"] >= 0,
             "duel_range must be >= 0")
    for flag in ("die_is_max_steps", "allow_early_stop", "pass_through_players",
                 "allow_stationary_special_actions"):
        _require(isinstance(movement[flag], bool), f"movement.{flag} must be boolean")
    _require(movement["die_is_max_steps"] and movement["allow_early_stop"],
             "V0.1 requires die_is_max_steps and allow_early_stop to be true")

    glory = rules["glory"]
    _require(isinstance(glory["cap"], int) and glory["cap"] >= 0,
             "glory.cap must be >= 0")
    for key in ("duel_win_reward", "guard_post_reward", "first_challenger_reward"):
        _require(isinstance(glory[key], int) and glory[key] >= 0,
                 f"glory.{key} must be >= 0")
    _require(1 <= glory["guard_post_success_min_roll"] <= die,
             "guard_post_success_min_roll must be within the die")

    combat = rules["combat"]
    for flag in ("duel_glory_theft", "duel_displacement", "duel_lost_turn"):
        if flag in combat:
            _require(isinstance(combat[flag], bool),
                     f"combat.{flag} must be boolean")
    tiers = combat["equipment_bonus_tiers"]
    covered = {}
    for tier in tiers:
        for count in range(tier["min_count"], tier["max_count"] + 1):
            covered.setdefault(count, tier["bonus"])
    for count in range(0, 7):
        _require(count in covered, f"equipment bonus tier missing for count {count}")
        _require(isinstance(covered[count], int) and covered[count] >= 0,
                 f"bonus for count {count} must be >= 0")
    _require(isinstance(combat["tie_goes_to_defender"], bool),
             "tie_goes_to_defender must be boolean")

    turns = rules.get("turns", {})
    _require(isinstance(turns, dict), "turns must be an object")
    _require(isinstance(turns.get("rotate_first_player_each_round", False), bool),
             "turns.rotate_first_player_each_round must be boolean")
    for key in ("imperial_guard_bonus", "emperor_bonus", "glory_attack_bonus"):
        _require(isinstance(combat[key], int) and combat[key] >= 0,
                 f"combat.{key} must be >= 0")
    _require(isinstance(combat["emperor_hits_to_win"], int)
             and combat["emperor_hits_to_win"] >= 1,
             "emperor_hits_to_win must be >= 1")

    level1 = rules["level1"]
    _require(isinstance(level1["max_rounds"], int) and level1["max_rounds"] >= 1,
             "level1.max_rounds must be >= 1")
    _require(isinstance(level1["grace_full_rounds"], int)
             and level1["grace_full_rounds"] >= 0,
             "grace_full_rounds must be >= 0")
    _require(level1["auto_equip_at_transition"] is True,
             "auto_equip_at_transition=false is rejected in V0.1 (DECISIONS.md D11)")

    level2 = rules["level2"]
    _require(isinstance(level2["max_rounds"], int) and level2["max_rounds"] >= 1,
             "level2.max_rounds must be >= 1")
    req = level2["required_distinct_seals"]
    _require(isinstance(req, int) and 1 <= req <= 3,
             "required_distinct_seals must be 1..3")
    for key in ("cellars_success_min_roll", "peristyle_success_min_roll"):
        _require(1 <= level2[key] <= die, f"level2.{key} must be within the die")
    _require(isinstance(level2["peristyle_glory_cost"], int)
             and level2["peristyle_glory_cost"] >= 0,
             "peristyle_glory_cost must be >= 0")

    logging_cfg = rules["logging"]
    _require(isinstance(logging_cfg["save_full_batch_logs"], bool),
             "logging.save_full_batch_logs must be boolean")
    _require(isinstance(logging_cfg["sample_games_per_batch"], int)
             and logging_cfg["sample_games_per_batch"] >= 0,
             "sample_games_per_batch must be >= 0")
    _require(isinstance(logging_cfg["save_anomalous_game_logs"], bool),
             "save_anomalous_game_logs must be boolean")
    return True


def equipment_bonus(count, rules):
    for tier in rules["combat"]["equipment_bonus_tiers"]:
        if tier["min_count"] <= count <= tier["max_count"]:
            return tier["bonus"]
    return 0


# ---------------------------------------------------------------------------
# RNG streams
# ---------------------------------------------------------------------------

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
# Game creation
# ---------------------------------------------------------------------------

def new_game(rules, seed, game_id, policies=None):
    """Create a fresh game state with the first turn's die already rolled."""
    if rules.get("gameplay_mode") == "succession-v1":
        import succession
        return succession.new_game(rules, seed, game_id, policies)
    validate_rules(rules)
    board = Board(rules)
    rngs = {name: _rng_from_seed(seed, name) for name in STREAMS}

    names = sorted(rules["equipment"])
    shuffled = names[:]
    rngs["placement"].shuffle(shuffled)
    district_equipment = dict(zip(sorted(board.districts), shuffled))

    turn_order = ["P0", "P1", "P2", "P3"]
    rngs["placement"].shuffle(turn_order)

    glory_cap = rules["glory"]["cap"]
    players = {}
    for pid in ("P0", "P1", "P2", "P3"):
        players[pid] = {
            "gate": list(board.gates[pid]),
            "pos": list(board.gates[pid]),
            "equipment": [],
            "glory": 0,
            "seals": [],
            "hits": 0,
            "turns": 0,
            "skip_next_turn": False,
        }

    state = {
        "engine_version": ENGINE_VERSION,
        "rules": copy.deepcopy(rules),
        "rules_hash": rules_hash(rules),
        "game_id": game_id,
        "seed": seed,
        "rng": {name: _dump_rng(rngs[name]) for name in STREAMS},
        "turn_order": turn_order,
        "rotate_first": rules.get("turns", {}).get(
            "rotate_first_player_each_round", False),
        "round_start": 0,
        "turn_index": 0,
        "turn_id": 0,
        "round": 1,
        "phase": 1,
        "current_roll": None,
        "players": players,
        "district_equipment": district_equipment,
        "revealed": {},
        "first_challenger": None,
        "trigger_round": None,
        "phase1_timeout": False,
        "phase2_timeout": False,
        "status": "in_progress",
        "winner": None,
        "end_reason": None,
        "rounds_level1": None,
        "event_seq": 0,
        "events": [],
        "created": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
    }
    if policies is not None:
        state["policies"] = dict(policies)
    _start_turn(state)
    return state


def _rng(state, stream):
    return _load_rng(state["rng"][stream])


def _store_rng(state, stream, rng):
    state["rng"][stream] = _dump_rng(rng)


def _start_turn(state):
    """Roll the active player's movement dice; called once per turn start.

    `movement.dice_count` dice of `die_sides` are summed (default 1).
    Challenge and duel rolls always use a single die of `die_sides`.
    """
    rng = _rng(state, "movement")
    movement = state["rules"]["movement"]
    die = sum(rng.randint(1, movement["die_sides"])
              for _ in range(movement.get("dice_count", 1)))
    _store_rng(state, "movement", rng)
    state["current_roll"] = die
    state["turn_id"] += 1
    active = current_order(state)[state["turn_index"]]
    state["active_player"] = active
    state["players"][active]["turns"] += 1


def current_order(state):
    """Seat order for the current round (rotated if the rule is on)."""
    order = state["turn_order"]
    start = state.get("round_start", 0)
    if not state.get("rotate_first"):
        return list(order)
    return [order[(start + i) % len(order)] for i in range(len(order))]


# ---------------------------------------------------------------------------
# Legal actions
# ---------------------------------------------------------------------------

KIND_ORDER = sorted(["move", "explore", "duel", "guard_post", "claim_checkpoint",
                     "attempt_seal", "attack_emperor"])


def legal_actions(state):
    """Enumerate every legal action for the active player this turn."""
    if state.get("gameplay_mode") == "succession-v1":
        import succession
        return succession.legal_actions(state)
    rules = state["rules"]
    board = Board(rules)
    pid = state["active_player"]
    me = state["players"][pid]
    pos = tuple(me["pos"])
    roll = state["current_roll"]
    phase = state["phase"]
    glory_cap = rules["glory"]["cap"]

    dist_from_pos = board.distances(pos)
    candidates = [c for c, d in dist_from_pos.items() if 1 <= d <= roll]

    actions = []

    def add(kind, dest, target=None, spend_glory=None):
        entry = {"kind": kind, "destination": [dest[0], dest[1]],
                 "path": [[x, y] for x, y in board.path(pos, dest)]}
        if target is not None:
            entry["target"] = target
        if spend_glory is not None:
            entry["spend_glory"] = spend_glory
        actions.append(entry)

    for dest in candidates:
        add("move", dest)
        if phase == 1:
            if dest in board.district_at:
                name = board.district_at[dest]
                item = state["district_equipment"][name]
                known_missing = name in state["revealed"] and item not in me["equipment"]
                unrevealed = name not in state["revealed"]
                if known_missing or unrevealed:  # D1: unrevealed stays legal
                    add("explore", dest)
            if dest in board.glory_posts and me["glory"] < glory_cap:
                add("guard_post", dest)
            if dest == board.checkpoint and len(me["equipment"]) == 6 \
                    and state["first_challenger"] is None:
                add("claim_checkpoint", dest)
            _add_duels(state, board, dest, add)
        else:
            _add_duels(state, board, dest, add)
            for site_name, cell in board.seal_sites.items():
                if cell == dest and site_name not in me["seals"]:
                    _add_seal_actions(state, add, site_name, dest)
            if dest == board.emperor and len(set(me["seals"])) >= \
                    rules["level2"]["required_distinct_seals"]:
                _add_emperor_actions(state, add, dest)

    # Stationary special actions (zero-step, SPEC §5).
    if rules["movement"]["allow_stationary_special_actions"]:
        if phase == 1:
            if pos in board.district_at:
                name = board.district_at[pos]
                item = state["district_equipment"][name]
                known_missing = name in state["revealed"] and item not in me["equipment"]
                unrevealed = name not in state["revealed"]
                if known_missing or unrevealed:
                    add("explore", pos)
            if pos == board.checkpoint and len(me["equipment"]) == 6 \
                    and state["first_challenger"] is None:
                add("claim_checkpoint", pos)
        else:
            for site_name, cell in board.seal_sites.items():
                if cell == pos and site_name not in me["seals"]:
                    _add_seal_actions(state, add, site_name, pos)
            if pos == board.emperor and len(set(me["seals"])) >= \
                    rules["level2"]["required_distinct_seals"]:
                _add_emperor_actions(state, add, pos)

    actions.sort(key=_action_sort_key)
    for i, action in enumerate(actions):
        action["action_id"] = f"a{i + 1:04d}"
    return actions


def _action_sort_key(action):
    return (KIND_ORDER.index(action["kind"]),
            action["destination"][0], action["destination"][1],
            action.get("target") or "",
            1 if action.get("spend_glory") else 0)


def _add_duels(state, board, dest, add):
    rules = state["rules"]
    duel_range = rules["movement"]["duel_range"]
    if duel_range <= 0:
        return
    dist = board.distances(dest)
    for other, pdata in sorted(state["players"].items()):
        if other == state["active_player"]:
            continue
        if dist.get(tuple(pdata["pos"]), 99) <= duel_range:
            add("duel", dest, target=other)


def _add_seal_actions(state, add, site_name, dest):
    rules = state["rules"]
    me = state["players"][state["active_player"]]
    if site_name == "peristyle":
        add("attempt_seal", dest, spend_glory=False)
        if me["glory"] >= rules["level2"]["peristyle_glory_cost"]:
            add("attempt_seal", dest, spend_glory=True)
    else:
        add("attempt_seal", dest)


def _add_emperor_actions(state, add, dest):
    me = state["players"][state["active_player"]]
    add("attack_emperor", dest, spend_glory=False)
    if me["glory"] >= 1:  # D8: both variants exactly when Glory >= 1
        add("attack_emperor", dest, spend_glory=True)


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

def observe(state, player):
    """Side-effect-free public observation for one player (SPEC §4)."""
    if state.get("gameplay_mode") == "succession-v1":
        import succession
        return succession.observe(state, player)
    if state["status"] != "in_progress":
        raise EngineError("game_over", "the game has finished; no observation")
    if player != state["active_player"]:
        raise EngineError("not_your_turn",
                          f"it is {state['active_player']}'s turn, not {player}'s")
    rules = state["rules"]
    board = Board(rules)
    actions = legal_actions(state)
    players_public = {}
    for pid, pdata in sorted(state["players"].items()):
        players_public[pid] = {
            "gate": list(pdata["gate"]),
            "position": list(pdata["pos"]),
            "equipment": sorted(pdata["equipment"]),
            "equipment_count": len(pdata["equipment"]),
            "equipment_bonus": equipment_bonus(len(pdata["equipment"]), rules),
            "glory": pdata["glory"],
            "seals": sorted(pdata["seals"]),
            "emperor_hits": pdata["hits"],
            "turns": pdata["turns"],
            "skip_next_turn": bool(pdata.get("skip_next_turn")),
        }
    progress = {
        "first_challenger": state["first_challenger"],
        "players_with_full_equipment": [
            p for p, d in sorted(state["players"].items())
            if len(d["equipment"]) == 6
        ],
    }
    if state["phase"] == 1:
        progress["level1_max_rounds"] = rules["level1"]["max_rounds"]
        progress["grace_full_rounds"] = rules["level1"]["grace_full_rounds"]
        if state["first_challenger"] is not None:
            end = min(state["trigger_round"] + rules["level1"]["grace_full_rounds"],
                      rules["level1"]["max_rounds"])
            progress["transition_after_round"] = end
    else:
        progress["level2_max_rounds"] = rules["level2"]["max_rounds"]
        progress["seals_required"] = rules["level2"]["required_distinct_seals"]
        progress["emperor_hits_to_win"] = rules["combat"]["emperor_hits_to_win"]
    return {
        "game_id": state["game_id"],
        "seed": state["seed"],
        "engine_version": state["engine_version"],
        "status": state["status"],
        "phase": state["phase"],
        "round": state["round"],
        "turn_id": state["turn_id"],
        "active_player": state["active_player"],
        "viewer": player,
        "movement_die": state["current_roll"],
        "turn_order": current_order(state),
        "board": {
            "width": board.width, "height": board.height,
            "gates": {p: list(c) for p, c in board.gates.items()},
            "districts": {n: list(c) for n, c in board.districts.items()},
            "glory_posts": [list(c) for c in board.glory_posts],
            "checkpoint": list(board.checkpoint),
            "seal_sites": {n: list(c) for n, c in board.seal_sites.items()},
            "emperor": list(board.emperor),
            "retreat": list(board.retreat),
        },
        "revealed_districts": {n: i for n, i in sorted(state["revealed"].items())},
        "glory_cap": rules["glory"]["cap"],
        "equipment_names": sorted(rules["equipment"]),
        "players": players_public,
        "progress": progress,
        "legal_actions": actions,
    }


# ---------------------------------------------------------------------------
# Action resolution
# ---------------------------------------------------------------------------

def apply_action(state, player, turn_id, action_id, reason=None):
    """Resolve one legal action for the active player; returns the record."""
    if state.get("gameplay_mode") == "succession-v1":
        import succession
        return succession.apply_action(state, player, turn_id, action_id, reason)
    if state["status"] != "in_progress":
        raise EngineError("game_over", "the game has finished; no actions")
    if player != state["active_player"]:
        raise EngineError("not_your_turn", f"it is {state['active_player']}'s turn")
    if turn_id != state["turn_id"]:
        raise EngineError("stale_turn_id",
                          f"expected turn_id {state['turn_id']}, got {turn_id}")
    actions = {a["action_id"]: a for a in legal_actions(state)}
    if action_id not in actions:
        raise EngineError("legal_action_error",
                          f"unknown or illegal action_id {action_id!r}")
    action = actions[action_id]
    rules = state["rules"]
    board = Board(rules)
    me = state["players"][player]
    phase = state["phase"]
    events = []
    dice_used = []

    def battle_die():
        rng = _rng(state, "battle")
        value = rng.randint(1, rules["movement"]["die_sides"])
        _store_rng(state, "battle", rng)
        dice_used.append(value)
        return value

    def grant_glory(pid, amount, cause):
        pdata = state["players"][pid]
        cap = rules["glory"]["cap"]
        room = cap - pdata["glory"]
        awarded = max(0, min(amount, room))
        pdata["glory"] += awarded
        wasted = amount - awarded
        event = {"type": cause, "player": pid, "glory_awarded": awarded}
        if wasted > 0:
            event["glory_wasted_at_cap"] = wasted  # D3, D15
        events.append(event)

    kind = action["kind"]
    dest = tuple(action["destination"])
    # Movement resolves first; later branches (emperor miss) may override.
    me["pos"] = [dest[0], dest[1]]

    if kind == "explore":
        name = board.district_at[dest]
        item = state["district_equipment"][name]
        if name not in state["revealed"]:
            state["revealed"][name] = item
            events.append({"type": "district_revealed", "district": name,
                           "item": item})
        if item not in me["equipment"]:
            me["equipment"].append(item)
            events.append({"type": "equipment_collected", "player": player,
                           "item": item, "district": name, "source": "explored"})
        else:
            events.append({"type": "explore_no_gain", "player": player,
                           "district": name, "reason": "already_owned"})  # D1

    elif kind == "guard_post":
        roll = battle_die()
        success = roll >= rules["glory"]["guard_post_success_min_roll"]
        events.append({"type": "guard_post", "player": player, "roll": roll,
                       "success": success})
        if success:
            grant_glory(player, rules["glory"]["guard_post_reward"],
                        "glory_earned_guard_post")

    elif kind == "duel":
        opponent = action["target"]
        them = state["players"][opponent]
        a_roll, d_roll = battle_die(), battle_die()
        a_score = a_roll + equipment_bonus(len(me["equipment"]), rules)
        d_score = d_roll + equipment_bonus(len(them["equipment"]), rules)
        if a_score > d_score:
            winner = player
        elif a_score < d_score:
            winner = opponent
        elif rules["combat"]["tie_goes_to_defender"]:
            winner = opponent
        else:
            winner = player
        loser = opponent if winner == player else player
        duel_event = {
            "type": "duel", "attacker": player, "defender": opponent,
            "attacker_roll": a_roll, "defender_roll": d_roll,
            "attacker_bonus": a_score - a_roll, "defender_bonus": d_score - d_roll,
            "attacker_score": a_score, "defender_score": d_score,
            "winner": winner,
        }
        events.append(duel_event)
        winner_data = state["players"][winner]
        loser_data = state["players"][loser]
        if rules["combat"].get("duel_glory_theft"):
            # D21: the winner's reward comes from the loser, not the bank.
            paid = min(1, loser_data["glory"])
            if paid:
                loser_data["glory"] -= paid
                room = rules["glory"]["cap"] - winner_data["glory"]
                kept = max(0, min(paid, room))
                winner_data["glory"] += kept
                events.append({"type": "glory_stolen", "winner": winner,
                               "loser": loser, "amount": paid,
                               "kept_by_winner": kept,
                               "wasted_at_cap": paid - kept})
        else:
            grant_glory(winner, rules["glory"]["duel_win_reward"],
                        "glory_earned_duel")
        if rules["combat"].get("duel_displacement"):
            # D22: the loser is moved to the retreat node.
            from_cell = list(loser_data["pos"])
            loser_data["pos"] = list(board.retreat)
            events.append({"type": "duel_displacement", "loser": loser,
                           "from": from_cell, "to": list(board.retreat)})
        if rules["combat"].get("duel_lost_turn"):
            # D23: the loser forfeits their next turn.
            loser_data["skip_next_turn"] = True
            events.append({"type": "turn_loss_scheduled", "loser": loser})

    elif kind == "claim_checkpoint":
        state["first_challenger"] = player
        state["trigger_round"] = state["round"]
        events.append({"type": "first_challenger", "player": player,
                       "round": state["round"]})
        grant_glory(player, rules["glory"]["first_challenger_reward"],
                    "glory_earned_first_challenger")

    elif kind == "attempt_seal":
        site_name = board.seal_site_at[dest]
        spend = action.get("spend_glory", False)
        if site_name == "cellars":
            roll = battle_die()
            success = roll >= rules["level2"]["cellars_success_min_roll"]
            detail = {"roll": roll}
        elif site_name == "guard_barracks":
            p_roll, g_roll = battle_die(), battle_die()
            p_score = p_roll + equipment_bonus(len(me["equipment"]), rules)
            g_score = g_roll + rules["combat"]["imperial_guard_bonus"]
            success = p_score > g_score
            detail = {"player_roll": p_roll, "guard_roll": g_roll,
                      "player_score": p_score, "guard_score": g_score}
        else:  # peristyle
            if spend:
                cost = rules["level2"]["peristyle_glory_cost"]
                me["glory"] -= cost
                success = True
                detail = {"glory_spent": cost}
                events.append({"type": "glory_spent", "player": player,
                               "amount": cost, "purpose": "peristyle_seal"})
            else:
                roll = battle_die()
                success = roll >= rules["level2"]["peristyle_success_min_roll"]
                detail = {"roll": roll}
        if success and site_name not in me["seals"]:
            me["seals"].append(site_name)
            events.append({"type": "seal_acquired", "player": player,
                           "site": site_name, "order": len(me["seals"]),
                           **detail})
        else:
            events.append({"type": "seal_failed", "player": player,
                           "site": site_name, **detail})

    elif kind == "attack_emperor":
        spend = action.get("spend_glory", False)
        p_roll = battle_die()
        e_roll = battle_die()
        p_score = p_roll + equipment_bonus(len(me["equipment"]), rules)
        if spend:
            me["glory"] -= 1
            p_score += rules["combat"]["glory_attack_bonus"]
            events.append({"type": "glory_spent", "player": player, "amount": 1,
                           "purpose": "emperor_attack"})
        e_score = e_roll + rules["combat"]["emperor_bonus"]
        success = p_score > e_score  # tie -> emperor
        if success:
            me["hits"] += 1
            events.append({"type": "emperor_hit", "player": player,
                           "player_roll": p_roll, "emperor_roll": e_roll,
                           "player_score": p_score, "emperor_score": e_score,
                           "hits": me["hits"], "spend_glory": spend})
            if me["hits"] >= rules["combat"]["emperor_hits_to_win"]:
                state["status"] = "finished"
                state["winner"] = player
                state["end_reason"] = "emperor"
                events.append({"type": "game_won", "player": player})
        else:
            me["pos"] = list(board.retreat)
            events.append({"type": "emperor_miss", "player": player,
                           "player_roll": p_roll, "emperor_roll": e_roll,
                           "player_score": p_score, "emperor_score": e_score,
                           "retreat_to": list(board.retreat),
                           "spend_glory": spend})

    elif kind == "move":
        pass

    else:  # pragma: no cover - kind generated by legal_actions only
        raise EngineError("legal_action_error", f"unknown kind {kind}")

    record = {
        "event_seq": state["event_seq"] + 1,
        "turn_id": state["turn_id"],
        "round": state["round"],
        "phase": state["phase"],
        "player": player,
        "movement_die": state["current_roll"],
        "action_id": action_id,
        "action": {k: v for k, v in action.items() if k != "action_id"},
        "dice_used": dice_used,
        "events": events,
        "position_after": list(me["pos"]),
        "glory_after": me["glory"],
        "equipment_count_after": len(me["equipment"]),
    }
    if reason is not None:
        record["reason"] = reason
    state["event_seq"] += 1
    state["events"].append(record)
    _advance(state)
    return record


def _advance(state):
    """Move to the next player; handle skips, wraps, transitions, endings."""
    if state["status"] != "in_progress":
        return  # game already won this turn; keep the final round's order
    rules = state["rules"]
    while True:
        state["turn_index"] += 1
        if state["turn_index"] >= len(state["turn_order"]):
            state["turn_index"] = 0
            state["round"] += 1
            if state.get("rotate_first"):
                state["round_start"] = (state.get("round_start", 0) + 1) % len(
                    state["turn_order"])
            if state["phase"] == 1:
                l1 = rules["level1"]
                if state["first_challenger"] is not None:
                    end = min(state["trigger_round"] + l1["grace_full_rounds"],
                              l1["max_rounds"])  # D4
                else:
                    end = l1["max_rounds"]
                if state["round"] > end:
                    _transition_to_level2(state)
                    return
            elif state["round"] > rules["level2"]["max_rounds"]:
                state["status"] = "finished"
                state["winner"] = None
                state["end_reason"] = "phase2_timeout"
                state["phase2_timeout"] = True
                state["current_roll"] = None
                state["round"] = rules["level2"]["max_rounds"]  # completed
                state["events"][-1]["events"].append({
                    "type": "game_draw", "reason": "phase2_timeout"})
                return
        active = current_order(state)[state["turn_index"]]
        if state["players"][active].get("skip_next_turn"):  # D23
            state["players"][active]["skip_next_turn"] = False
            state["players"][active]["turns"] += 1
            state["turn_id"] += 1
            state["event_seq"] += 1
            state["events"].append({
                "event_seq": state["event_seq"],
                "turn_id": state["turn_id"],
                "round": state["round"],
                "phase": state["phase"],
                "player": active,
                "movement_die": None,
                "action_id": None,
                "action": {"kind": "skip_turn"},
                "dice_used": [],
                "events": [{"type": "turn_skipped", "player": active}],
                "position_after": list(state["players"][active]["pos"]),
                "glory_after": state["players"][active]["glory"],
                "equipment_count_after": len(
                    state["players"][active]["equipment"]),
            })
            continue
        break
    _start_turn(state)


def _transition_to_level2(state):
    """End Level 1: auto-equip, reset pawns, start Level 2 round 1 (SPEC §6)."""
    rules = state["rules"]
    board = Board(rules)
    if state["first_challenger"] is None:
        state["phase1_timeout"] = True
    state["rounds_level1"] = state["round"] - 1
    auto = {}
    transition_events = []
    for pid, pdata in sorted(state["players"].items()):
        granted = [item for item in sorted(rules["equipment"])
                   if item not in pdata["equipment"]]
        pdata["equipment"] = sorted(rules["equipment"])
        pdata["pos"] = list(pdata["gate"])
        pdata["seals"] = []
        pdata["hits"] = 0
        auto[pid] = granted
        for item in granted:
            transition_events.append({
                "type": "auto_equipment_granted", "player": pid, "item": item})
    transition_events.append({"type": "phase_transition", "from_phase": 1,
                              "to_phase": 2, "auto_granted": auto,
                              "phase1_timeout": state["phase1_timeout"]})
    state["events"][-1]["events"].extend(transition_events)
    state["phase"] = 2
    state["round"] = 1
    state["turn_index"] = 0
    state["round_start"] = 0  # Level 2 restarts from the base order
    _start_turn(state)


def is_finished(state):
    return state["status"] != "in_progress"


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
# Result and metrics
# ---------------------------------------------------------------------------

def result(state):
    """Terminal summary computed from the event log (SPEC §11)."""
    if state.get("gameplay_mode") == "succession-v1":
        import succession
        return succession.result(state)
    rules = state["rules"]
    board = Board(rules)
    turns_l1 = [r for r in state["events"] if r["phase"] == 1]
    metrics = {}
    for pid in state["players"]:
        metrics[pid] = {
            "gate": [board.gates[pid][0], board.gates[pid][1]],
            "turns": state["players"][pid]["turns"],
            "glory_final": state["players"][pid]["glory"],
            "glory_earned": 0, "glory_spent": 0, "glory_wasted_at_cap": 0,
            "equipment_collected": 0, "auto_granted": 0,
            "explores": 0, "explore_no_gain": 0,
            "guard_post_attempts": 0, "guard_post_successes": 0,
            "duels_initiated": 0, "duels_won_attacker": 0,
            "duels_won_defender": 0, "duels_defended": 0,
            "glory_stolen": 0, "glory_lost_theft": 0,
            "times_displaced": 0, "turns_skipped": 0,
            "chamber_evictions": 0,
            "seals": [], "seal_attempts": 0,
            "seal_attempts_by_site": {"cellars": 0, "guard_barracks": 0,
                                      "peristyle": 0},
            "emperor_attempts": 0, "emperor_hits": state["players"][pid]["hits"],
            "glory_spent_peristyle": 0, "glory_spent_emperor": 0,
            "districts_explored": set(),
        }
    for record in state["events"]:
        pid = record["player"]
        m = metrics[pid]
        kind = record["action"]["kind"]
        last_duel_winner = None
        for ev in record["events"]:
            if ev["type"] == "duel":
                last_duel_winner = ev["winner"]
        if kind == "explore":
            m["explores"] += 1
            m["districts_explored"].add(tuple(record["action"]["destination"]))
        if kind == "duel":
            m["duels_initiated"] += 1
        if kind == "attack_emperor":
            m["emperor_attempts"] += 1
        for ev in record["events"]:
            t = ev["type"]
            tm = metrics[ev["player"]] if "player" in ev else m
            if t.startswith("glory_earned"):
                tm["glory_earned"] += ev.get("glory_awarded", 0)
                tm["glory_wasted_at_cap"] += ev.get("glory_wasted_at_cap", 0)
            elif t == "glory_spent":
                tm["glory_spent"] += ev["amount"]
                if ev["purpose"] == "peristyle_seal":
                    tm["glory_spent_peristyle"] += ev["amount"]
                elif ev["purpose"] == "emperor_attack":
                    tm["glory_spent_emperor"] += ev["amount"]
            elif t == "equipment_collected":
                tm["equipment_collected"] += 1
            elif t == "auto_equipment_granted":
                tm["auto_granted"] += 1
            elif t == "explore_no_gain":
                tm["explore_no_gain"] += 1
            elif t == "guard_post":
                tm["guard_post_attempts"] += 1
                tm["guard_post_successes"] += 1 if ev["success"] else 0
            elif t == "duel":
                defender = metrics[ev["defender"]]
                defender["duels_defended"] += 1
                if ev["winner"] == ev["attacker"]:
                    m["duels_won_attacker"] += 1
                else:
                    defender["duels_won_defender"] += 1
            elif t == "glory_stolen":
                metrics[ev["winner"]]["glory_stolen"] += ev["kept_by_winner"]
                metrics[ev["loser"]]["glory_lost_theft"] += ev["amount"]
            elif t == "duel_displacement":
                metrics[ev["loser"]]["times_displaced"] += 1
                if (ev["from"] == [board.emperor[0], board.emperor[1]]
                        and last_duel_winner):
                    metrics[last_duel_winner]["chamber_evictions"] += 1
            elif t == "turn_skipped":
                metrics[ev["player"]]["turns_skipped"] += 1
            elif t == "seal_acquired":
                tm["seals"].append(ev["site"])
                tm["seal_attempts_by_site"][ev["site"]] += 1
            elif t == "seal_failed":
                tm["seal_attempts_by_site"][ev["site"]] += 1
    for m in metrics.values():
        m["seal_attempts"] = sum(m["seal_attempts_by_site"].values())
        m["districts_explored"] = len(m["districts_explored"])

    high_impact = []
    for record in state["events"]:
        for ev in record["events"]:
            if ev["type"] in ("first_challenger", "duel", "seal_acquired",
                              "emperor_hit", "emperor_miss", "phase_transition",
                              "duel_displacement", "game_won", "game_draw"):
                high_impact.append({"turn_id": record["turn_id"],
                                    "round": record["round"],
                                    "phase": record["phase"],
                                    **ev})

    comeback = None
    if state["winner"] and state["first_challenger"]:
        comeback = state["winner"] != state["first_challenger"]  # D16

    return {
        "game_id": state["game_id"],
        "seed": state["seed"],
        "rules_hash": state["rules_hash"],
        "engine_version": state["engine_version"],
        "outcome": "win" if state["winner"] else "draw",
        "winner": state["winner"],
        "end_reason": state["end_reason"],
        "first_challenger": state["first_challenger"],
        "first_challenger_won": (state["first_challenger"] == state["winner"]
                                 if state["first_challenger"] else None),
        "comeback_win": comeback,
        "phase1_timeout": state["phase1_timeout"],
        "phase2_timeout": state["phase2_timeout"],
        "rounds_level1": state["rounds_level1"],
        "rounds_level2": state["round"] if state["phase"] == 2 else 0,
        "turns_level1": len(turns_l1),
        "turns_level2": len(state["events"]) - len(turns_l1),
        "total_turns": len(state["events"]),
        "total_rounds": ((state["rounds_level1"] or 0)
                         + (state["round"] if state["phase"] == 2 else 0)),
        "policies": state.get("policies", {}),
        "turn_order": current_order(state),
        "players": metrics,
        "high_impact_events": high_impact,
    }


# ---------------------------------------------------------------------------
# Invariant checker (tests and anomaly detection)
# ---------------------------------------------------------------------------

def check_invariants(state):
    """Raise AssertionError if the state breaks a core invariant (SPEC §14)."""
    if state.get("gameplay_mode") == "succession-v1":
        import succession
        return succession.check_invariants(state)
    rules = state["rules"]
    board = Board(rules)
    cap = rules["glory"]["cap"]
    names = set(rules["equipment"])
    for pid, p in state["players"].items():
        assert board.in_bounds(tuple(p["pos"])), f"{pid} off board"
        assert 0 <= p["glory"] <= cap, f"{pid} glory {p['glory']} outside 0..{cap}"
        assert len(p["equipment"]) == len(set(p["equipment"])), f"{pid} dup gear"
        assert set(p["equipment"]) <= names, f"{pid} unknown gear"
        assert len(p["seals"]) == len(set(p["seals"])), f"{pid} dup seals"
        assert set(p["seals"]) <= set(board.seal_sites), f"{pid} bad seal"
        assert p["hits"] <= rules["combat"]["emperor_hits_to_win"], f"{pid} hits"
        if state["phase"] == 2:
            assert len(p["equipment"]) == 6, f"{pid} not fully equipped in phase 2"
    if state["status"] == "finished":
        if state["winner"] is None:
            assert state["phase2_timeout"], "draw without phase2_timeout"
        else:
            w = state["players"][state["winner"]]
            assert w["hits"] == rules["combat"]["emperor_hits_to_win"], \
                "winner without enough emperor hits"
    for record in state["events"]:
        path = record["action"].get("path")
        if path is not None:
            assert len(path) - 1 <= record["movement_die"], "moved beyond the die"
        kinds = [ev["type"] for ev in record["events"]]
        if "emperor_miss" in kinds:
            assert record["position_after"] == [board.retreat[0],
                                                board.retreat[1]], \
                "emperor miss did not end at the retreat node"
    # Unrevealed mapping must never appear in any observation (spot check).
    actions_log = json.dumps(state["events"], sort_keys=True)
    for name, item in state["district_equipment"].items():
        if name not in state["revealed"]:
            assert f'"district": "{name}", "item": "{item}"' not in actions_log, \
                "unrevealed mapping leaked into the event log"
    return True
