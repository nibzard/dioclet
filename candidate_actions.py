# ABOUTME: Observation-only projection and candidate shortlists for the
# ABOUTME: succession game; reads public observations and rules only.
"""Observation-only projection and candidate shortlists.

Everything here is a pure function of one public observation plus the
public rules file. Nothing reads engine internals, `state.json`, or
future randomness. The shortlist never invents or renames actions: it
only filters, groups, and annotates the engine's `legal_actions`.
"""

import itertools
import json

import engine
from board import Board

SUCCESSION_SCHEMA_VERSION = "v0102-succession-proj-4"


def _enumerate_with_sides(sides):
    wins = ties = 0
    total = sides * sides
    for a in range(1, sides + 1):
        for b in range(1, sides + 1):
            if a > b:
                wins += 1
            elif a == b:
                ties += 1
    return wins, ties, total


def contest_probability(my_bonus, their_bonus, tie_wins, sides=6):
    """Exact P(my die + my_bonus >= their die + their_bonus)."""
    offset = my_bonus - their_bonus
    favorable = 0
    total = sides * sides
    for a in range(1, sides + 1):
        for b in range(1, sides + 1):
            diff = a + offset - b
            if diff > 0 or (diff == 0 and tie_wins):
                favorable += 1
    return favorable / total


def threshold_probability(min_roll, sides=6):
    """Exact P(die >= min_roll)."""
    return max(0, sides - min_roll + 1) / sides


def duel_win_probability(attacker_bonus, defender_bonus, tie_attacker_wins,
                         sides=6):
    return contest_probability(attacker_bonus, defender_bonus,
                               tie_attacker_wins, sides)


def duel_odds(attacker, defender, rules, pending_claim):
    """Exact attacker win chance for one duel, plus the parts that drove it.

    Mirrors the engine's duel resolution: at most one attack modifier
    applies (the best; the pilum counts only against the pending
    claimant), at most one defense modifier applies, never a sum, and
    the pugio wins ties only for a lone holder. The attacker and
    defender are public player dicts carrying "id" and "equipment".
    """
    abilities = rules["treasures"]["abilities"]

    def _ability_total(equipment, ability_type):
        total = 0
        for item in equipment:
            spec = abilities.get(item)
            if spec and spec["type"] == ability_type and spec["value"] > 0:
                total += spec["value"]
        return total

    attack_mods = []
    for item in attacker["equipment"]:
        spec = abilities.get(item)
        if not spec or spec["value"] <= 0:
            continue
        if spec["type"] == "attack_bonus":
            attack_mods.append(spec["value"])
        elif (spec["type"] == "attack_vs_claimant" and pending_claim
                and pending_claim["player"] == defender["id"]):
            attack_mods.append(spec["value"])
    defense_mods = []
    for item in defender["equipment"]:
        spec = abilities.get(item)
        if spec and spec["type"] == "defense_bonus" and spec["value"] > 0:
            defense_mods.append(spec["value"])
    parts = {
        "attack_bonus": max(attack_mods) if attack_mods else 0,
        "defense_bonus": max(defense_mods) if defense_mods else 0,
        "attacker_pugio": _ability_total(attacker["equipment"], "win_ties") > 0,
        "defender_pugio": _ability_total(defender["equipment"], "win_ties") > 0,
        "tie_rule": rules["duels"]["tie_winner"],
    }
    sides = rules["movement"]["die_sides"]
    wins = 0
    for attack_roll in range(1, sides + 1):
        for defense_roll in range(1, sides + 1):
            if parts["attack_bonus"] + attack_roll \
                    != parts["defense_bonus"] + defense_roll:
                won = (parts["attack_bonus"] + attack_roll
                       > parts["defense_bonus"] + defense_roll)
            elif parts["attacker_pugio"] != parts["defender_pugio"]:
                won = parts["attacker_pugio"]
            else:
                won = parts["tie_rule"] == "attacker"
            wins += won
    return {"probability": wins / (sides * sides), "parts": parts}


# ---------------------------------------------------------------------------
# Public-rule helpers
# ---------------------------------------------------------------------------

def claim_rule_text(rules):
    """Public claim-win wording, generated from the active rules.

    With a claim window the claim must survive that many full rounds
    uncancelled; with a zero window each distinct rival completes one
    response turn and the claim wins when the last response ends.
    """
    window = rules["succession"]["claim_window_rounds"]
    if window:
        return (f"A proclaimed claim wins after it survives {window} full "
                "round(s) uncancelled; rivals must cancel it inside the "
                "window.")
    return ("Each distinct rival completes one response turn; the claim "
            "wins when the last response ends without cancelling it.")


def rule_summary(rules):
    """Public mechanics summary sent to the model (no secrets exist)."""
    cfg = rules["succession"]
    summary = {
        "prestige_cap": rules["prestige"]["cap"],
        "support_cost": cfg["support_cost"],
        "required_support": cfg["factions_to_proclaim"],
        "contest_cost": cfg["contest_fee"],
        "support_is_permanent": True,
        "equipment_is_persistent": True,
        "free_equipment_at_transition": False,
        "successful_challenge": "Cancel the claim; claimant returns to their own assigned gate.",
        "duel_tie_goes_to": rules["duels"]["tie_winner"],
        "guard_success_min_roll": rules["prestige"]["guard_post_min_roll"],
        "duel_range": rules["duels"]["range"],
        "grace_full_rounds": rules["palace"]["rounds_after_checkpoint"],
    }
    summary["claim_response_rule"] = claim_rule_text(rules)
    if rules["prestige"]["duel_loss_penalty"]:
        summary["duel_loser_cost"] = rules["prestige"]["duel_loss_penalty"]
    if cfg["proclaim_cost"]:
        summary["proclaim_cost"] = cfg["proclaim_cost"]
    count = len(cfg["map"]["card_spaces"])
    summary["card_spaces"] = (
        f"Succession map: the three faction meeting places are hidden among "
        f"{count} candidate cells; end movement on one and search to reveal it.")
    summary["equipment_abilities"] = {
        item: spec["type"] for item, spec in sorted(rules["treasures"]["abilities"].items())}
    return summary


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def project_observation(obs, rules):
    """Compact, stable, fully public projection for the model."""
    me = obs["players"][obs["viewer"]]
    claim = _claim_block(obs, rules)
    public_players = []
    for pid, p in sorted(obs["players"].items()):
        public_players.append({
            "id": pid, "position": p["position"],
            "gate": p["gate"], "gate_id": p["gate_id"],
            "equipment": list(p["equipment"]),
            "equipment_count": p["equipment_count"],
            "prestige": p["prestige"], "support": list(p["support"]),
        })
    return {
        "schema": SUCCESSION_SCHEMA_VERSION,
        "gameplay_mode": "succession-v1", "game_id": obs["game_id"],
        "objective": (
            "Win the succession: gain support from two different factions, "
            "reach the Peristyle in the succession phase, and proclaim a "
            "claim. " + claim_rule_text(rules) + " "
            "Collect equipment for lasting duel strength. Earn and spend "
            "Prestige on support or contesting a claim. A rival's "
            "successful challenge cancels your claim. Choose to maximize "
            "your eventual chance of winning, not merely immediate "
            "resources."),
        "turn": {"id": obs["turn_id"], "round": obs["round"],
                 "phase": obs["phase"], "player": obs["viewer"],
                 "movement_die": obs["movement_die"],
                 "turn_order_this_round": obs["turn_order"]},
        "self": next(p for p in public_players if p["id"] == obs["viewer"]),
        "opponents": [p for p in public_players if p["id"] != obs["viewer"]],
        "goals": _projection_goals(obs, rules),
        "pending_claim": obs.get("pending_claim"),
        **({"claim": claim} if claim else {}),
        "public_locations": {key: obs["board"][key] for key in (
            "width", "height", "blocked", "gates", "districts", "guard_posts",
            "checkpoint") if key in obs["board"]},
        # Blind card spaces replace the printed faction cells; only
        # candidates and already-revealed spaces are public (D17/D25).
        **({"card_spaces": obs["board"]["card_spaces"]}
           if "card_spaces" in obs["board"] else
           {"factions": obs["board"]["factions"]}),
        "gate_assignments": obs["gate_assignments"],
        "revealed_districts": dict(obs["revealed_districts"]),
        "equipment_names": list(obs["equipment_names"]),
        "missing_equipment": sorted(set(obs["equipment_names"]) - set(me["equipment"])),
        "progress": dict(obs["progress"]),
        "rule_summary": rule_summary(rules),
        "limits": (
            "Outcome probabilities from dice and from the public remaining "
            "composition of the board are exact. Action choice "
            "probabilities are model preferences, not win rates or human fun scores. "
            "Unrevealed treasure locations and future dice are not supplied."),
    }


def projection_hash(projection):
    blob = json.dumps(projection, sort_keys=True, separators=(",", ":"))
    import hashlib
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Candidate shortlist
# ---------------------------------------------------------------------------

def _succession_distances(obs, rules, start):
    # The public rules contain only geometry. No state or secret is read.
    # The succession phase is played on the succession map.
    section = "succession" if obs.get("phase") == 2 else "palace"
    return Board(rules, section).distances(tuple(start))


def _succession_goals(obs, rules):
    me = obs["players"][obs["viewer"]]
    board = obs["board"]
    goals = {"claim": [board["checkpoint"]], "collection": [],
             "support": [], "prestige": board["guard_posts"]}
    for name, cell in board["districts"].items():
        revealed = obs["revealed_districts"].get(name)
        if revealed is None or revealed not in me["equipment"]:
            goals["collection"].append(cell)
    if "card_spaces" in board:  # blind faction cards
        revealed = board["card_spaces"]["revealed"]
        for cell in board["card_spaces"]["candidates"]:
            key = f"{cell[0]},{cell[1]}"
            # Skip searched blanks and factions this player already has.
            if key not in revealed or (revealed[key] and revealed[key] not in me["support"]):
                goals["support"].append(cell)
    else:
        for name, cell in board["factions"].items():
            if name not in me["support"]:
                goals["support"].append(cell)
    pending = obs.get("pending_claim")
    if pending and pending["player"] != obs["viewer"]:
        goals["counterclaim"] = [obs["players"][pending["player"]]["position"]]
    return goals


def _public_player(obs, pid):
    """The id and equipment a duel needs, from one public observation."""
    return {"id": pid, "equipment": obs["players"][pid]["equipment"]}


def _claim_block(obs, rules):
    """The pending claim's deadline, remaining schedule, and cancel chances.

    The deadline calls the engine's own window rule
    (engine.claim_window_deadline), so projection and engine share one
    source. Every input is public: the claim, the turn order, and the
    rules file. Without a claim window the acclamation response rule
    decides the win, so the schedule fields stay empty. A deadline past
    the last succession round never arrives; the schedule then runs to
    the game's end and the win turn stays unset.
    """
    pending = obs.get("pending_claim")
    if not pending:
        return None
    claimant = pending["player"]
    can_cancel = any(a["kind"] == "duel" and a.get("target") == claimant
                     for a in obs["legal_actions"])
    order = list(obs["turn_order"])
    seated = order.index(obs["active_player"])
    deadline_round = engine.claim_window_deadline(
        pending["round"], rules["succession"]["claim_window_rounds"])
    if deadline_round is None:
        return {"claimant": claimant, "wins_after_turn": None,
                "remaining_turns": [], "cancel_chances": {},
                "can_cancel_this_turn": can_cancel}
    max_round = rules["succession"]["max_rounds"]
    wins_after_turn = None
    if deadline_round <= max_round:
        wins_after_turn = (obs["turn_id"] + len(order) - 1 - seated
                           + len(order) * (deadline_round - obs["round"]))
    last_round = min(deadline_round, max_round)
    turn, idx = obs["turn_id"], seated
    rotate = rules["turns"]["rotate_first_player_each_round"]
    span = len(order) - idx + len(order) * (last_round - obs["round"])
    if wins_after_turn is not None:
        span = min(span, wins_after_turn - turn + 1)
    turns, chances = [], {}
    round_no = obs["round"]
    for _ in range(span):
        player = order[idx]
        turns.append({"round": round_no, "turn": turn, "player": player})
        if player != claimant:
            chances[player] = chances.get(player, 0) + 1
        turn += 1
        idx += 1
        if idx == len(order):
            idx = 0
            round_no += 1
            if rotate:
                order = order[1:] + order[:1]
    return {"claimant": claimant, "wins_after_turn": wins_after_turn,
            "remaining_turns": turns, "cancel_chances": chances,
            "can_cancel_this_turn": can_cancel}


# ---------------------------------------------------------------------------
# Predicted outcomes
# ---------------------------------------------------------------------------

def _prestige_after_award(prestige, amount, rules):
    """Prestige after one award; the cap clamps the gain like the engine."""
    cap = rules["prestige"]["cap"]
    got = amount if cap is None else min(amount, max(0, cap - prestige))
    return prestige + got


def _leaves_claim(obs, action):
    """True when the acting claimant ends this action off the Peristyle."""
    pending = obs.get("pending_claim")
    return bool(pending and pending["player"] == obs["viewer"]
                and tuple(action["destination"])
                != tuple(obs["board"]["checkpoint"]))


def _displacement_preventers(rules):
    """Items whose ability keeps a beaten claimant on the square."""
    abilities = rules["treasures"]["abilities"]
    return {item for item, spec in abilities.items()
            if spec["type"] == "prevent_displacement"}


def _hidden_items(obs):
    """Items still face down, derived from public reveals and equipment."""
    revealed = set(obs["revealed_districts"].values())
    owned = {item for player in obs["players"].values()
             for item in player["equipment"]}
    return [name for name in obs["equipment_names"]
            if name not in revealed and name not in owned]


def _hidden_cards(obs, rules):
    """Faction names and blanks still hidden in the card spaces.

    Returns None when the public counts cannot describe the deal.
    """
    spaces = obs["board"].get("card_spaces")
    if spaces is None:
        return None
    revealed = spaces["revealed"]
    total = len(spaces["candidates"]) - len(revealed)
    found = {name for name in revealed.values() if name}
    deck = rules["succession"]["faction_cards"]["factions"]
    factions = sorted(set(deck) - found)
    blanks = total - len(factions)
    if total <= 0 or blanks < 0:
        return None
    return factions, blanks, total


# ---------------------------------------------------------------------------
# Named goals
# ---------------------------------------------------------------------------

def move_reach_probability(distance, rules):
    """Exact share of movement dice sums that cover the street distance.

    The engine offers a move to a cell when the street distance is at
    most the roll, so this is also the chance the cell is reachable on
    the next turn.
    """
    movement = rules["movement"]
    dice, sides = movement["dice"], movement["die_sides"]
    if distance <= 0:
        return 1.0
    if distance > dice * sides:
        return 0.0
    rolls = itertools.product(range(1, sides + 1), repeat=dice)
    reached = sum(1 for roll in rolls if sum(roll) >= distance)
    return reached / sides ** dice


def _reach_next_turn(steps, rules):
    """Exact one-turn chance, or a turn estimate when one roll cannot span it."""
    movement = rules["movement"]
    dice, sides = movement["dice"], movement["die_sides"]
    reach = {"dice": dice, "die_sides": sides}
    if steps <= dice * sides:
        reach.update(kind="exact",
                     probability=round(move_reach_probability(steps, rules), 6))
    else:
        reach.update(kind="estimate", turns_at_best=-(-steps // (dice * sides)))
    return reach


def _goal(name, kind, target, dists, prerequisites, rules):
    steps = dists[tuple(target)]
    return {"name": name, "kind": kind, "target": list(target),
            "steps": steps, "reach_next_turn": _reach_next_turn(steps, rules),
            "prerequisites": prerequisites,
            "prerequisites_met": all(p["met"] for p in prerequisites)}


def _pay_prestige(cost, prestige):
    return {"need": "prestige", "cost": cost, "have": prestige,
            "met": prestige >= cost}


def _claim_goal(obs, me, dists, rules):
    if obs["phase"] == 2:
        name = "Peristyle"
        if obs.get("pending_claim") and \
                obs["pending_claim"]["player"] == obs["viewer"]:
            prereqs = [{"need": "hold_claim", "met": True}]
        else:
            required = rules["succession"]["factions_to_proclaim"]
            prereqs = [
                {"need": "factions", "required": required,
                 "have": len(me["support"]), "met": len(me["support"]) >= required},
                _pay_prestige(rules["succession"]["proclaim_cost"],
                              me["prestige"]),
            ]
    else:
        if obs["progress"]["first_challenger"] is not None:
            return None  # the checkpoint is already claimed
        name = "Checkpoint"
        required = rules["palace"]["checkpoint_items_required"]
        prereqs = [{"need": "items", "required": required,
                    "have": len(me["equipment"]),
                    "met": len(me["equipment"]) >= required}]
    return _goal(name, "claim", obs["board"]["checkpoint"], dists,
                 prereqs, rules)


def _support_goals(obs, me, dists, rules):
    goals = []
    board = obs["board"]
    spaces = board.get("card_spaces")
    cost = rules["succession"]["support_cost"]
    if spaces is None:
        for faction, cell in sorted(board.get("factions", {}).items()):
            if faction in me["support"]:
                continue
            prereqs = [_pay_prestige(cost, me["prestige"])]
            goals.append(_goal(f"{faction.capitalize()} support", "support",
                               cell, dists, prereqs, rules))
        return goals
    letters = {tuple(cell): chr(ord("A") + index)
               for index, cell in enumerate(spaces["candidates"])}
    hidden = _hidden_cards(obs, rules)
    for cell in spaces["candidates"]:
        key = f"{cell[0]},{cell[1]}"
        if key in spaces["revealed"]:
            faction = spaces["revealed"][key]
            if not faction or faction in me["support"]:
                continue  # a searched blank, or support already held
            prereqs = [
                {"need": "card", "state": "face up", "faction": faction,
                 "met": True},
                _pay_prestige(cost, me["prestige"]),
            ]
            goals.append(_goal(f"{faction.capitalize()} support", "support",
                               cell, dists, prereqs, rules))
        else:
            prereqs = [{"need": "card", "state": "face down", "met": False}]
            goal = _goal(f"card space {letters[tuple(cell)]}", "support",
                         cell, dists, prereqs, rules)
            if hidden is not None:
                factions, blanks, total = hidden
                # Public composition only: how many of the face-down
                # cards must be factions by the setup rules.
                goal["hidden_cards"] = {"total": total,
                                        "factions": len(factions),
                                        "blanks": blanks}
            goals.append(goal)
    return goals


def _treasure_goals(obs, me, dists, rules):
    goals = []
    for name, cell in sorted(obs["board"]["districts"].items()):
        revealed = obs["revealed_districts"].get(name)
        if revealed is not None and revealed in me["equipment"]:
            continue  # the item is already collected
        goal = _goal(f"district {name}", "treasure", cell, dists, [], rules)
        if revealed is not None:
            goal["item"] = revealed
        goals.append(goal)
    return goals


def _guard_goal(obs, me, dists, rules):
    cap = obs["prestige_cap"]
    posts = sorted((cell for cell in obs["board"]["guard_posts"]
                    if dists[tuple(cell)] > 0),
                   key=lambda cell: (dists[tuple(cell)], tuple(cell)))
    if not posts:
        return None
    prereqs = [{"need": "prestige_below_cap", "cap": cap,
                "have": me["prestige"],
                "met": cap is None or me["prestige"] < cap}]
    return _goal("Guard post", "prestige", posts[0], dists, prereqs, rules)


def _projection_goals(obs, rules):
    """Named destinations for the viewing seat, with public prerequisites.

    Distances reuse the engine's street graph (Board.distances), the one
    legal moves come from; the reach chance is the exact share of
    movement dice that cover the distance in one turn.
    """
    me = obs["players"][obs["viewer"]]
    dists = _succession_distances(obs, rules, me["position"])
    goals = []
    claim = _claim_goal(obs, me, dists, rules)
    if claim is not None:
        goals.append(claim)
    if obs["phase"] == 2:
        goals.extend(_support_goals(obs, me, dists, rules))
    else:
        goals.extend(_treasure_goals(obs, me, dists, rules))
    guard = _guard_goal(obs, me, dists, rules)
    if guard is not None:
        goals.append(guard)
    return goals


def _duel_outcomes(action, obs, rules):
    """Win and lose branches with the engine's exact prestige arithmetic."""
    pending = obs.get("pending_claim")
    prestige_cfg = rules["prestige"]
    cost = action.get("contest_cost", 0)
    at_risk = obs["players"][obs["viewer"]]["prestige"] - cost
    vs_claimant = bool(pending and pending["player"] == action["target"])
    shame = prestige_cfg["duel_loss_penalty"]
    win = {
        "prestige_after": _prestige_after_award(
            at_risk, prestige_cfg["duel_win_reward"], rules),
        "claim_cancelled": vs_claimant or _leaves_claim(obs, action),
    }
    lose = {
        "prestige_after": at_risk - (min(shame, at_risk) if shame else 0),
        "claim_cancelled": _leaves_claim(obs, action),
    }
    if vs_claimant and not (_displacement_preventers(rules)
                            & set(obs["players"][action["target"]]["equipment"])):
        # Without such an item the beaten claimant always returns to the
        # gate. Holding one makes the once-per-game use private, so the
        # outcome stays silent instead of guessing.
        win["claimant_to_gate"] = True
    odds = duel_odds(_public_player(obs, obs["viewer"]),
                     _public_player(obs, action["target"]), rules, pending)
    return [
        {"condition": "win", "probability": round(odds["probability"], 6),
         "effects": win},
        {"condition": "lose",
         "probability": round(1 - odds["probability"], 6), "effects": lose},
    ]


def _guard_post_outcomes(action, obs, rules):
    """One die against the guard threshold: prestige on a pass only."""
    prestige_cfg = rules["prestige"]
    prestige = obs["players"][obs["viewer"]]["prestige"]
    chance = threshold_probability(prestige_cfg["guard_post_min_roll"],
                                   rules["movement"]["die_sides"])
    cancelled = _leaves_claim(obs, action)
    return [
        {"condition": "win", "probability": round(chance, 6),
         "effects": {"prestige_after": _prestige_after_award(
             prestige, prestige_cfg["guard_post_reward"], rules),
             "claim_cancelled": cancelled}},
        {"condition": "lose", "probability": round(1 - chance, 6),
         "effects": {"prestige_after": prestige,
                     "claim_cancelled": cancelled}},
    ]


def _flat_outcome(action, obs, cost, effects=()):
    """The single certain outcome of a paid, dice-free action."""
    base = {"prestige_after": obs["players"][obs["viewer"]]["prestige"] - cost,
            "claim_cancelled": _leaves_claim(obs, action)}
    base.update(effects)
    return [{"condition": "always", "probability": 1.0, "effects": base}]


def _explore_outcomes(action, obs, rules, district):
    """One branch per hidden item; one certain branch when the item is public."""
    prestige = obs["players"][obs["viewer"]]["prestige"]
    known = obs["revealed_districts"].get(district)
    if known is not None:
        return _flat_outcome(action, obs, 0,
                             {"item_gained": known})
    hidden = _hidden_items(obs)
    count = len(obs["board"]["districts"]) - len(obs["revealed_districts"])
    if len(hidden) != count:
        return None
    chance = round(1 / count, 6)
    return [{"condition": f"reveal {name}", "probability": chance,
             "effects": {"prestige_after": prestige,
                         "claim_cancelled": _leaves_claim(obs, action),
                         "item_gained": name}}
            for name in hidden]


def _search_outcomes(action, obs, rules):
    """One branch per remaining faction card, plus one blank branch."""
    cards = _hidden_cards(obs, rules)
    if cards is None:
        return None
    factions, blanks, total = cards
    prestige = obs["players"][obs["viewer"]]["prestige"]
    cancelled = _leaves_claim(obs, action)
    outcomes = [{"condition": f"reveal {name}",
                 "probability": round(1 / total, 6),
                 "effects": {"prestige_after": prestige,
                             "claim_cancelled": cancelled,
                             "card_revealed": name}}
                for name in factions]
    if blanks:
        outcomes.append({"condition": "reveal blank",
                         "probability": round(blanks / total, 6),
                         "effects": {"prestige_after": prestige,
                                     "claim_cancelled": cancelled,
                                     "card_revealed": None}})
    return outcomes


def _action_outcomes(action, obs, rules):
    """Public outcomes for one candidate; None when not computable."""
    kind = action["kind"]
    if kind == "duel":
        return _duel_outcomes(action, obs, rules)
    if kind == "guard_post":
        return _guard_post_outcomes(action, obs, rules)
    if kind == "gain_support":
        return _flat_outcome(action, obs, rules["succession"]["support_cost"])
    if kind == "proclaim":
        return _flat_outcome(action, obs, rules["succession"]["proclaim_cost"])
    if kind == "explore":
        district = next((name for name, cell in obs["board"]["districts"].items()
                         if list(cell) == action["destination"]), None)
        if district is None:
            return None
        return _explore_outcomes(action, obs, rules, district)
    if kind == "search_site":
        return _search_outcomes(action, obs, rules)
    return None


def _succession_features(action, obs, rules):
    me = obs["players"][obs["viewer"]]
    dest = action["destination"]
    dists = _succession_distances(obs, rules, dest)
    pending = obs.get("pending_claim")
    feats = {
        "path_steps": len(action.get("path", [])) - 1,
        "distance_to_peristyle_after": dists[tuple(obs["board"]["checkpoint"])],
        "support_after": len(me["support"]) + (action["kind"] == "gain_support"),
        "counterclaim": bool(pending and action["kind"] == "duel" and action.get("target") == pending["player"]),
    }
    for category, targets in _succession_goals(obs, rules).items():
        if targets:
            feats["distance_to_" + category + "_after"] = min(dists[tuple(c)] for c in targets)
    if action["kind"] == "duel":
        target = obs["players"][action["target"]]
        odds = duel_odds(_public_player(obs, obs["viewer"]),
                         _public_player(obs, action["target"]), rules, pending)
        feats.update({
            "duel_win_probability_exact": round(odds["probability"], 6),
            "prestige_cost": action.get("contest_cost", 0),
            "target_support_count": len(target["support"]),
            "would_cancel_claim_if_won": feats["counterclaim"],
        })
    elif action["kind"] == "gain_support":
        feats["faction"] = action["faction"]
        feats["prestige_cost"] = rules["succession"]["support_cost"]
    elif action["kind"] == "guard_post":
        feats["prestige_probability_exact"] = threshold_probability(
            rules["prestige"]["guard_post_min_roll"], rules["movement"]["die_sides"])
    elif action["kind"] == "explore":
        district = next(name for name, cell in obs["board"]["districts"].items() if list(cell) == dest)
        feats["district"] = district
        feats["district_revealed"] = district in obs["revealed_districts"]
        # Do not use action.get('item') even if a malformed caller supplies it.
        if district in obs["revealed_districts"]:
            feats["public_item"] = obs["revealed_districts"][district]
    outcomes = _action_outcomes(action, obs, rules)
    if outcomes is not None:
        feats["outcomes"] = outcomes
    return feats


def _describe_succession(action, feats, rules):
    kind, dest = action["kind"], action["destination"]
    if kind == "explore":
        return f"Collect at district {feats['district']}; equipment stays with you in both phases."
    if kind == "search_site":
        return f"Search the face-down faction card at {dest}; the result is public."
    if kind == "gain_support":
        return f"Gain {action['faction']} support for {feats['prestige_cost']} Prestige, without a die test."
    if kind == "proclaim":
        return f"Proclaim your claim at the Peristyle. {claim_rule_text(rules)}"
    if kind == "maintain_claim":
        return "Remain at the Peristyle and maintain your pending claim."
    if kind == "claim_checkpoint":
        return "Open succession after the grace round; collected equipment and support are kept."
    if kind == "duel":
        purpose = "Cancel the rival's pending claim if you win" if feats["counterclaim"] else "Duel a rival for Prestige"
        return (f"{purpose}: target {action['target']}, exact single-contest win chance "
                f"{feats['duel_win_probability_exact']:.1%}, cost {feats['prestige_cost']} Prestige; "
                f"end at {dest}.")
    if kind == "guard_post":
        return f"Stand guard at {dest}; exact chance to earn Prestige {feats['prestige_probability_exact']:.0%}."
    distances = ", ".join(f"{k.removeprefix('distance_to_').removesuffix('_after')} {v}" for k, v in feats.items() if k.startswith("distance_to_"))
    return f"Move to {dest}; street distances after moving: {distances}."


def _succession_candidate(action, obs, rules):
    feats = _succession_features(action, obs, rules)
    return {"action_id": action["action_id"], "kind": action["kind"],
            "destination": list(action["destination"]),
            "path_steps": len(action.get("path", [])) - 1,
            "target": action.get("target"), "faction": action.get("faction"),
            "spend_prestige": bool(action.get("spend_prestige")),
            "description": _describe_succession(action, feats, rules),
            "features": feats}


def build_candidates(obs, rules, cap=16, max_cap=400):
    """Deterministic shortlist plus an audit trail of exclusions.

    Essential actions (claim actions, support, explores, searches, and
    duels against a pending claimant) are always kept; if they exceed
    `cap` the cap grows (never silently dropping a win) and the growth
    is logged. Ordinary moves are grouped by destination value.
    """
    legal = obs["legal_actions"]
    if not legal:
        raise ValueError("no legal actions in a live turn")
    pending = obs.get("pending_claim")
    mandatory, duels, ordinary = [], {}, []
    essential = {"proclaim", "maintain_claim", "claim_checkpoint", "gain_support", "explore",
                 "search_site"}
    for action in legal:
        kind = action["kind"]
        if kind in essential or (kind == "duel" and pending and action.get("target") == pending["player"]):
            mandatory.append(action)
        elif kind == "duel":
            key = (action["target"], bool(action.get("spend_prestige")))
            if key not in duels or len(action["path"]) < len(duels[key]["path"]):
                duels[key] = action
        else:
            ordinary.append(action)
    mandatory.extend(duels.values())
    kept = {a["action_id"]: a for a in mandatory}
    # Keep each available productive category before filling route alternatives.
    for kind in ("guard_post",):
        pool = [a for a in ordinary if a["kind"] == kind]
        if pool:
            best = min(pool, key=lambda a: (len(a["path"]), a["destination"]))
            kept[best["action_id"]] = best
    moves = [a for a in ordinary if a["kind"] == "move"]
    for targets in _succession_goals(obs, rules).values():
        if not targets or not moves:
            continue
        distances = [_succession_distances(obs, rules, c) for c in targets]
        best = min(moves, key=lambda a: (
            min(d[tuple(a["destination"])] for d in distances),
            len(a["path"]), a["destination"]))
        kept[best["action_id"]] = best
    effective_cap = max(cap, len(kept))
    if effective_cap > max_cap:
        raise ValueError(f"essential succession actions exceed Decisions limit {max_cap}")
    ranked = sorted(ordinary, key=lambda a: (a["kind"] != "guard_post", len(a["path"]), a["destination"]))
    for action in ranked:
        if len(kept) >= effective_cap:
            break
        kept.setdefault(action["action_id"], action)
    selected = sorted(kept.values(), key=lambda a: (a["kind"], a["destination"], a.get("target", ""), bool(a.get("spend_prestige"))))
    excluded = [{"action_id": a["action_id"], "kind": a["kind"],
                 "destination": a["destination"],
                 "reason": "same strategic target or grouped route; essential objectives and claim responses retained"}
                for a in legal if a["action_id"] not in kept]
    if effective_cap > cap:
        excluded.append({"note": f"cap raised {cap} -> {effective_cap} to preserve objectives and response options"})
    return [_succession_candidate(a, obs, rules) for a in selected], excluded
