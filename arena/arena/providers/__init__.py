# ABOUTME: The provider contract every Arena seat uses: one decide() call per turn.
# ABOUTME: Local bots and remote decision models both implement this interface.

from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """One decision attempt failed. The runner retries once, then stops."""


class TransportError(ProviderError):
    """Network, timeout, or HTTP-level failure."""


class RefusalError(ProviderError):
    """The provider refused to answer."""


class InvalidAnswerError(ProviderError):
    """The answer is malformed, or not a current legal action id."""


@dataclass(frozen=True)
class Decision:
    action_id: str
    probabilities: dict[str, float] | None = None
    latency_ms: float = 0.0
    usage: dict | None = None
    cost_usd: float = 0.0
    reason: str = "provider_choice"


@dataclass(frozen=True)
class TurnView:
    """Everything a seat may see for one turn. Public data only."""

    observation: dict
    projection: dict
    candidates: list
    rules: dict

    @property
    def legal_ids(self) -> set[str]:
        return {a["action_id"] for a in self.observation["legal_actions"]}


class Provider(Protocol):
    name: str
    model: str
    timeout_s: float

    def decide(self, view: TurnView) -> Decision: ...


# Environment variables each remote provider needs before it is offered.
REQUIRED_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "jev": ("TYPESAFE_API_KEY",),
    "clef": ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"),
    "pplx": ("PERPLEXITY_API_KEY",),
}

REMOTE_PROVIDERS = ("openai", "jev", "clef", "pplx")

# Default model per remote provider, per the plan's example match config.
DEFAULT_MODELS = {
    "openai": "gpt-6-luna",
    "jev": "jev-latest",
    "clef": "clef-flash",
    "pplx": "pplx-decider-v1.3",
}


def default_model(provider: str) -> str:
    return DEFAULT_MODELS.get(provider, "")


def local_provider_names() -> list[str]:
    from arena.providers import local

    return list(local.NAMES)


def available_remote_providers(env) -> list[str]:
    """Remote providers whose required variables are all set."""
    return [name for name in REMOTE_PROVIDERS
            if all(env.get(var) for var in REQUIRED_ENV[name])]


def build_provider(name: str, model: str | None = None):
    """Build a provider by seat-config name; lazy imports keep deps optional."""
    if name in REMOTE_PROVIDERS:
        modules = {"openai": "arena.providers.openai_decisions",
                   "jev": "arena.providers.jev",
                   "clef": "arena.providers.clef",
                   "pplx": "arena.providers.pplx"}
        import importlib

        module = importlib.import_module(modules[name])
        return module.build(model)
    from arena.providers import local

    return local.build(name)
