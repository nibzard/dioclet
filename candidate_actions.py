# ABOUTME: Observation-only projection and candidate shortlists for the
# ABOUTME: succession game; reads public observations and rules only.
"""Observation-only projection and candidate shortlists.

Everything here is a pure function of one public observation plus the
public rules file. Nothing reads engine internals, `state.json`, or
future randomness. The shortlist never invents or renames actions: it
only filters, groups, and annotates the engine's `legal_actions`.
"""

import json

from board import Board

SUCCESSION_SCHEMA_VERSION = "v08-succession-proj-1"


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
    cfg = rules["succession"]
    window = cfg["claim_window_rounds"]
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
    if window:
        summary["claim_response_rule"] = (
            f"The claim wins after surviving {window} full round(s) uncancelled; "
            "responses do not crown it - rivals must cancel it inside the window.")
    else:
        summary["claim_response_rule"] = "Each distinct rival completes one response turn."
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
            "reach the Peristyle in the succession phase, proclaim a claim, "
            "and survive "
            "one completed response turn from each rival. Collect equipment "
            "for lasting duel strength. Earn and spend Prestige on support "
            "or contesting a claim. A rival's successful challenge "
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
            "Only one-step dice probabilities are exact. Action choice "
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
        feats.update({
            "duel_win_probability_exact": round(duel_win_probability(
                me["equipment_bonus"], target["equipment_bonus"],
                rules["duels"]["tie_winner"] == "attacker",
                rules["movement"]["die_sides"]), 6),
            "prestige_cost": action.get("contest_cost", 0),
            "target_support_count": len(target["support"]),
            "target_equipment_bonus": target["equipment_bonus"],
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
    return feats


def _describe_succession(action, feats):
    kind, dest = action["kind"], action["destination"]
    if kind == "explore":
        return f"Collect at district {feats['district']}; equipment stays with you in both phases."
    if kind == "search_site":
        return f"Search the face-down faction card at {dest}; the result is public."
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
