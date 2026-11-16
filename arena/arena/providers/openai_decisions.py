# ABOUTME: OpenAI Decisions seat provider on the official SDK client.decisions.
# ABOUTME: Same request shape and parsing discipline as decisions_policy.LiveProvider.

import dataclasses
import math
import os
import time

from arena.providers import (Decision, InvalidAnswerError, ProviderError,
                             RefusalError, TransportError, TurnView)

DEFAULT_MODEL = "gpt-6-luna"
PRICING = {"*": 0.10}
TIMEOUT_S = 20.0
QUESTION_NAME = "best_action"

INTRO_TEXT = ("Select the best legal board-game move given this public "
              "state. Exact single-roll odds in the features are exact; "
              "any longer-horizon judgement is yours.")
PROJECTION_INSTRUCTIONS = (
    "You are one player in a four-player competitive board game. "
    "Pick the option most likely to improve your eventual chance to be "
    "first to defeat the Emperor. Prefer an immediate legal win over "
    "unrelated actions; consider progress, opponents, and resource tempo. "
    "Use only the supplied public information and action descriptions.")
SUCCESSION_INSTRUCTIONS = (
    "You are a player in a four-player imperial succession game. "
    "Choose the legal action that maximizes your eventual chance "
    "of being acclaimed emperor. Use the supplied objective and "
    "response-window rules, not an Emperor boss-fight objective. "
    "Consider collection, support, Prestige spending, routes, and "
    "stopping a pending rival claim. If you are the final rival "
    "to respond, unrelated action can hand the claimant victory. "
    "Only public evidence is supplied. Exact contest odds describe "
    "one roll, not eventual win probabilities. Return one supplied action id.")


class OpenAIDecisions:
    """One seat backed by client.decisions.create; no silent fallbacks."""

    def __init__(self, client, model, name="openai", pricing=None,
                 per_request_usd=None, timeout_s=TIMEOUT_S):
        self.name = name
        self.client = client
        self.model = model
        self.pricing = pricing or PRICING
        # Flat fee for each request, in USD, keyed like pricing.
        self.per_request_usd = per_request_usd or {}
        self.timeout_s = timeout_s

    def build_request(self, view: TurnView) -> dict:
        if view.projection.get("gameplay_mode") == "succession-v1":
            evidence = dict(view.projection)
            evidence["candidate_features"] = [
                {key: c[key] for key in (
                    "action_id", "kind", "destination", "features")}
                for c in view.candidates]
            instructions = SUCCESSION_INSTRUCTIONS
        else:
            evidence = view.projection
            instructions = PROJECTION_INSTRUCTIONS
        return {
            "model": self.model,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": INTRO_TEXT},
                    {"type": "input_json", "data": evidence},
                ],
            }],
            "questions": [{
                "type": "choice",
                "name": QUESTION_NAME,
                "instructions": instructions,
                "choices": [
                    {"value": c["action_id"], "description": c["description"]}
                    for c in view.candidates
                ],
            }],
        }

    def rate(self) -> float:
        return self.pricing.get(self.model, self.pricing.get("*", 0.0))

    def request_fee(self) -> float:
        return self.per_request_usd.get(self.model, 0.0)

    def decide(self, view: TurnView) -> Decision:
        request = self.build_request(view)
        client = self.client
        if hasattr(client, "with_options"):
            client = client.with_options(timeout=self.timeout_s,
                                         max_retries=0)
        exchange = {"request": request, "response": None}
        started = time.monotonic()
        try:
            response = client.decisions.create(**request)
        except Exception as exc:
            raise TransportError(
                f"{self.name} decisions call failed: {exc}",
                exchange=exchange) from None
        latency_ms = round((time.monotonic() - started) * 1000, 1)
        exchange["response"] = {"status_code": None, "body": _dump(response)}
        try:
            decision = self._parse(response, view.legal_ids, latency_ms)
        except ProviderError as exc:
            exc.exchange = exchange
            raise
        return dataclasses.replace(decision, exchange=exchange)

    def _parse(self, response, legal_ids, latency_ms) -> Decision:
        answers = getattr(response, "answers", None) or []
        if not answers:
            raise InvalidAnswerError("openai returned an empty answers array")
        answer = answers[0]
        answer_type = getattr(answer, "type", None)
        if answer_type == "refusal":
            raise RefusalError("openai refused best_action")
        if answer_type != "choice":
            raise InvalidAnswerError(
                f"openai answer type {answer_type!r} is not choice")
        name = getattr(answer, "name", None)
        if name is not None and name != QUESTION_NAME:
            raise InvalidAnswerError(
                f"openai answer name {name!r} is unexpected")
        choice = getattr(answer, "choice", None)
        if not isinstance(choice, str) or choice not in legal_ids:
            raise InvalidAnswerError(
                f"openai choice {choice!r} is not a legal action id")
        usage = _parse_usage(getattr(response, "usage", None))
        request_id = getattr(response, "id", None)
        if request_id is not None:
            usage.setdefault("request_id", request_id)
        input_tokens = usage.get("input_tokens")
        cost = 0.0
        if isinstance(input_tokens, (int, float)) and input_tokens > 0:
            cost = input_tokens / 1_000_000 * self.rate()
        cost = round(cost + self.request_fee(), 8)
        confidence = getattr(answer, "confidence", None)
        if isinstance(confidence, bool) \
                or not isinstance(confidence, (int, float)) \
                or not math.isfinite(confidence) \
                or not 0.0 <= confidence <= 1.0:
            confidence = None
        return Decision(
            action_id=choice,
            confidence=confidence,
            probabilities=_parse_probabilities(
                getattr(answer, "probabilities", None), legal_ids),
            latency_ms=latency_ms,
            usage=usage or None,
            cost_usd=cost,
            reason=f"{self.name}_decisions_choice")


def _dump(value):
    """Turn an SDK response into plain JSON data for the match log."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _dump(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return {k: _dump(v) for k, v in vars(value).items()
                if not k.startswith("_")}
    return str(value)


def _parse_probabilities(raw, legal_ids):
    """OpenAI returns an array of entries; keep it only when fully valid."""
    if not raw:
        return None
    seen = {}
    for entry in raw:
        value = entry.get("value") if isinstance(entry, dict) \
            else getattr(entry, "value", None)
        probability = entry.get("probability") if isinstance(entry, dict) \
            else getattr(entry, "probability", None)
        if not isinstance(value, str) or value in seen:
            return None
        if isinstance(probability, bool) \
                or not isinstance(probability, (int, float)) \
                or not math.isfinite(probability) \
                or not 0.0 <= probability <= 1.0:
            return None
        seen[value] = float(probability)
    if set(seen) - legal_ids:
        return None
    return seen


def _parse_usage(usage) -> dict:
    if usage is None:
        return {}
    details = getattr(usage, "input_tokens_details", None)

    def detail(name):
        return getattr(details, name, None) if details is not None else None

    parsed = {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "cached_tokens": detail("cached_tokens"),
        "cache_write_tokens": detail("cache_write_tokens"),
    }
    return {key: value for key, value in parsed.items() if value is not None}


def build(model: str | None = None, client=None) -> OpenAIDecisions:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ProviderError(
            "openai package not installed; "
            "run `uv sync --extra decisions`") from exc
    if not os.environ.get("OPENAI_API_KEY"):
        raise ProviderError("openai needs OPENAI_API_KEY in the environment")
    return OpenAIDecisions(client if client is not None else OpenAI(),
                           model or DEFAULT_MODEL)
