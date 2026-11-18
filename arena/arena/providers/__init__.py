# ABOUTME: The provider contract every Arena seat uses: one decide() call per turn.
# ABOUTME: Local bots and remote decision models both implement this interface.

from dataclasses import dataclass
from typing import Protocol
import re


class ProviderError(Exception):
    """One decision attempt failed. The runner retries once, then stops.

    `exchange` holds the request sent and the response received, when
    the failure happened after the request was built. It never holds
    keys or HTTP headers. `retry_after_s` carries the provider's own
    wait hint when the failure is a rate limit.
    """

    def __init__(self, message, exchange=None, retry_after_s=None):
        super().__init__(message)
        self.exchange = exchange
        self.retry_after_s = retry_after_s


class TransportError(ProviderError):
    """Network, timeout, or HTTP-level failure."""


_RETRY_AFTER_TEXT = re.compile(r"[Rr]etry [Aa]fter (\d+) ?s")


def parse_retry_after(*texts):
    """The provider's wait hint in seconds, or None.

    Reads a Retry-After style hint from any error text the adapters
    hold: the HTTP header value (a bare seconds count), or a body or
    SDK message that says "Retry after Ns". Only whole-second hints
    are understood.
    """
    for text in texts:
        if not text:
            continue
        if isinstance(text, (int, float)) and not isinstance(text, bool):
            return float(text)
        stripped = str(text).strip()
        if stripped.isdigit():
            return float(stripped)
        match = _RETRY_AFTER_TEXT.search(stripped)
        if match:
            return float(match.group(1))
    return None


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
    confidence: float | None = None
    # {"request": <exact body sent>, "response": {"status_code", "body"}}.
    exchange: dict | None = None


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
    "gateway": ("AI_GATEWAY_API_KEY",),
}

REMOTE_PROVIDERS = ("openai", "jev", "clef", "pplx", "gateway")

# Default model per remote provider, per the plan's example match config.
DEFAULT_MODELS = {
    "openai": "gpt-6-luna",
    "jev": "jev-latest",
    "clef": "clef-flash",
    "pplx": "pplx-decider-v1.3",
    "gateway": "nace-ai/drex-v2.0",
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
                   "pplx": "arena.providers.pplx",
                   "gateway": "arena.providers.gateway"}
        import importlib

        module = importlib.import_module(modules[name])
        return module.build(model)
    from arena.providers import local

    return local.build(name)
