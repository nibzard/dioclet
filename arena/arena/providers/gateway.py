# ABOUTME: Vercel AI Gateway seat provider on its OpenAI-compatible Decisions API.
# ABOUTME: One key reaches many vendors' decision models by "vendor/model" id.

import os

from arena.providers import ProviderError
from arena.providers.openai_decisions import OpenAIDecisions

BASE_URL = "https://ai-gateway.vercel.sh/v1"
DEFAULT_MODEL = "nace-ai/drex-v2.0"
TIMEOUT_S = 65.0

# USD per million input tokens; output is free. Source: the AI Gateway
# model list, decision type, read on 2026-11-16. Verify before long runs.
# convaiinnovations/laya is not listed: it rejects the Arena request (422).
PRICING = {
    "openai/gpt-6-luna-decisions": 0.10,
    "google/gemini-decision-1": 0.10,
    "microsoft/microsoft-decision-1": 0.04,
    "typesafe-ai/jev": 0.04,
    "typesafe-ai/jev-1.13.0": 0.04,
    "typesafe-ai/jev-1.14.0": 0.04,
    "perplexity/pplx-decider-v1.2": 0.02,
    "perplexity/pplx-decider-flash-v1.2": 0.01,
    "perplexity/pplx-decider-flash-v1.3": 0.01,
    "liquid/d1": 0.02,
    "liquid/d1-ultra": 0.04,
    "nace-ai/drex-v2.0": 0.03,
    "nace-ai/drex-max-v1.1": 0.03,
    "nace-ai/drex-max-finance": 0.03,
    "baseten/joey-1": 0.01,
    "baseten/elephant-1": 0.04,
    "baseten/mammoth-1": 0.10,
    "scaledown/scaledown-classify-1": 0.05,
}

# USD per request: the list shows "$1/K" for the Perplexity models.
PER_REQUEST_USD = {
    "perplexity/pplx-decider-v1.2": 0.001,
    "perplexity/pplx-decider-flash-v1.2": 0.001,
    "perplexity/pplx-decider-flash-v1.3": 0.001,
}


def build(model: str | None = None, client=None) -> OpenAIDecisions:
    model = model or DEFAULT_MODEL
    if model not in PRICING:
        # Budget caps need a price; an unpriced model could overspend.
        raise ProviderError(
            f"gateway has no price for {model!r}; add it to "
            f"arena/providers/gateway.py PRICING")
    api_key = os.environ.get("AI_GATEWAY_API_KEY")
    if not api_key:
        raise ProviderError(
            "gateway needs AI_GATEWAY_API_KEY in the environment")
    if client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                "openai package not installed; "
                "run `uv sync --extra decisions`") from exc
        client = OpenAI(base_url=BASE_URL, api_key=api_key)
    return OpenAIDecisions(client, model, name="gateway", pricing=PRICING,
                           per_request_usd=PER_REQUEST_USD,
                           timeout_s=TIMEOUT_S)
