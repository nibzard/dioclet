"""V0.8 succession rules, separate from the archived Emperor rules.

The state and observation APIs match engine.py. Randomness uses five
serialized xorshift32 streams, shared with the browser implementation.
"""

import copy
import json
import time

from board import Board, validate_six_block_layout

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
_BOARDS = {}


def _error(code, message):
    from engine import EngineError
    raise EngineError(code, message)


def _validate_abilities(rules, abilities):
    if not isinstance(abilities, dict):
        _error("invalid_rules", "combat.abilities must be an object keyed by equipment name")
    if set(abilities) != set(rules["equipment"]):
        _error("invalid_rules", "combat.abilities must define one ability for each equipment name")
    for item, spec in sorted(abilities.items()):
        if not isinstance(spec, dict) or set(spec) != {"type", "value"}:
            _error("invalid_rules", f"combat.abilities.{item} must be an object with type and value")
        if spec["type"] not in ABILITY_TYPES:
            _error("invalid_rules",
                   f"combat.abilities.{item}.type must be one of: {', '.join(ABILITY_TYPES)}")
        if type(spec["value"]) is not int or not 0 <= spec["value"] <= 3:
            _error("invalid_rules", f"combat.abilities.{item}.value must be an integer from 0 to 3")


def validate_rules(rules):
    """Validate shared fields through the unchanged legacy validator."""
    import engine
    legacy = copy.deepcopy(rules)
    legacy.pop("gameplay_mode", None)
    config = legacy.pop("succession", None)
    legacy.pop("start_reveals", None)
    legacy.pop("board_level2", None)
    if rules.get("gameplay_mode") != MODE or not isinstance(config, dict):
        _error("invalid_rules", "succession-v1 needs a succession object")
    missing = engine.REQUIRED_KEYS - set(rules)
    if missing:
        _error("invalid_rules", f"missing top-level keys: {sorted(missing)}")
    allowed = {"support_cost", "required_support", "support_in_city", "challenge_cost",
               "challenge_bonus", "contest_cost", "reset_positions", "gate_assignment",
               "gate_order", "gate_rotation", "factions",
               "claim_window_rounds", "challenge_radius", "duel_loser_cost",
               "proclaim_cost", "blind_support"}
    unknown = set(config) - allowed
    if unknown:
        _error("invalid_rules", f"unknown succession keys: {sorted(unknown)}")
    for name, ceiling in (("claim_window_rounds", 6), ("challenge_radius", 8),
                          ("duel_loser_cost", 3), ("proclaim_cost", 3)):
        value = config.get(name, 0)
        if type(value) is not int or not 0 <= value <= ceiling:
            _error("invalid_rules", f"succession.{name} must be an integer from 0 to {ceiling}")
    if type(config.get("blind_support", False)) is not bool:
        _error("invalid_rules", "succession.blind_support must be boolean")
    stacking = rules["combat"].get("ability_stacking", "best")
    if stacking not in ("best", "sum"):
        _error("invalid_rules", "combat.ability_stacking must be best or sum")
    # The engine reads only these combat keys; anything else is a dead
    # key that silently no-ops an experiment arm (the S2 screen set a
    # nonexistent combat.challenge_bonus while the live knob sits under
    # succession.challenge_bonus).
    known_combat = {"equipment_bonus_tiers", "tie_goes_to_defender",
                    "imperial_guard_bonus", "emperor_bonus", "glory_attack_bonus",
                    "emperor_hits_to_win", "duel_displacement", "duel_glory_theft",
                    "duel_lost_turn", "abilities", "ability_stacking"}
    unknown_combat = set(rules["combat"]) - known_combat
    if unknown_combat:
        _error("invalid_rules",
               f"unknown combat keys (nothing reads them): {sorted(unknown_combat)}")
    start_reveals = rules.get("start_reveals", 0)
    if type(start_reveals) is not int or not 0 <= start_reveals <= 6:
        _error("invalid_rules", "start_reveals must be an integer from 0 to 6")
    required = rules["level1"].get("claim_required_equipment", 6)
    if type(required) is not int or not 1 <= required <= 6:
        _error("invalid_rules", "level1.claim_required_equipment must be an integer from 1 to 6")
    set_reward = rules["glory"].get("set_completion_reward", 0)
    if type(set_reward) is not int or set_reward < 0:
        _error("invalid_rules", "glory.set_completion_reward must be a nonnegative integer")
    abilities = rules["combat"].get("abilities")
    if abilities is not None:
        _validate_abilities(rules, abilities)
        nonzero_tiers = [t["bonus"] for t in rules["combat"]["equipment_bonus_tiers"] if t["bonus"]]
        if nonzero_tiers:
            _error("invalid_rules",
                   "combat.abilities replace the count tiers; every equipment_bonus_tiers bonus must be 0")
    cap = legacy["glory"]["cap"]
    if cap is None:
        legacy["glory"]["cap"] = 0
    legacy["level1"]["auto_equip_at_transition"] = True
    engine.validate_rules(legacy)
    try:
        validate_six_block_layout(rules)
    except (KeyError, TypeError, ValueError) as exc:
        _error("invalid_rules", f"invalid succession layout: {exc}")
    if rules["level1"]["auto_equip_at_transition"] is not False:
        _error("invalid_rules", "succession keeps collected equipment; auto-equipping must be false")
    for name in ("support_cost", "challenge_cost", "required_support"):
        if type(config.get(name)) is not int or config[name] < 1:
            _error("invalid_rules", f"succession.{name} must be a positive integer")
    if cap is not None and (type(cap) is not int or cap < config["support_cost"]):
        _error("invalid_rules", "Prestige cap must cover at least one support purchase, or be null")
    if type(config.get("contest_cost", 0)) is not int or config.get("contest_cost", 0) < 0:
        _error("invalid_rules", "succession.contest_cost must be a nonnegative integer")
    if type(config.get("challenge_bonus")) is not int or config["challenge_bonus"] < 0:
        _error("invalid_rules", "succession.challenge_bonus must be a nonnegative integer")
    for name in ("support_in_city", "reset_positions"):
        if not isinstance(config.get(name), bool):
            _error("invalid_rules", f"succession.{name} must be boolean")
    if config.get("gate_assignment", "random") not in ("random", "manual", "rotation"):
        _error("invalid_rules", "gate_assignment must be random, manual, or rotation")
    if config.get("gate_order") is not None and (
            not isinstance(config["gate_order"], list) or sorted(config["gate_order"]) != list(IDS)):
        _error("invalid_rules", "gate_order must contain each of P0..P3 once")
    rotation = config.get("gate_rotation", 0)
    if type(rotation) is not int or not 0 <= rotation < 4:
        _error("invalid_rules", "gate_rotation must be 0..3")
    factions = config.get("factions")
    if not isinstance(factions, dict) or set(factions) != {"army", "officials", "elites"}:
        _error("invalid_rules", "factions must define army, officials, and elites")
    b = Board(rules, "board_level2") if "board_level2" in rules else Board(rules)
    reachable = b.distances(b.gates["P0"])
    for name, cell in factions.items():
        if not isinstance(cell, list) or len(cell) != 2 or tuple(cell) not in reachable:
            board_name = "board_level2" if "board_level2" in rules else "board"
            _error("invalid_rules",
                   f"faction {name} must occupy a reachable street on {board_name}")
    if len(set(map(tuple, factions.values()))) != 3:
        _error("invalid_rules", "faction meeting places must be distinct")
    if config["required_support"] > len(factions):
        _error("invalid_rules", "required_support exceeds the number of factions")
    if "board_level2" in rules:
        _validate_board_level2(rules, config)
    return True


def _validate_board_level2(rules, config):
    """A separate succession map: four gates, a checkpoint, optional
    posts, no districts and no six-block contract (that layout is the
    palace level's)."""
    twin = rules["board_level2"]
    if not isinstance(twin, dict):
        _error("invalid_rules", "board_level2 must be an object")
    for key in ("width", "height"):
        value = twin.get(key)
        if type(value) is not int or value < 5:
            _error("invalid_rules", f"board_level2.{key} must be an integer of at least 5")
    blocked = {tuple(c) for c in twin.get("blocked", [])}
    def in_bounds(cell):
        return (isinstance(cell, list) and len(cell) == 2
                and all(isinstance(v, int) for v in cell)
                and 0 <= cell[0] < twin["width"] and 0 <= cell[1] < twin["height"])
    gates = twin.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(IDS):
        _error("invalid_rules", "board_level2.gates must define P0..P3")
    for pid, cell in gates.items():
        if not in_bounds(cell) or tuple(cell) in blocked:
            _error("invalid_rules", f"board_level2 gate {pid} out of bounds or blocked")
    if len({tuple(c) for c in gates.values()}) != 4:
        _error("invalid_rules", "board_level2 gates must be distinct")
    if not in_bounds(twin.get("checkpoint")) or tuple(twin["checkpoint"]) in blocked:
        _error("invalid_rules", "board_level2.checkpoint out of bounds or blocked")
    if twin.get("districts"):
        _error("invalid_rules", "board_level2 carries no districts; treasures live on the palace map")
    posts = twin.get("glory_posts", [])
    if not isinstance(posts, list):
        _error("invalid_rules", "board_level2.glory_posts must be a list")
    for cell in posts:
        if not in_bounds(cell) or tuple(cell) in blocked:
            _error("invalid_rules", "board_level2 glory post out of bounds or blocked")
    if config.get("blind_support"):
        _error("invalid_rules",
               "blind_support re-deals the palace districts; it cannot combine with board_level2")
    b = Board(rules, "board_level2")
    if set(b.districts) or b.district_at:
        _error("invalid_rules", "board_level2 must not declare districts")
    claimed = [(name, tuple(cell)) for name, cell in config["factions"].items()]
    claimed += [("glory post", tuple(cell)) for cell in twin.get("glory_posts", [])]
    for pid, cell in gates.items():
        occupied = tuple(cell)
        if occupied == tuple(twin["checkpoint"]):
            _error("invalid_rules", f"board_level2 gate {pid} sits on the checkpoint")
        for name, site in claimed:
            if occupied == site:
                _error("invalid_rules",
                       f"board_level2 gate {pid} sits on {name} - seats may not start on content")
    for pid, gate in b.gates.items():
        reach = b.distances(gate)
        if b.checkpoint not in reach:
            _error("invalid_rules", f"board_level2 checkpoint unreachable from gate {pid}")
    reach = b.distances(b.gates["P0"])
    for cell in b.glory_posts:
        if cell not in reach:
            _error("invalid_rules", "board_level2 glory post unreachable")
    for name, cell in config["factions"].items():
        if tuple(cell) == b.checkpoint:
            _error("invalid_rules", f"faction {name} sits on the board_level2 checkpoint")


def _board(rules, phase=1):
    """The active Board: the level-1 palace map, or the separate
    succession map in phase 2 when the rules declare one."""
    section = "board_level2" if (phase == 2 and "board_level2" in rules) else "board"
    key = json.dumps([section, rules.get(section)], sort_keys=True, separators=(",", ":"))
    if key not in _BOARDS:
        b = Board(rules, section)
        b._succ_distances = {}
        b._succ_paths = {}
        _BOARDS[key] = b
    return _BOARDS[key]


def _gate_cell(state, player, phase=None):
    """The player's gate on the ACTIVE board (twin-board games move
    the gates to the succession map in phase 2)."""
    phase = state["phase"] if phase is None else phase
    section = "board_level2" if ("board_level2" in state["rules"] and phase == 2) else "board"
    return list(state["rules"][section]["gates"][player["gate_id"]])


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


def _usable_ability(player, rules, ability_type):
    """Return (item, spec) for an owned, unused, nonzero ability of this type."""
    for item in player["equipment"]:
        spec = rules["combat"].get("abilities", {}).get(item)
        if (spec and spec["type"] == ability_type and spec["value"] > 0
                and not player["abilities_used"].get(ability_type)):
            return item, spec
    return None, None


def _ability_total(player, rules, ability_type):
    """Public rule fact: total value of owned abilities of this type."""
    total = 0
    for item in player["equipment"]:
        spec = rules["combat"].get("abilities", {}).get(item)
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


def new_game(rules, seed, game_id, policies=None):
    from engine import rules_hash
    validate_rules(rules)
    config = rules["succession"]
    state = {
        "gameplay_mode": MODE, "engine_version": VERSION,
        "rules": copy.deepcopy(rules), "rules_hash": rules_hash(rules),
        "game_id": game_id, "seed": seed,
        "rng": {name: ((int(seed) & 0xFFFFFFFF) ^ salt) or 1 for name, salt in SALTS.items()},
        "players": {}, "turn_order": [], "round_start": 0, "turn_index": 0,
        "rotate_first": rules.get("turns", {}).get("rotate_first_player_each_round", False),
        "turn_id": 0, "round": 1, "phase": 1, "current_roll": None,
        "pending_claim": None, "first_challenger": None, "trigger_round": None,
        "district_equipment": {}, "revealed": {}, "equipment_at_transition": {},
        "faction_sites": None, "faction_sites_revealed": None,
        "phase1_timeout": False, "phase2_timeout": False, "rounds_level1": None,
        "status": "in_progress", "winner": None, "end_reason": None,
        "event_seq": 0, "events": [], "policies": dict(policies or {}),
        "policy_version": POLICY_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    gate_order = list(config.get("gate_order") or IDS)
    if config.get("gate_assignment", "random") == "random" and not config.get("gate_order"):
        gate_order = _shuffle(state, IDS, "gates")
    rotation = config.get("gate_rotation", 0)
    gate_order = gate_order[rotation:] + gate_order[:rotation]
    state["gate_assignments"] = dict(zip(IDS, gate_order))
    for pid, gateid in state["gate_assignments"].items():
        gate = list(rules["board"]["gates"][gateid])
        state["players"][pid] = {"gate_id": gateid, "gate": gate, "pos": gate[:],
                                  "equipment": [], "prestige": 0, "support": [],
                                  "turns": 0, "stats": _stats(),
                                  "abilities_used": {}, "set_rewarded": False}
    state["turn_order"] = _shuffle(state, IDS, "order")
    equipment = _shuffle(state, rules["equipment"], "equipment")
    state["district_equipment"] = dict(zip(sorted(rules["board"]["districts"]), equipment))
    # Start-of-game public reveals (variant B). Drawn from the equipment stream
    # AFTER the district shuffle: no other code consumes that stream, so gates,
    # turn order, the district mapping, and every die stay identical across
    # arms on matched seeds.
    reveal_count = rules.get("start_reveals", 0)
    if reveal_count:
        for name in _shuffle(state, sorted(rules["board"]["districts"]), "equipment")[:reveal_count]:
            state["revealed"][name] = state["district_equipment"][name]
        state["setup_reveals"] = sorted(state["revealed"])
    else:
        state["setup_reveals"] = []
    _start_turn(state)
    return state


def _start_turn(state):
    state["active_player"] = current_order(state)[state["turn_index"]]
    movement = state["rules"]["movement"]
    state["current_dice"] = [_die(state, "movement") for _ in range(movement.get("dice_count", 1))]
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
    cap = rules["glory"]["cap"]
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
            if (state["phase"] == 2
                    or (config["support_in_city"] and not config.get("blind_support")
                        and "board_level2" not in rules)):
                if state["phase"] == 2 and config.get("blind_support") and state["faction_sites"]:
                    # Blind support sites: search unrevealed cells (the offer
                    # never depends on the hidden faction - DECISIONS.md D1),
                    # buy support only at revealed sites that hold a faction.
                    key = f"{dest[0]},{dest[1]}"
                    if key in state["faction_sites"] and key not in state["faction_sites_revealed"]:
                        add("search_site", dest)
                    revealed = state["faction_sites_revealed"]
                    if revealed.get(key) and revealed[key] not in me["support"] and me["prestige"] >= config["support_cost"]:
                        add("gain_support", dest, faction=revealed[key])
                else:
                    for faction, location in sorted(config["factions"].items()):
                        if tuple(location) == dest and faction not in me["support"] and me["prestige"] >= config["support_cost"]:
                            add("gain_support", dest, faction=faction)
            if dest == b.checkpoint:
                if (state["phase"] == 1 and state["first_challenger"] is None
                        and len(me["equipment"]) >= rules["level1"].get("claim_required_equipment", 6)):
                    add("claim_checkpoint", dest)
                if (state["phase"] == 2 and state["pending_claim"] is None
                        and len(me["support"]) >= config["required_support"]
                        and me["prestige"] >= config.get("proclaim_cost", 0)):
                    add("proclaim", dest)
        if moved:
            if dest in b.glory_posts and (cap is None or me["prestige"] < cap):
                add("guard_post", dest)
            for other, target in sorted(state["players"].items()):
                if other == pid or _distances(b, dest)[tuple(target["pos"])] > rules["movement"]["duel_range"]:
                    continue
                pending = state["pending_claim"]
                # Human redesign: challenging the claimant requires standing
                # within the painted radius of the Peristyle.
                if (pending and pending["player"] == other and config.get("challenge_radius", 0)
                        and _distances(b, dest)[tuple(target["pos"])] > config["challenge_radius"]):
                    continue
                contest_cost = config.get("contest_cost", 0) if pending and pending["player"] == other else 0
                if me["prestige"] < contest_cost:
                    continue
                add("duel", dest, target=other, spend_prestige=False, contest_cost=contest_cost)
                if config["challenge_bonus"] and me["prestige"] >= config["challenge_cost"] + contest_cost:
                    add("duel", dest, target=other, spend_prestige=True, contest_cost=contest_cost)
    # Galea: a stationary, once-per-game public reveal of any unexplored
    # district. The offer never depends on the hidden item (DECISIONS.md D1).
    if rules["movement"]["allow_stationary_special_actions"]:
        if _usable_ability(me, rules, "reveal_district")[0]:
            for name in sorted(rules["board"]["districts"]):
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
    from engine import equipment_bonus
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
                        "equipment_bonus": equipment_bonus(len(pdata["equipment"]), rules),
                        "attack_bonus": _ability_total(pdata, rules, "attack_bonus"),
                        "defense_bonus": _ability_total(pdata, rules, "defense_bonus"),
                        "attack_vs_claimant_bonus": _ability_total(pdata, rules, "attack_vs_claimant"),
                        "prestige": pdata["prestige"], "support": sorted(pdata["support"]),
                        "turns": pdata["turns"]}
    progress = {"first_challenger": state["first_challenger"],
                "players_with_full_equipment": [p for p in IDS
                                                if len(state["players"][p]["equipment"]) >= rules["level1"].get("claim_required_equipment", 6)],
                "claim_required_equipment": rules["level1"].get("claim_required_equipment", 6),
                "set_completion_reward": rules["glory"].get("set_completion_reward", 0),
                "level1_max_rounds": rules["level1"]["max_rounds"],
                "level2_max_rounds": rules["level2"]["max_rounds"],
                "grace_full_rounds": rules["level1"]["grace_full_rounds"],
                **{key: config[key] for key in ("support_cost", "required_support", "support_in_city",
                                                "challenge_cost", "challenge_bonus")}}
    progress["contest_cost"] = config.get("contest_cost", 0)
    progress["claim_window_rounds"] = config.get("claim_window_rounds", 0)
    progress["challenge_radius"] = config.get("challenge_radius", 0)
    progress["proclaim_cost"] = config.get("proclaim_cost", 0)
    progress["duel_loser_cost"] = config.get("duel_loser_cost", 0)
    if config.get("blind_support"):
        # Blind support replaces city-phase support: the meeting places exist
        # only as hidden palace-level sites.
        progress["support_in_city"] = False
    if "board_level2" in rules and state["phase"] == 1:
        # Twin-board game: no meeting places exist on the palace map.
        progress["support_in_city"] = False
    if state["first_challenger"] is not None:
        progress["transition_after_round"] = min(state["trigger_round"] + rules["level1"]["grace_full_rounds"], rules["level1"]["max_rounds"])
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
                      "glory_posts": [list(c) for c in b.glory_posts],
                      "checkpoint": list(b.checkpoint),
                      **({"factions": ({} if ("board_level2" in rules and state["phase"] == 1)
                                      else copy.deepcopy(config["factions"]))}
                         if not (state["phase"] == 2 and config.get("blind_support") and state["faction_sites"])
                         else {"support_sites": {"candidates": [[int(x) for x in k.split(",")] for k in sorted(state["faction_sites"])],
                                                  "revealed": {k: v for k, v in sorted(state["faction_sites_revealed"].items())}}})},
            "revealed_districts": dict(sorted(state["revealed"].items())),
            "prestige_cap": rules["glory"]["cap"], "equipment_names": sorted(rules["equipment"]),
            "players": players, "pending_claim": copy.deepcopy(state["pending_claim"]),
            "progress": progress, "legal_actions": legal_actions(state)}


def _award(state, pid, amount, cause, events):
    player = state["players"][pid]
    cap = state["rules"]["glory"]["cap"]
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
    from engine import equipment_bonus
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
            if (len(me["equipment"]) == 6 and not me["set_rewarded"]
                    and rules["glory"].get("set_completion_reward", 0) > 0):
                me["set_rewarded"] = True
                me["stats"]["set_completion_awards"] += 1
                _award(state, player, rules["glory"]["set_completion_reward"], "set_completion", events)
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
        success = roll >= rules["glory"]["guard_post_success_min_roll"]
        events.append({"type": "guard_post", "player": player, "roll": roll, "success": success})
        if success:
            me["stats"]["guard_post_successes"] += 1
            _award(state, player, rules["glory"]["guard_post_reward"], "guard_post", events)
    elif kind == "search_site":
        key = f"{me['pos'][0]},{me['pos'][1]}"
        faction = state["faction_sites"][key]
        state["faction_sites_revealed"][key] = faction
        me["stats"]["site_searches"] += 1
        events.append({"type": "support_site_revealed", "player": player,
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
        _award(state, player, rules["glory"]["first_challenger_reward"], "checkpoint", events)
        events.append({"type": "first_challenger", "player": player})
    elif kind == "proclaim":
        state["pending_claim"] = {"player": player, "claim_id": turn_id, "responded": [],
                                  "round": state["round"]}
        if config.get("proclaim_cost", 0):
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
        paid = action["spend_prestige"]
        if action["contest_cost"]:
            _spend(state, player, action["contest_cost"], "claim_contest", events)
            me["stats"]["contest_prestige_spent"] += action["contest_cost"]
        if paid:
            _spend(state, player, config["challenge_cost"], "challenge", events)
            me["stats"]["challenge_boosts"] += 1
        attack_roll, defense_roll = die(), die()
        abilities = rules["combat"].get("abilities", {})
        # Count tiers apply when no ability table is present (baseline V0.8.1).
        # With abilities, every tier bonus is zero by validation, and at most
        # one ability modifier applies per side: the best one, never the sum
        # (DECISIONS.md D42). The paid challenge boost is separate because it
        # is not equipment.
        tier_attack = equipment_bonus(len(me["equipment"]), rules)
        tier_defense = equipment_bonus(len(them["equipment"]), rules)
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
        stacking = sum if rules["combat"].get("ability_stacking", "best") == "sum" else max
        attack_bonus = tier_attack + (stacking(attack_mods) if attack_mods else 0) + (config["challenge_bonus"] if paid else 0)
        defense_bonus = tier_defense + (stacking(defense_mods) if defense_mods else 0)
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
            won = not rules["combat"]["tie_goes_to_defender"]
        winner = player if won else target
        state["players"][winner]["stats"]["duels_won_attacker" if won else "duels_won_defender"] += 1
        events.append({"type": "duel", "attacker": player, "defender": target,
                       "winner": winner, "attacker_roll": attack_roll, "defender_roll": defense_roll,
                       "attacker_bonus": attack_bonus, "defender_bonus": defense_bonus,
                       "attacker_score": attack_score, "defender_score": defense_score,
                       "spend_prestige": paid})
        _award(state, winner, rules["glory"]["duel_win_reward"], "duel", events)
        # Human redesign option: the beaten duelist is shamed and pays the
        # bank up to one Prestige of what they hold.
        shame = config.get("duel_loser_cost", 0)
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
        if len(set(pending["responded"])) == 3 and not config.get("claim_window_rounds", 0):
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
              "prestige_after": me["prestige"], "glory_after": me["prestige"],
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
        window = rules["succession"].get("claim_window_rounds", 0)
        pending = state["pending_claim"]
        if (window and state["phase"] == 2 and pending
                and state["round"] - pending["round"] >= window):
            # Human redesign: a claim that survived the window unchallenged
            # wins the game outright (end_reason survived_window). The event
            # rides the last turn record, like phase_transition and game_draw.
            claimant = pending["player"]
            state["winner"], state["status"], state["end_reason"] = claimant, "finished", "survived_window"
            state["players"][claimant]["stats"]["claims_survived"] += 1
            state["events"][-1]["events"].append({"type": "game_won", "player": claimant,
                                                  "cause": "survived_window"})
            state["current_roll"] = None
            return
        if state["phase"] == 1:
            end = rules["level1"]["max_rounds"]
            if state["first_challenger"] is not None:
                end = min(end, state["trigger_round"] + rules["level1"]["grace_full_rounds"])
            if state["round"] > end:
                state["rounds_level1"] = state["round"] - 1
                state["phase1_timeout"] = state["first_challenger"] is None
                state["equipment_at_transition"] = {p: len(d["equipment"]) for p, d in state["players"].items()}
                if "board_level2" in rules:
                    # Twin-board game: the succession map takes over and every
                    # seat returns to its gate on that map (the playtest's
                    # table rule, now structural). Phase is set first so the
                    # gate lookup sees the new map.
                    state["phase"] = 2
                    for player in state["players"].values():
                        player["pos"] = _gate_cell(state, player)
                elif rules["succession"]["reset_positions"]:
                    for player in state["players"].values():
                        player["pos"] = player["gate"][:]
                state["phase"], state["round"], state["round_start"] = 2, 1, 0
                if rules["succession"].get("blind_support"):
                    # Human redesign: on the palace level the three faction
                    # meeting places are re-dealt blind onto the six district
                    # entry cells - three hold a faction, three are decoys.
                    # Drawn from the order stream, which nothing uses after
                    # setup, so matched seeds stay aligned across arms.
                    cells = sorted(list(c) for c in rules["board"]["districts"].values())
                    state["faction_sites"] = {f"{c[0]},{c[1]}": None for c in cells}
                    for cell, name in zip(_shuffle(state, cells, "order")[:3],
                                          sorted(rules["succession"]["factions"])):
                        state["faction_sites"][f"{cell[0]},{cell[1]}"] = name
                    state["faction_sites_revealed"] = {}
                state["events"][-1]["events"].append({"type": "phase_transition", "from_phase": 1,
                    "to_phase": 2, "auto_granted": {}, "phase1_timeout": state["phase1_timeout"]})
        elif state["round"] > rules["level2"]["max_rounds"]:
            state["status"], state["winner"], state["end_reason"] = "finished", None, "phase2_timeout"
            state["phase2_timeout"] = True
            state["round"] = rules["level2"]["max_rounds"]
            state["current_roll"] = None
            state["events"][-1]["events"].append({"type": "game_draw", "reason": "phase2_timeout"})
            return
    _start_turn(state)


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
            "districts_explored": len(districts),
            # Explicit compatibility columns for the original CSV writer.
            "glory_final": player["prestige"], "glory_earned": stats["prestige_earned"],
            "glory_spent": stats["prestige_spent"], "glory_wasted_at_cap": stats["prestige_wasted_at_cap"],
            "auto_granted": 0, "glory_stolen": 0, "glory_lost_theft": 0,
            "turns_skipped": 0, "chamber_evictions": 0, "seals": [], "seal_attempts": 0,
            "seal_attempts_by_site": {"cellars": 0, "guard_barracks": 0, "peristyle": 0},
            "emperor_attempts": 0, "emperor_hits": 0,
            "glory_spent_peristyle": 0, "glory_spent_emperor": 0}
    turns1 = sum(r["phase"] == 1 for r in state["events"])
    first = state["first_challenger"]
    return {"gameplay_mode": MODE, "game_id": state["game_id"], "seed": state["seed"],
        "rules_hash": state["rules_hash"], "engine_version": VERSION, "policy_version": POLICY_VERSION,
        "outcome": "win" if state["winner"] else "draw", "winner": state["winner"],
        "end_reason": state["end_reason"], "first_challenger": first,
        "setup_reveals": list(state.get("setup_reveals", [])),
        "first_challenger_won": first == state["winner"] if first else None,
        "comeback_win": first != state["winner"] if first and state["winner"] else None,
        "phase1_timeout": state["phase1_timeout"], "phase2_timeout": state["phase2_timeout"],
        "rounds_level1": state["rounds_level1"], "rounds_level2": state["round"] if state["phase"] == 2 else 0,
        "turns_level1": turns1, "turns_level2": len(state["events"]) - turns1,
        "total_turns": len(state["events"]),
        "total_rounds": (state["rounds_level1"] or 0) + (state["round"] if state["phase"] == 2 else 0),
        "policies": dict(state["policies"]), "turn_order": current_order(state),
        "gate_assignments": dict(state["gate_assignments"]), "players": metrics,
        "high_impact_events": [{"turn_id": r["turn_id"], "round": r["round"], "phase": r["phase"], **ev}
            for r in state["events"] for ev in r["events"]
            if ev["type"] in {"duel", "support_gained", "claim_proclaimed", "claim_cancelled", "claim_response", "game_won", "phase_transition", "game_draw", "ability_used"}]}


def check_invariants(state):
    b = _board(state["rules"], state["phase"])
    cap = state["rules"]["glory"]["cap"]
    for pid, player in state["players"].items():
        assert tuple(player["pos"]) in _distances(b, _gate_cell(state, player)), f"{pid} outside street graph"
        assert player["prestige"] >= 0 and (cap is None or player["prestige"] <= cap), "invalid Prestige"
        assert len(set(player["equipment"])) == len(player["equipment"]), "duplicate equipment"
        assert set(player["equipment"]) <= set(state["rules"]["equipment"]), "unknown equipment"
        assert len(set(player["support"])) == len(player["support"]), "duplicate support"
        assert set(player["support"]) <= set(state["rules"]["succession"]["factions"]), "unknown support"
        assert set(player["abilities_used"]) <= set(ABILITY_TYPES), "unknown ability type used"
        assert set(player["abilities_used"].values()) <= set(state["rules"]["equipment"]), "unknown ability item"
    assert sorted(state["gate_assignments"].values()) == list(IDS), "gate assignment not a permutation"
    pending = state["pending_claim"]
    if pending:
        assert tuple(state["players"][pending["player"]]["pos"]) == b.checkpoint, "claimant left Peristyle"
        assert pending["player"] not in pending["responded"], "claimant counted as responder"
        assert len(pending["responded"]) == len(set(pending["responded"])), "duplicate response"
    if state["winner"]:
        if state["end_reason"] == "survived_window":
            assert pending, "window win without a pending claim"
            window = state["rules"]["succession"].get("claim_window_rounds", 0)
            assert window and state["round"] - pending["round"] >= window, "claim window not actually survived"
        else:
            assert state["end_reason"] == "acclamation" and pending and len(pending["responded"]) == 3, "incomplete acclamation"
    if state["faction_sites"]:
        names = set(state["rules"]["succession"]["factions"])
        held = sorted(f for f in state["faction_sites"].values() if f)
        assert held == sorted(names), "blind support sites must hold each faction exactly once"
        assert set(state["faction_sites_revealed"]) <= set(state["faction_sites"]), "revealed site is not a candidate"
        for key, faction in state["faction_sites_revealed"].items():
            assert state["faction_sites"][key] == faction, "revealed site mismatches the hidden deal"
    for record in state["events"]:
        assert len(record["action"]["path"]) - 1 <= record["movement_die"], "movement exceeds roll"
    return True


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
        edge = (me["equipment_bonus"] + me.get("attack_bonus", 0)
                - other["equipment_bonus"] - other.get("defense_bonus", 0))
        if pending and pending["player"] == action["target"]:
            edge += me.get("attack_vs_claimant_bonus", 0)
        bonus = edge + (progress["challenge_bonus"] if action["spend_prestige"] else 0)
        wins = sum(1 for a in range(1, 7) for d in range(1, 7) if a + bonus >= d)
        # Paid duels are useful against a claimant but not for farming.
        return (-wins, bool(action["spend_prestige"]), len(action["path"]), action["action_id"])

    if pending and pending["player"] == obs["viewer"] and bykind("maintain_claim"):
        return select(bykind("maintain_claim")[0], "maintain the pending claim")
    if pending and pending["player"] != obs["viewer"]:
        challenges = [a for a in bykind("duel") if a["target"] == pending["player"]]
        if challenges:
            return select(min(challenges, key=duel_key), "challenge the claimant")
        if prestige < progress.get("contest_cost", 0):
            if bykind("guard_post"):
                return select(nearest(bykind("guard_post")), "earn Prestige for a future contest")
            available_duels = [a for a in bykind("duel") if not a["spend_prestige"]]
            if available_duels:
                return select(min(available_duels, key=duel_key), "earn Prestige for a future contest")
            public_dist = _public_distances(obs, me["position"])
            posts = obs["board"]["glory_posts"]
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
    faction_accessible = obs["phase"] == 2 or progress["support_in_city"]
    # Gear targets read the rule parameters (D41/D43): collectors rush to the
    # checkpoint requirement; other profiles complete the set only when the
    # completion reward exists, and otherwise stop at three items as before.
    claim_requirement = progress.get("claim_required_equipment", 6)
    set_target = 6 if progress.get("set_completion_reward", 0) else 3
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
    if "support_sites" in obs["board"]:
        # Blind palace-level sites: target revealed faction sites, else hunt
        # the nearest unrevealed candidate cell.
        sites = obs["board"]["support_sites"]
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
    guard_target = (min(obs["board"]["glory_posts"], key=lambda c: (public_dist[tuple(c)], c))
                    if obs["board"]["glory_posts"] else None)
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
            return select(nearest(bykind("search_site")), "search a support site")
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
