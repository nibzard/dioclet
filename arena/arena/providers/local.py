# ABOUTME: Local seat providers wrapping the real scripted bots.
# ABOUTME: No keys and no network; every choice comes from the public observation.

import random

import policies

from arena.providers import Decision, TurnView

# Names accepted by policies.act, including the tactical profile.
NAMES = ("tactical", "balanced", "greedy", "aggressive", "random",
         "collector", "early_support", "prestige_farmer", "counterleader",
         "balanced_se")


class LocalBot:
    """One seat driven by a built-in policy; mirrors the ai_driver dispatch."""

    def __init__(self, name: str, rng: random.Random | None = None):
        if name not in NAMES:
            raise ValueError(
                f"unknown local provider {name!r}; expected one of {NAMES}")
        self.name = name
        self.model = "local"
        self.timeout_s = 0.0
        self._rng = rng or random.Random(f"arena-local:{name}")

    def decide(self, view: TurnView) -> Decision:
        obs = view.observation
        action_id, reason = policies.act(self.name, obs, self._rng)
        return Decision(action_id=action_id, reason=reason)


def build(name: str, rng: random.Random | None = None) -> LocalBot:
    return LocalBot(name, rng=rng)
