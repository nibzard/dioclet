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
    if _is_succession(obs, rules):
        return _project_succession(obs, rules)
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
    if _is_succession(obs, rules):
        return _build_succession_candidates(obs, rules, cap=cap)
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


# ---------------------------------------------------------------------------
# V0.8 succession projection. Public observation only.
# ---------------------------------------------------------------------------

SUCCESSION_SCHEMA_VERSION = "v08-succession-proj-1"


def _is_succession(obs=None, rules=None):
    return (obs or {}).get("gameplay_mode") == "succession-v1" or \
        (rules or {}).get("gameplay_mode") == "succession-v1"


def _succession_rule_summary(rules):
    cfg = rules["succession"]
    window = cfg.get("claim_window_rounds", 0)
    summary = {
        "prestige_cap": rules["glory"]["cap"],
        "support_cost": cfg["support_cost"],
        "required_support": cfg["required_support"],
        "support_in_city": (cfg["support_in_city"] and not cfg.get("blind_support")),
        "challenge_cost": cfg["challenge_cost"],
        "challenge_bonus": cfg["challenge_bonus"],
        "contest_cost": cfg.get("contest_cost", 0),
        "support_is_permanent": True,
        "equipment_is_persistent": True,
        "free_equipment_at_transition": False,
        "successful_challenge": "Cancel the claim; claimant returns to their own assigned gate.",
        "duel_tie_goes_to": "defender" if rules["combat"]["tie_goes_to_defender"] else "attacker",
        "guard_success_min_roll": rules["glory"]["guard_post_success_min_roll"],
        "duel_range": rules["movement"]["duel_range"],
        "grace_full_rounds": rules["level1"]["grace_full_rounds"],
    }
    if window:
        summary["claim_response_rule"] = (
            f"The claim wins after surviving {window} full round(s) uncancelled; "
            "responses do not crown it - rivals must cancel it inside the window.")
    else:
        summary["claim_response_rule"] = "Each distinct rival completes one response turn."
    if cfg.get("duel_loser_cost"):
        summary["duel_loser_cost"] = cfg["duel_loser_cost"]
    if cfg.get("proclaim_cost"):
        summary["proclaim_cost"] = cfg["proclaim_cost"]
    if cfg.get("blind_support"):
        summary["support_sites"] = ("Palace level only: the three faction meeting places "
                                    "are hidden among six candidate cells; end movement on "
                                    "one and search to reveal it.")
    abilities = rules["combat"].get("abilities")
    if abilities:
        summary["equipment_abilities"] = {item: spec["type"] for item, spec in sorted(abilities.items())}
    return summary


def _project_succession(obs, rules):
    me = obs["players"][obs["viewer"]]
    public_players = []
    for pid, p in sorted(obs["players"].items()):
        public_players.append({
            "id": pid, "position": p["position"],
            "gate": p["gate"], "gate_id": p["gate_id"],
            "equipment": list(p["equipment"]),
            "equipment_count": p["equipment_count"],
            "equipment_bonus": p["equipment_bonus"],
            "prestige": p["prestige"], "support": list(p["support"]),
        })
    return {
        "schema": SUCCESSION_SCHEMA_VERSION,
        "gameplay_mode": "succession-v1", "game_id": obs["game_id"],
        "objective": (
            "Win the succession: gain support from two different factions, "
            "reach the Peristyle in phase 2, proclaim a claim, and survive "
            "one completed response turn from each rival. Collect equipment "
            "for lasting duel strength. Earn and spend Prestige on support "
            "or a declared challenge bonus. A rival's successful challenge "
            "cancels your claim. A pending rival claim must be stopped before "
            "its final outstanding response ends. Choose to maximize your "
            "eventual chance of winning, not merely immediate resources."),
        "turn": {"id": obs["turn_id"], "round": obs["round"],
                 "phase": obs["phase"], "player": obs["viewer"],
                 "movement_die": obs["movement_die"],
                 "turn_order_this_round": obs["turn_order"]},
        "self": next(p for p in public_players if p["id"] == obs["viewer"]),
        "opponents": [p for p in public_players if p["id"] != obs["viewer"]],
        "pending_claim": obs.get("pending_claim"),
        "public_locations": {key: obs["board"][key] for key in (
            "width", "height", "blocked", "gates", "districts", "glory_posts",
            "checkpoint") if key in obs["board"]},
        # Blind palace-level support sites replace the printed faction cells;
        # only candidates and already-revealed sites are public (D17/D25).
        **({"support_sites": obs["board"]["support_sites"]}
           if "support_sites" in obs["board"] else
           {"factions": obs["board"]["factions"]}),
        "gate_assignments": obs["gate_assignments"],
        "revealed_districts": dict(obs["revealed_districts"]),
        "equipment_names": list(obs["equipment_names"]),
        "missing_equipment": sorted(set(obs["equipment_names"]) - set(me["equipment"])),
        "progress": dict(obs["progress"]),
        "rule_summary": _succession_rule_summary(rules),
        "limits": (
            "Only one-step dice probabilities are exact. Action choice "
            "probabilities are model preferences, not win rates or human fun scores. "
            "Unrevealed treasure locations and future dice are not supplied."),
    }


def _succession_distances(obs, rules, start):
    # The public rules contain only geometry. No state or secret is read.
    from board import Board
    return Board(rules).distances(tuple(start))


def _succession_goals(obs, rules):
    me = obs["players"][obs["viewer"]]
    board = obs["board"]
    goals = {"claim": [board["checkpoint"]], "collection": [],
             "support": [], "prestige": board["glory_posts"]}
    for name, cell in board["districts"].items():
        revealed = obs["revealed_districts"].get(name)
        if revealed is None or revealed not in me["equipment"]:
            goals["collection"].append(cell)
    if "support_sites" in board:  # blind palace-level sites
        for cell in board["support_sites"]["candidates"]:
            goals["support"].append(cell)
    else:
        for name, cell in board["factions"].items():
            if name not in me["support"]:
                goals["support"].append(cell)
    pending = obs.get("pending_claim")
    if pending and pending["player"] != obs["viewer"]:
        goals["counterclaim"] = [obs["players"][pending["player"]]["position"]]
    return goals


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
        bonus = rules["succession"]["challenge_bonus"] if action.get("spend_prestige") else 0
        feats.update({
            "duel_win_probability_exact": round(duel_win_probability(
                me["equipment_bonus"] + bonus, target["equipment_bonus"],
                not rules["combat"]["tie_goes_to_defender"],
                rules["movement"]["die_sides"]), 6),
            "prestige_cost": action.get("contest_cost", 0) + (rules["succession"]["challenge_cost"] if action.get("spend_prestige") else 0),
            "target_support_count": len(target["support"]),
            "target_equipment_bonus": target["equipment_bonus"],
            "would_cancel_claim_if_won": feats["counterclaim"],
        })
    elif action["kind"] == "gain_support":
        feats["faction"] = action["faction"]
        feats["prestige_cost"] = rules["succession"]["support_cost"]
    elif action["kind"] == "guard_post":
        feats["prestige_probability_exact"] = threshold_probability(
            rules["glory"]["guard_post_success_min_roll"], rules["movement"]["die_sides"])
    elif action["kind"] == "explore":
        district = next(name for name, cell in obs["board"]["districts"].items() if list(cell) == dest)
        feats["district"] = district
        feats["district_revealed"] = district in obs["revealed_districts"]
        # Do not use action.get('item') even if a malformed caller supplies it.
        if district in obs["revealed_districts"]:
            feats["public_item"] = obs["revealed_districts"][district]
    return feats


def _describe_succession(action, feats):
    kind, dest = action["kind"], action["destination"]
    if kind == "explore":
        return f"Collect at district {feats['district']}; equipment stays with you in both phases."
    if kind == "gain_support":
        return f"Gain {action['faction']} support for {feats['prestige_cost']} Prestige, without a die test."
    if kind == "proclaim":
        return "Proclaim your claim at the Peristyle; win if it survives one response from every rival."
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
            "description": _describe_succession(action, feats), "features": feats}


def _build_succession_candidates(obs, rules, cap=16, max_cap=400):
    legal = obs["legal_actions"]
    if not legal:
        raise ValueError("no legal actions in a live turn")
    pending = obs.get("pending_claim")
    mandatory, duels, ordinary = [], {}, []
    essential = {"proclaim", "maintain_claim", "claim_checkpoint", "gain_support", "explore"}
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
