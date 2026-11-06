"""Four built-in, observation-only bot policies (SPEC §10).

Every policy picks only from `observation["legal_actions"]`. Policies never
see the hidden equipment mapping, future dice, or engine RNG state. Only the
`random` policy uses randomness; its RNG is supplied by the caller and is
separate from all engine streams (DECISIONS.md D14).
"""

# Category weights for the random policy (DECISIONS.md D13).
RANDOM_CATEGORY_WEIGHTS = {
    "claim_checkpoint": 4,
    "explore": 3,
    "attempt_seal": 3,
    "attack_emperor": 3,
    "duel": 2,
    "guard_post": 2,
    "move": 1,
}


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _by_kind(actions, kind):
    return [a for a in actions if a["kind"] == kind]


def _path_len(action):
    return len(action["path"]) - 1


def _dest_key(action):
    return (action["destination"][0], action["destination"][1])


def _nearest(actions):
    """Stable pick: shortest path, then destination coordinate order."""
    return min(actions, key=lambda a: (_path_len(a), _dest_key(a)))


def _best_move_toward(actions, target):
    """Move action whose destination is closest to the target cell."""
    moves = _by_kind(actions, "move")
    if not moves:
        return None
    return min(moves, key=lambda a: (_manhattan(a["destination"], target),
                                     _dest_key(a)))


def _me(obs):
    return obs["players"][obs["viewer"]]


def _level1_explore_target(obs):
    """Best district to head for: revealed-and-missing first, else unrevealed."""
    board = obs["board"]
    revealed = obs["revealed_districts"]
    mine = set(_me(obs)["equipment"])
    known = [list(cell) for name, cell in board["districts"].items()
             if name in revealed and revealed[name] not in mine]
    unknown = [list(cell) for name, cell in board["districts"].items()
               if name not in revealed]
    me_pos = _me(obs)["position"]
    for pool in (known, unknown):
        if pool:
            return min(pool, key=lambda c: (_manhattan(me_pos, c), c[0], c[1]))
    return None


def _level2_target(obs):
    """Nearest lacking seal site, or the Emperor once eligible."""
    board = obs["board"]
    me = _me(obs)
    lacking = [list(cell) for name, cell in board["seal_sites"].items()
               if name not in me["seals"]]
    me_pos = me["position"]
    if lacking and len(me["seals"]) < obs["progress"]["seals_required"]:
        return min(lacking, key=lambda c: (_manhattan(me_pos, c), c[0], c[1]))
    return list(board["emperor"])


def _prefer_spend(actions, kind, want_spend):
    for action in actions:
        if action["kind"] == kind and action.get("spend_glory") is want_spend:
            return action
    spenders = [a for a in actions if a["kind"] == kind]
    return spenders[0] if spenders else None


def _pick_duel(obs, actions, max_target_bonus=None):
    """Duel with the most winnable target; None if none is acceptable."""
    duels = _by_kind(actions, "duel")
    if not duels:
        return None
    me_glory = _me(obs)["glory"]
    if me_glory >= obs["glory_cap"]:
        return None  # avoid fights while capped (SPEC §10 balanced/aggressive)
    def key(a):
        bonus = obs["players"][a["target"]]["equipment_bonus"]
        blocked = max_target_bonus is not None and bonus > max_target_bonus
        return (1 if blocked else 0, bonus, _path_len(a), _dest_key(a))
    best = min(duels, key=key)
    if key(best)[0]:
        return None
    return best


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

def policy_random(obs, rng):
    actions = obs["legal_actions"]
    kinds = {a["kind"] for a in actions}
    weights = [RANDOM_CATEGORY_WEIGHTS.get(k, 1) for k in sorted(kinds)]
    kind = rng.choices(sorted(kinds), weights=weights, k=1)[0]
    pool = _by_kind(actions, kind)
    action = rng.choice(sorted(pool, key=lambda a: a["action_id"]))
    return action["action_id"], f"random choice: {kind}"


def policy_greedy(obs, rng=None):
    actions = obs["legal_actions"]
    if obs["phase"] == 1:
        if _by_kind(actions, "claim_checkpoint"):
            return _by_kind(actions, "claim_checkpoint")[0]["action_id"], \
                "trigger the Level 2 transition now"
        explores = _by_kind(actions, "explore")
        if explores:
            revealed = obs["revealed_districts"]
            mine = set(_me(obs)["equipment"])
            board = obs["board"]

            def certain(a):
                name = next(n for n, c in board["districts"].items()
                            if list(c) == a["destination"])
                return 0 if (name in revealed
                             and revealed[name] not in mine) else 1
            best = min(explores, key=lambda a: (certain(a), _path_len(a),
                                                _dest_key(a)))
            return best["action_id"], "collect the nearest useful district"
        target = _level1_explore_target(obs)
        if target is None:
            target = list(obs["board"]["checkpoint"])
        move = _best_move_toward(actions, target)
        return move["action_id"], f"move toward {_manhattan(move['destination'], target)} steps from target"
    # Level 2: Emperor as soon as eligible, never spends Glory.
    if _by_kind(actions, "attack_emperor"):
        action = _prefer_spend(actions, "attack_emperor", False)
        return action["action_id"], "attack the Emperor"
    seals = _by_kind(actions, "attempt_seal")
    if seals:
        best = min(seals, key=lambda a: (_path_len(a), _dest_key(a)))
        return best["action_id"], "claim the nearest missing seal"
    move = _best_move_toward(actions, _level2_target(obs))
    return move["action_id"], "move toward the next objective"


def policy_aggressive(obs, rng=None):
    actions = obs["legal_actions"]
    duel = _pick_duel(obs, actions)
    if duel:
        return duel["action_id"], f"duel {duel['target']} for Glory"
    if obs["phase"] == 1:
        if _by_kind(actions, "claim_checkpoint"):
            return _by_kind(actions, "claim_checkpoint")[0]["action_id"], \
                "trigger the Level 2 transition now"
        explores = _by_kind(actions, "explore")
        if explores:
            best = min(explores, key=lambda a: (_path_len(a), _dest_key(a)))
            return best["action_id"], "collect the nearest district"
        target = _level1_explore_target(obs) or list(obs["board"]["checkpoint"])
        move = _best_move_toward(actions, target)
        return move["action_id"], "move toward the next district"
    if _by_kind(actions, "attack_emperor"):
        action = _prefer_spend(actions, "attack_emperor", True)
        return action["action_id"], "attack the Emperor, spending Glory"
    seals = _by_kind(actions, "attempt_seal")
    if seals:
        action = _prefer_spend(seals, "attempt_seal", True) if any(
            s.get("spend_glory") for s in seals) else _nearest(seals)
        return action["action_id"], "claim a seal, spending Glory if offered"
    move = _best_move_toward(actions, _level2_target(obs))
    return move["action_id"], "move toward the next objective"


def policy_balanced(obs, rng=None):
    actions = obs["legal_actions"]
    me = _me(obs)
    if obs["phase"] == 1:
        if _by_kind(actions, "claim_checkpoint"):
            return _by_kind(actions, "claim_checkpoint")[0]["action_id"], \
                "trigger the Level 2 transition now"
        certain = [a for a in _by_kind(actions, "explore")]
        if certain:
            best = min(certain, key=lambda a: (_path_len(a), _dest_key(a)))
            return best["action_id"], "collect the nearest district"
        posts = _by_kind(actions, "guard_post")
        if posts and me["glory"] < obs["glory_cap"]:
            return _nearest(posts)["action_id"], "earn Glory at a guard post"
        duel = _pick_duel(obs, actions, max_target_bonus=me["equipment_bonus"])
        if duel:
            return duel["action_id"], f"duel {duel['target']} while Glory is useful"
        target = _level1_explore_target(obs)
        if target is None:
            posts_cells = obs["board"]["glory_posts"]
            target = min(posts_cells, key=lambda c: _manhattan(me["position"], c))
        move = _best_move_toward(actions, list(target))
        return move["action_id"], "move toward the next objective"
    if _by_kind(actions, "attack_emperor"):
        at_cap = me["glory"] >= obs["glory_cap"]
        action = _prefer_spend(actions, "attack_emperor", at_cap)
        return action["action_id"], \
            f"attack the Emperor{' with Glory' if at_cap else ''}"
    seals = _by_kind(actions, "attempt_seal")
    if seals:
        if any(s.get("spend_glory") for s in seals) and \
                me["glory"] >= obs["glory_cap"]:
            action = _prefer_spend(seals, "attempt_seal", True)
        else:
            action = min(seals, key=lambda a: (_path_len(a), _dest_key(a)))
        return action["action_id"], "claim the nearest missing seal"
    if me["glory"] == 0:
        duel = _pick_duel(obs, actions)
        if duel:
            return duel["action_id"], "refuel on Glory through a duel"
    move = _best_move_toward(actions, _level2_target(obs))
    return move["action_id"], "move toward the next objective"


POLICIES = {
    "random": policy_random,
    "greedy": policy_greedy,
    "aggressive": policy_aggressive,
    "balanced": policy_balanced,
}


def act(policy_name, obs, rng):
    """Run one policy; returns (action_id, reason)."""
    try:
        func = POLICIES[policy_name]
    except KeyError:
        raise ValueError(f"unknown policy {policy_name!r}; "
                         f"expected one of {sorted(POLICIES)}") from None
    return func(obs, rng)
