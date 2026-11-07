"""Observation-only projection and candidate shortlists (V0.4).

Everything here is a pure function of one public observation plus the
public rules file. Nothing reads engine internals, `state.json`, or
future randomness. The shortlist never invents or renames actions: it
only filters, groups, and annotates the engine's `legal_actions`.
"""

import json
import math

PROJECTION_SCHEMA_VERSION = "v04-proj-1"


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


# ---------------------------------------------------------------------------
# Public-rule helpers
# ---------------------------------------------------------------------------

def rule_summary(rules):
    """Public mechanics summary sent to the model (no secrets exist)."""
    return {
        "glory_cap": rules["glory"]["cap"],
        "emperor_hits_to_win": rules["combat"]["emperor_hits_to_win"],
        "seals_required": rules["level2"]["required_distinct_seals"],
        "duel_tie_goes_to": "attacker" if not rules["combat"][
            "tie_goes_to_defender"] else "defender",
        "duel_lost_turn": bool(rules["combat"].get("duel_lost_turn")),
        "duel_displacement": bool(rules["combat"].get("duel_displacement")),
        "duel_glory_theft": bool(rules["combat"].get("duel_glory_theft")),
        "peristyle_glory_cost": rules["level2"]["peristyle_glory_cost"],
        "glory_attack_bonus": rules["combat"]["glory_attack_bonus"],
        "grace_full_rounds": rules["level1"]["grace_full_rounds"],
        "rotate_first_player": bool(
            rules.get("turns", {}).get("rotate_first_player_each_round")),
    }


def _equipment_bonus(count, rules):
    for tier in rules["combat"]["equipment_bonus_tiers"]:
        if tier["min_count"] <= count <= tier["max_count"]:
            return tier["bonus"]
    return 0


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def project_observation(obs, rules):
    """Compact, stable, fully public projection for the model."""
    me = obs["players"][obs["viewer"]]
    board = obs["board"]
    opponents = []
    for pid, pdata in obs["players"].items():
        if pid == obs["viewer"]:
            continue
        opponents.append({
            "id": pid,
            "position": pdata["position"],
            "equipment_count": pdata["equipment_count"],
            "equipment_bonus": pdata["equipment_bonus"],
            "glory": pdata["glory"],
            "seals": pdata["seals"],
            "emperor_hits": pdata["emperor_hits"],
        })
    projection = {
        "schema": PROJECTION_SCHEMA_VERSION,
        "game_id": obs["game_id"],
        "objective": ("Be the first player to land the required Emperor "
                      "hits in level 2. Maximize your eventual win "
                      "chance; level 1 collects equipment, Glory, and "
                      "triggers the transition."),
        "turn": {
            "id": obs["turn_id"], "round": obs["round"], "phase": obs["phase"],
            "player": obs["viewer"], "movement_die": obs["movement_die"],
            "turn_order_this_round": obs["turn_order"],
        },
        "self": {
            "position": me["position"],
            "equipment_count": me["equipment_count"],
            "equipment_bonus": me["equipment_bonus"],
            "missing_equipment": sorted(
                set(obs["equipment_names"]) - set(me["equipment"])),
            "glory": me["glory"],
            "seals": me["seals"],
            "emperor_hits": me["emperor_hits"],
            "skip_next_turn": me.get("skip_next_turn", False),
        },
        "opponents": sorted(opponents, key=lambda o: o["id"]),
        "public_locations": {
            "emperor": board["emperor"], "retreat": board["retreat"],
            "seal_sites": board["seal_sites"],
            "districts": board["districts"],
            "glory_posts": board["glory_posts"],
            "checkpoint": board["checkpoint"],
            "gates": board["gates"],
        },
        "revealed_districts": obs["revealed_districts"],
        "progress": obs["progress"],
        "rule_summary": rule_summary(rules),
    }
    return projection


def projection_hash(projection):
    blob = json.dumps(projection, sort_keys=True, separators=(",", ":"))
    import hashlib
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Candidate shortlist
# ---------------------------------------------------------------------------

MANDATORY_KINDS = ("attack_emperor", "claim_checkpoint", "attempt_seal",
                   "explore")


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _goal_cell(obs, rules):
    """Nearest current objective cell for move grouping (public data)."""
    board = obs["board"]
    me = obs["players"][obs["viewer"]]
    if obs["phase"] == 2:
        lacking = [cell for name, cell in board["seal_sites"].items()
                   if name not in me["seals"]]
        if lacking and len(me["seals"]) < obs["progress"].get(
                "seals_required", 2):
            return min(lacking, key=lambda c: (
                _manhattan(me["position"], c), c[0], c[1]))
        return board["emperor"]
    revealed = obs["revealed_districts"]
    mine = set(me["equipment"])
    known_missing = [list(cell) for name, cell in board["districts"].items()
                     if name in revealed and revealed[name] not in mine]
    unknown = [list(cell) for name, cell in board["districts"].items()
               if name not in revealed]
    pool = known_missing or unknown
    if pool:
        return min(pool, key=lambda c: (
            _manhattan(me["position"], c), c[0], c[1]))
    return board["checkpoint"]


def _action_features(action, obs, rules):
    """Deterministic per-action feature block (exact odds or heuristic)."""
    board = obs["board"]
    me = obs["players"][obs["viewer"]]
    emperor = board["emperor"]
    feats = {
        "path_steps": len(action.get("path", [])) - 1,
        "distance_to_emperor_after": _manhattan(action["destination"],
                                                emperor),
    }
    kind = action["kind"]
    if kind == "duel":
        target = obs["players"][action["target"]]
        p_win = duel_win_probability(
            me["equipment_bonus"], target["equipment_bonus"],
            not rules["combat"]["tie_goes_to_defender"])
        feats["duel_win_probability_exact"] = round(p_win, 4)
        feats["target_glory"] = target["glory"]
        feats["target_emperor_hits"] = target["emperor_hits"]
        feats["target_seals"] = len(target["seals"])
        feats["target_distance_to_emperor"] = _manhattan(
            target["position"], emperor)
    elif kind == "attack_emperor":
        bonus = me["equipment_bonus"] + (
            rules["combat"]["glory_attack_bonus"]
            if action.get("spend_glory") else 0)
        feats["hit_probability_exact"] = round(contest_probability(
            bonus, rules["combat"]["emperor_bonus"], tie_wins=False), 4)
        feats["would_win_game_if_hit"] = (
            me["emperor_hits"] + 1 >= obs["progress"].get(
                "emperor_hits_to_win", 2))
    elif kind == "attempt_seal":
        site = next(name for name, cell in board["seal_sites"].items()
                    if list(cell) == action["destination"])
        if action.get("spend_glory"):
            feats["seal_success_probability_exact"] = 1.0
        elif site == "cellars":
            feats["seal_success_probability_exact"] = round(
                threshold_probability(rules["level2"]["cellars_success_min_roll"]), 4)
        elif site == "peristyle":
            feats["seal_success_probability_exact"] = round(
                threshold_probability(rules["level2"]["peristyle_success_min_roll"]), 4)
        else:  # guard barracks contest
            feats["seal_success_probability_exact"] = round(
                contest_probability(me["equipment_bonus"],
                                    rules["combat"]["imperial_guard_bonus"],
                                    tie_wins=False), 4)
    elif kind == "guard_post":
        feats["glory_probability_exact"] = round(threshold_probability(
            rules["glory"]["guard_post_success_min_roll"]), 4)
        feats["glory_room"] = obs["glory_cap"] - me["glory"]
    elif kind == "explore":
        district = next((name for name, cell in board["districts"].items()
                         if list(cell) == action["destination"]), None)
        feats["district"] = district
        feats["district_revealed"] = district in obs["revealed_districts"]
    goal = _goal_cell(obs, rules)
    feats["distance_to_current_goal_after"] = _manhattan(action["destination"],
                                                         goal)
    return feats


def _describe(action, obs, feats):
    kind = action["kind"]
    dest = action["destination"]
    if kind == "attack_emperor":
        spend = ", spending 1 Glory for +2" if action.get("spend_glory") \
            else " without Glory"
        win = " (wins the game on a hit)" if feats.get("would_win_game_if_hit") \
            else ""
        return (f"Attack the Emperor{spend}; exact hit chance "
                f"{feats['hit_probability_exact']:.0%}{win}.")
    if kind == "duel":
        return (f"Duel {action['target']} "
                f"(exact win chance {feats['duel_win_probability_exact']:.0%}; "
                f"target has {feats['target_emperor_hits']} Emperor hits, "
                f"{feats['target_glory']} Glory).")
    if kind == "attempt_seal":
        spend = " by spending 1 Glory (guaranteed)" \
            if action.get("spend_glory") else " by rolling"
        return (f"Attempt a seal at {dest}{spend}; exact success chance "
                f"{feats['seal_success_probability_exact']:.0%}.")
    if kind == "claim_checkpoint":
        return "Claim the checkpoint: trigger the level transition and +1 Glory."
    if kind == "explore":
        known = "revealed" if feats["district_revealed"] else "unrevealed"
        return f"Move to district {feats['district']} ({known}) and explore it."
    if kind == "guard_post":
        return (f"Work a guard post at {dest}; exact Glory chance "
                f"{feats['glory_probability_exact']:.0%}.")
    return (f"Move to {dest} ({feats['path_steps']} step(s); now "
            f"{feats['distance_to_current_goal_after']} from the current goal).")


def build_candidates(obs, rules, cap=16, max_cap=24):
    """Deterministic shortlist plus an audit trail of exclusions.

    Mandatory actions (winning Emperor attacks, checkpoint, seals,
    explores, duels per distinct target) are always kept; if they
    exceed `cap` the cap grows (never silently dropping a win) and the
    growth is logged. Ordinary moves are grouped by destination value.
    """
    legal = obs["legal_actions"]
    if not legal:
        raise ValueError("no legal actions in a live turn")
    if len(legal) == 1:
        return _finalize(legal, [], obs, rules), []

    mandatory, moves, duels = [], [], {}
    for action in legal:
        kind = action["kind"]
        if kind in MANDATORY_KINDS:
            mandatory.append(action)
        elif kind == "duel":
            key = (action["target"],
                   1 if action.get("spend_glory") else 0)
            # Keep one duel per distinct target (and spend variant),
            # preferring the shortest approach.
            if key not in duels or len(action["path"]) < len(duels[key]["path"]):
                duels[key] = action
        else:
            moves.append(action)

    mandatory.extend(duels.values())
    mandatory.sort(key=_action_sort_key)
    effective_cap = max(cap, len(mandatory))
    if effective_cap > max_cap:
        raise ValueError(
            f"mandatory candidates ({len(mandatory)}) exceed max_cap "
            f"{max_cap}; refusing to discard wins silently")

    goal = _goal_cell(obs, rules)
    # Group moves: one per distinct destination, ranked by usefulness
    # (progress toward the goal first), then keep one deliberately
    # non-greedy alternative (the move furthest from the goal).
    ranked = sorted(moves, key=lambda a: (
        _manhattan(a["destination"], goal),
        a["destination"][0], a["destination"][1]))
    seen_dest = set()
    grouped = []
    for action in ranked:
        key = tuple(action["destination"])
        if key not in seen_dest:
            seen_dest.add(key)
            grouped.append(action)
    room = effective_cap - len(mandatory)
    kept_moves = grouped[:max(0, room - 1)] if len(grouped) > 1 else grouped
    if room > 0 and len(grouped) > len(kept_moves):
        non_greedy = grouped[-1]
        kept_moves.append(non_greedy)
        kept_moves = kept_moves[:room]
    selected = mandatory + kept_moves
    selected.sort(key=_action_sort_key)

    excluded = []
    kept_ids = {a["action_id"] for a in selected}
    for action in legal:
        if action["action_id"] in kept_ids:
            continue
        if action["kind"] == "duel":
            reason = "duplicate duel target (longer approach kept)"
        else:
            reason = "grouped move (a closer or distinct destination kept)"
        excluded.append({"action_id": action["action_id"],
                         "kind": action["kind"],
                         "destination": action["destination"],
                         "reason": reason})
    if effective_cap > cap:
        excluded.append({"note": f"cap raised {cap} -> {effective_cap} to "
                                 f"keep all mandatory candidates"})
    return _finalize(selected, excluded, obs, rules), excluded


def _action_sort_key(action):
    return (action["kind"], action["destination"][0], action["destination"][1],
            action.get("target") or "", 1 if action.get("spend_glory") else 0)


def _finalize(selected, excluded, obs, rules):
    candidates = []
    for action in selected:
        feats = _action_features(action, obs, rules)
        candidates.append({
            "action_id": action["action_id"],
            "kind": action["kind"],
            "destination": action["destination"],
            "path_steps": len(action.get("path", [])) - 1,
            "target": action.get("target"),
            "spend_glory": bool(action.get("spend_glory")),
            "description": _describe(action, obs, feats),
            "features": feats,
        })
    return candidates
