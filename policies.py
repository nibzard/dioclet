# ABOUTME: Bot-policy front door: one registry of every built-in bot name,
# ABOUTME: and the dispatch into the engine's succession policies.
"""Policy names and the dispatch into the engine's built-in bots.

The engine module owns the succession policies (engine.choose_policy).
This module keeps the shared name registry. Callers test membership in
`POLICIES` and choose through `act`.
"""

import engine

# Every built-in succession bot, keyed by name. The values are unused:
# callers only test membership. `act` dispatches to the engine.
POLICIES = dict.fromkeys(engine.POLICY_NAMES)


def act(policy_name, obs, rng):
    """Run one policy; returns (action_id, reason)."""
    return engine.choose_policy(policy_name, obs, rng)
