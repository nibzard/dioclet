# ABOUTME: Shared System One client used by the Jev, Clef, and Perplexity seats.
# ABOUTME: One choice question per turn; HTTP and answer errors map to the contract.

import dataclasses
import math
import time

import httpx

from arena.providers import (Decision, InvalidAnswerError, ProviderError,
                             TransportError, TurnView)

QUESTION_NAME = "best_action"
TRANSIENT_STATUS = frozenset({408, 429, 529})

INTRO_TEXT = ("Select the best legal board-game move given this public "
              "state. Exact single-roll odds in the features are exact; "
              "any longer-horizon judgement is yours.")
CLASSIC_INSTRUCTIONS = (
    "You are one player in a four-player competitive board game. "
    "Pick the option most likely to improve your eventual chance to be "
    "first to defeat the Emperor. Prefer an immediate legal win over "
    "unrelated actions; consider progress, opponents, and resource tempo. "
    "Use only the supplied public information and action descriptions. "
    "Return one of the supplied option ids.")
SUCCESSION_INSTRUCTIONS = (
    "You are a player in a four-player imperial succession game. "
    "Choose the legal action that maximizes your eventual chance "
    "of being acclaimed emperor. Use the supplied objective and "
    "response-window rules, not an Emperor boss-fight objective. "
    "Consider collection, support, Prestige spending, routes, and "
    "stopping a pending rival claim. If you are the final rival "
    "to respond, unrelated action can hand the claimant victory. "
    "Only public evidence is supplied. Exact contest odds describe "
    "one roll, not eventual win probabilities. Return one of the "
    "supplied option ids.")


class SystemOneProvider:
    """One seat backed by any System One compatible endpoint."""

    def __init__(self, name, base_url, headers, model, pricing, timeout_s,
                 http_client=None):
        self.name = name
        self.base_url = base_url
        self.headers = headers
        self.model = model
        self.pricing = pricing
        self.timeout_s = timeout_s
        self._client = http_client

    def build_request(self, view: TurnView) -> dict:
        if view.projection.get("gameplay_mode") == "succession-v1":
            instructions = SUCCESSION_INSTRUCTIONS
        else:
            instructions = CLASSIC_INSTRUCTIONS
        return {
            "model": self.model,
            "state": view.projection,
            "questions": {
                QUESTION_NAME: {
                    "type": "choice",
                    "instructions": f"{INTRO_TEXT} {instructions}",
                    "criteria": {c["action_id"]: c["description"]
                                 for c in view.candidates},
                }
            },
        }

    def rate(self) -> float:
        return self.pricing.get(self.model, self.pricing["*"])

    def decide(self, view: TurnView) -> Decision:
        request = self.build_request(view)
        exchange = {"request": request, "response": None}
        started = time.monotonic()
        try:
            response = self._send(request)
            latency_ms = round((time.monotonic() - started) * 1000, 1)
            exchange["response"] = _recorded(response)
            payload = self._json(response)
            decision = self._parse(payload, view.legal_ids, latency_ms,
                                   self._extra_usage(response))
        except ProviderError as exc:
            if exc.exchange is None:
                exc.exchange = exchange
            raise
        return dataclasses.replace(decision, exchange=exchange)

    def _send(self, request) -> httpx.Response:
        client = self._client if self._client is not None else httpx.Client()
        close = self._client is None
        try:
            try:
                response = client.post(self.base_url, json=request,
                                       headers=self.headers,
                                       timeout=self.timeout_s)
            except httpx.TimeoutException:
                raise TransportError(
                    f"{self.name} request timed out after "
                    f"{self.timeout_s}s") from None
            except httpx.HTTPError as exc:
                raise TransportError(
                    f"{self.name} transport failure: {exc}") from None
        finally:
            if close:
                client.close()
        if 200 <= response.status_code < 300:
            return response
        detail = (f"{self.name} HTTP {response.status_code}: "
                  f"{response.text[:200]}")
        exchange = {"request": request, "response": _recorded(response)}
        if response.status_code in TRANSIENT_STATUS \
                or response.status_code >= 500:
            raise TransportError(detail, exchange=exchange)
        raise ProviderError(detail, exchange=exchange)

    def _json(self, response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidAnswerError(
                f"{self.name} response is not JSON: {exc}") from None
        if not isinstance(payload, dict):
            raise InvalidAnswerError(f"{self.name} response is not an object")
        return payload

    def _extra_usage(self, response) -> dict:
        return {}

    def _parse(self, payload, legal_ids, latency_ms, extra_usage) -> Decision:
        answer = (payload.get("answers") or {}).get(QUESTION_NAME)
        if not isinstance(answer, dict):
            raise InvalidAnswerError(
                f"{self.name} response has no answers.{QUESTION_NAME}")
        if answer.get("type") != "choice":
            raise InvalidAnswerError(
                f"{self.name} answer type {answer.get('type')!r} is not "
                f"choice")
        choice = answer.get("choice")
        if choice not in legal_ids:
            raise InvalidAnswerError(
                f"{self.name} choice {choice!r} is not a legal action id")
        usage = dict(extra_usage)
        raw_usage = payload.get("usage") or {}
        for key in ("input_tokens", "output_tokens"):
            if key in raw_usage:
                usage[key] = raw_usage[key]
        input_tokens = raw_usage.get("input_tokens")
        cost = 0.0
        if isinstance(input_tokens, (int, float)) and input_tokens > 0:
            cost = round(input_tokens / 1_000_000 * self.rate(), 8)
        confidence = answer.get("confidence")
        return Decision(
            action_id=choice,
            confidence=confidence if _unit(confidence) else None,
            probabilities=_validated_probabilities(
                answer.get("probabilities"), legal_ids),
            latency_ms=latency_ms,
            usage=usage or None,
            cost_usd=cost,
            reason=f"{self.name}_choice")


def _recorded(response) -> dict:
    """The status and full body, JSON when it parses; never headers."""
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return {"status_code": response.status_code, "body": body}


def _unit(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) \
        and math.isfinite(value) and 0.0 <= value <= 1.0


def _validated_probabilities(raw, legal_ids):
    """Keep the distribution only when it is complete and well formed."""
    if not isinstance(raw, dict) or not raw:
        return None
    for value, probability in raw.items():
        if value not in legal_ids:
            return None
        if isinstance(probability, bool) \
                or not isinstance(probability, (int, float)) \
                or not math.isfinite(probability) \
                or not 0.0 <= probability <= 1.0:
            return None
    return {value: float(probability) for value, probability in raw.items()}
