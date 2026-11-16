# ABOUTME: Thin adapter over the Dioclet engine for Arena: new game,
# ABOUTME: observe, project, candidates, apply, result, invariants.
import candidate_actions
import engine


def new_game(rules, seed, game_id):
    return engine.new_game(rules, seed, game_id)


def observe(state):
    return engine.observe(state, state["active_player"])


def projection(obs, rules):
    return candidate_actions.project_observation(obs, rules)


def candidates(obs, rules, cap=16):
    return candidate_actions.build_candidates(obs, rules, cap=cap)


def legal_ids(obs):
    return {action["action_id"] for action in obs["legal_actions"]}


def apply(state, action_id, reason=None):
    return engine.apply_action(state, state["active_player"],
                               state["turn_id"], action_id, reason)


def finished(state):
    return engine.is_finished(state)


def result(state):
    return engine.result(state)


def check_invariants(state):
    return engine.check_invariants(state)
