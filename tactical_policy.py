"""Deterministic tactical benchmark policy (V0.4, observation-only).

A short-horizon rational player used to evaluate decision quality. It
must beat the trap the old `aggressive` bot falls into: dueling before
an available game-winning Emperor attack. Version-frozen parameters;
changes require a new recorded experiment version.

TACTICAL_VERSION = "tactical-v04.1" (frozen 2026-11-07)
"""

from candidate_actions import (contest_probability, duel_win_probability,
                               threshold_probability)

TACTICAL_VERSION = "tactical-v04.1"

# Frozen parameters (documented; do not tune after comparisons).
EMPEROR_SPEND_MIN_GAIN = 0.15   # spend 1 Glory only if +2 adds >= this
PERISTYLE_SPEND_AT_CAP_ONLY = True  # buy the guaranteed seal only at cap
DUEL_MIN_WIN_PROB = 0.50
DUEL_THREAT_MIN = 1             # target seals+hits needed to bother
DUEL_LOSTTURN_THREAT_MIN = 1


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _by_kind(actions, kind):
    return [a for a in actions if a["kind"] == kind]


def _nearest(actions):
    return min(actions, key=lambda a: (len(a["path"]),
                                       a["destination"][0],
                                       a["destination"][1]))


def choose(obs, rules):
    """Return (action_id, reason_code). Depends only on the observation."""
    actions = obs["legal_actions"]
    me = obs["players"][obs["viewer"]]
    board = obs["board"]
    emperor = board["emperor"]
    hits_to_win = obs["progress"].get(
        "emperor_hits_to_win", rules["combat"]["emperor_hits_to_win"])
    seals_required = obs["progress"].get(
        "seals_required", rules["level2"]["required_distinct_seals"])

    # 1. Emperor attacks first, ranked by exact odds; a hit that would
    #    win the game outranks every duel.
    attacks = _by_kind(actions, "attack_emperor")
    if attacks:
        def attack_key(a):
            p = _attack_success(a, me, rules)
            spend_penalty = 1 if a.get("spend_glory") else 0
            winning = me["emperor_hits"] + 1 >= hits_to_win
            return (0 if winning else 1, -p, spend_penalty,
                    a["destination"][0], a["destination"][1])
        best = min(attacks, key=attack_key)
        winning = me["emperor_hits"] + 1 >= hits_to_win
        p_best = _attack_success(best, me, rules)
        spend = best.get("spend_glory", False)
        if spend:
            return best["action_id"], "emperor_attack_spend"
        if winning:
            return best["action_id"], "emperor_attack_win"
        # Spend Glory when the +2 materially raises the exact odds.
        free = next((a for a in attacks if not a.get("spend_glory")), None)
        paid = next((a for a in attacks if a.get("spend_glory")), None)
        if free is not None and paid is not None:
            gain = _attack_success(paid, me, rules) - \
                _attack_success(free, me, rules)
            if gain >= EMPEROR_SPEND_MIN_GAIN and me["glory"] >= 1:
                return paid["action_id"], "emperor_attack_spend"
        return best["action_id"], "emperor_attack"

    # 2. Seals when short of the Emperor requirement.
    seals = _by_kind(actions, "attempt_seal")
    if seals and len(me["seals"]) < seals_required:
        lacking = [a for a in seals if _site_name(a, board) not in me["seals"]]
        pool = lacking or seals
        spenders = [a for a in pool if a.get("spend_glory")]
        if spenders and me["glory"] >= 1 and (
                not PERISTYLE_SPEND_AT_CAP_ONLY
                or me["glory"] >= obs["glory_cap"]):
            return min(spenders, key=_path_key)["action_id"], "seal_buy_at_cap"
        rollable = [a for a in pool if not a.get("spend_glory")]
        if rollable:
            return _nearest(rollable)["action_id"], "seal_roll"
        return _nearest(pool)["action_id"], "seal_any"

    # 3. Checkpoint (immediately, it is on the objective path).
    claims = _by_kind(actions, "claim_checkpoint")
    if claims:
        return claims[0]["action_id"], "claim_checkpoint"

    # 4. Certain exploration first, then unknown districts.
    explores = _by_kind(actions, "explore")
    if explores:
        revealed = obs["revealed_districts"]
        mine = set(me["equipment"])
        certain = []
        for a in explores:
            name = next((n for n, c in board["districts"].items()
                         if list(c) == a["destination"]), None)
            if name in revealed and revealed.get(name) not in mine:
                certain.append(a)
        pool = certain or explores
        return _nearest(pool)["action_id"], \
            "explore_certain" if certain else "explore_unknown"

    # 5. Duels by expected payoff (never above an Emperor/seal/explore
    #    option). Fight only with an edge and against a threat.
    duels = _by_kind(actions, "duel")
    if duels and obs["phase"] == 2:
        best = _best_duel(duels, obs, rules, emperor)
        if best is not None:
            return best

    # 6. Guard posts when Glory has room.
    posts = _by_kind(actions, "guard_post")
    if posts and me["glory"] < obs["glory_cap"]:
        return _nearest(posts)["action_id"], "guard_glory"

    # 7. Level 1 duels with an edge against a threat.
    if duels:
        best = _best_duel(duels, obs, rules, emperor)
        if best is not None:
            return best

    # 8. Advance toward the current goal; never shuffle in place.
    target = _goal(obs, rules)
    moves = _by_kind(actions, "move")
    if moves:
        best = min(moves, key=lambda a: (_manhattan(a["destination"], target),
                                         a["destination"][0],
                                         a["destination"][1]))
        return best["action_id"], "advance"
    return actions[0]["action_id"], "forced"


def _path_key(a):
    return (len(a["path"]), a["destination"][0], a["destination"][1])


def _attack_success(action, me, rules):
    bonus = me["equipment_bonus"] + (
        rules["combat"]["glory_attack_bonus"]
        if action.get("spend_glory") else 0)
    return contest_probability(bonus, rules["combat"]["emperor_bonus"],
                               tie_wins=False)


def _site_name(action, board):
    return next((name for name, cell in board["seal_sites"].items()
                 if list(cell) == action["destination"]), None)


def _best_duel(duels, obs, rules, emperor):
    me = obs["players"][obs["viewer"]]
    tie_attacker = not rules["combat"]["tie_goes_to_defender"]
    lost_turn = bool(rules["combat"].get("duel_lost_turn"))
    best = None
    for a in duels:
        target = obs["players"][a["target"]]
        p_win = duel_win_probability(me["equipment_bonus"],
                                     target["equipment_bonus"], tie_attacker)
        threat = len(target["seals"]) + target["emperor_hits"]
        near_emperor = _manhattan(target["position"], emperor) <= 3
        threshold = DUEL_LOSTTURN_THREAT_MIN if lost_turn else DUEL_THREAT_MIN
        glory_room = me["glory"] < obs["glory_cap"]
        interferences_value = threat >= threshold or near_emperor
        if p_win >= DUEL_MIN_WIN_PROB and interferences_value and (
                glory_room or lost_turn):
            key = (-p_win, -threat, len(a["path"]), a["target"])
            if best is None or key < best[0]:
                best = (key, (a["action_id"], "duel_edge"))
    return best[1] if best else None


def _goal(obs, rules):
    board = obs["board"]
    me = obs["players"][obs["viewer"]]
    if obs["phase"] == 2:
        lacking = [list(c) for n, c in board["seal_sites"].items()
                   if n not in me["seals"]]
        if lacking and len(me["seals"]) < obs["progress"].get(
                "seals_required", 2):
            return min(lacking, key=lambda c: (
                _manhattan(me["position"], c), c[0], c[1]))
        return board["emperor"]
    revealed = obs["revealed_districts"]
    mine = set(me["equipment"])
    known = [list(c) for n, c in board["districts"].items()
             if n in revealed and revealed[n] not in mine]
    unknown = [list(c) for n, c in board["districts"].items()
               if n not in revealed]
    pool = known or unknown
    if pool:
        return min(pool, key=lambda c: (
            _manhattan(me["position"], c), c[0], c[1]))
    return board["checkpoint"]
