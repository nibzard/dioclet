"""OpenAI Decisions provider boundary (V0.4).

Three providers behind one interface:

- ``mock``     deterministic local ranking, zero network, pipeline tests;
- ``playback`` replays recorded choices from a ``decisions.jsonl``;
- ``live``     official SDK ``client.decisions.create`` on gpt-6-luna.

The live path is strictly typed and validated: a refusal, a bad answer
type, or an action outside the engine's current legal set never
reaches ``engine.apply_action``. The optional ``openai`` package is
imported lazily so the offline engine works without it.
"""

import json
import math
import time
from dataclasses import dataclass, field

DEFAULT_MODEL = "gpt-6-luna"
QUESTION_NAME = "best_action"
PROJECTION_INSTRUCTIONS = (
    "You are one player in a four-player competitive board game. "
    "Pick the option most likely to improve your eventual chance to be "
    "first to defeat the Emperor. Prefer an immediate legal win over "
    "unrelated actions; consider progress, opponents, and resource tempo. "
    "Use only the supplied public information and action descriptions."
)
INTRO_TEXT = ("Select the best legal board-game move given this public "
              "state. Exact single-roll odds in the features are exact; "
              "any longer-horizon judgement is yours.")

NORMALIZATION_TOLERANCE = 0.02


class DecisionsError(Exception):
    """Base class for decision failures (never silently swallowed)."""


class RefusalError(DecisionsError):
    pass


class InvalidAnswerError(DecisionsError):
    pass


class BudgetExceededError(DecisionsError):
    pass


class LiveUnavailableError(DecisionsError):
    pass


@dataclass(frozen=True)
class PlayerDecision:
    action_id: str
    policy: str
    reason: str
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

class Budget:
    """Hard caps enforced before every live call."""

    def __init__(self, max_calls=0, max_cost_usd=0.0, max_input_tokens=0,
                 wall_clock_seconds=0.0):
        self.max_calls = max_calls
        self.max_cost_usd = max_cost_usd
        self.max_input_tokens = max_input_tokens
        self.wall_clock_seconds = wall_clock_seconds
        self.calls = 0
        self.spent_estimate_usd = 0.0
        self.input_tokens_seen = 0
        self.started = time.monotonic()

    def check_before(self, estimated_input_tokens):
        if self.max_calls and self.calls >= self.max_calls:
            raise BudgetExceededError(
                f"call cap reached ({self.calls}/{self.max_calls})")
        est_cost = self._cost(estimated_input_tokens)
        if self.max_cost_usd and \
                self.spent_estimate_usd + est_cost > self.max_cost_usd:
            raise BudgetExceededError(
                f"cost cap would be exceeded "
                f"({self.spent_estimate_usd:.4f} + ~{est_cost:.4f} > "
                f"{self.max_cost_usd:.4f} USD)")
        if self.max_input_tokens and \
                self.input_tokens_seen + estimated_input_tokens > \
                self.max_input_tokens:
            raise BudgetExceededError("input-token cap would be exceeded")
        if self.wall_clock_seconds and \
                time.monotonic() - self.started > self.wall_clock_seconds:
            raise BudgetExceededError("wall-clock timeout")

    def record(self, input_tokens, cost_estimate_usd):
        self.calls += 1
        self.input_tokens_seen += input_tokens
        self.spent_estimate_usd += cost_estimate_usd

    def _cost(self, tokens):
        rate = PRICING.get("uncached_input_usd_per_mtok", 0.10)
        # Conservative: charge every input token at the uncached rate.
        return tokens * rate / 1_000_000


# Versioned pricing (see FINDINGS_V04 / decisions_config.json).
PRICING = {"uncached_input_usd_per_mtok": 0.10}


def set_pricing(pricing_config):
    """Replace the versioned pricing table from decisions_config.json."""
    global PRICING
    PRICING = {
        "uncached_input_usd_per_mtok": float(
            pricing_config.get("uncached_input_usd_per_mtok", 0.10))
    }


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def _rank_key(c):
    """Mock ranking: objective priority, then exact odds, then ids."""
    priority = {"attack_emperor": 0, "attempt_seal": 1, "claim_checkpoint": 2,
                "explore": 3, "guard_post": 4, "duel": 5, "move": 6}
    feats = c["features"]
    odds = max(
        feats.get("hit_probability_exact", 0),
        feats.get("seal_success_probability_exact", 0),
        feats.get("duel_win_probability_exact", 0),
        feats.get("glory_probability_exact", 0),
    )
    winning = 1 if feats.get("would_win_game_if_hit") else 0
    return (-winning, priority.get(c["kind"], 9), -odds,
            c["action_id"])


class MockProvider:
    """Deterministic offline ranking; never a network call."""

    name = "mock"

    def decide(self, projection, candidates, config, budget=None):
        best = min(candidates, key=_rank_key)
        return PlayerDecision(
            action_id=best["action_id"], policy="decisions",
            reason="mock_ranking",
            metadata={"provider": "mock", "model": None,
                      "probabilities": None, "confidence": None,
                      "latency_ms": 0, "usage": None,
                      "estimated_cost_usd": 0.0, "error": None})


class PlaybackProvider:
    """Replays a recorded choice by (game_id, turn_id, player)."""

    name = "playback"

    def __init__(self, records):
        # records: {(game_id, turn_id, player): chosen_action_id}
        self.records = records

    def decide(self, projection, candidates, config, budget=None):
        key = (projection["game_id"], projection["turn"]["id"],
               projection["turn"]["player"])
        action_id = self.records.get(key)
        if action_id not in {c["action_id"] for c in candidates}:
            raise InvalidAnswerError(
                f"playback record for {key} missing or illegal")
        return PlayerDecision(
            action_id=action_id, policy="decisions",
            reason="playback_record",
            metadata={"provider": "playback", "model": None,
                      "probabilities": None, "confidence": None,
                      "latency_ms": 0, "usage": None,
                      "estimated_cost_usd": 0.0, "error": None})


class LiveProvider:
    """Official OpenAI Decisions call via client.decisions.create."""

    name = "live"

    def __init__(self, client=None, model=DEFAULT_MODEL):
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LiveUnavailableError(
                    "openai package not installed; see "
                    "requirements-decisions.txt") from exc
            client = OpenAI()
        self.client = client
        self.model = model

    def build_request(self, projection, candidates):
        return {
            "model": self.model,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": INTRO_TEXT},
                    {"type": "input_json", "data": projection},
                ],
            }],
            "questions": [{
                "type": "choice",
                "name": QUESTION_NAME,
                "instructions": PROJECTION_INSTRUCTIONS,
                "choices": [
                    {"value": c["action_id"],
                     "description": c["description"]}
                    for c in candidates
                ],
            }],
        }

    def estimate_input_tokens(self, request):
        blob = json.dumps(request, sort_keys=True)
        return max(1, len(blob) // 4)  # ~4 chars per token, conservative

    def decide(self, projection, candidates, config, budget=None):
        legal_ids = {c["action_id"] for c in candidates}
        request = self.build_request(projection, candidates)
        est_tokens = self.estimate_input_tokens(request)
        if budget is not None:
            budget.check_before(est_tokens)
        max_retries = int(config.get("max_retries", 1))
        timeout = float(config.get("timeout_seconds", 20))
        last_error = None
        for attempt in range(max_retries + 1):
            started = time.monotonic()
            try:
                response = self._call(request, timeout)
                latency_ms = round((time.monotonic() - started) * 1000, 1)
                break
            except DecisionsError:
                raise
            except Exception as exc:  # transient SDK/transport faults
                last_error = str(exc)
                if attempt >= max_retries:
                    raise LiveUnavailableError(
                        f"decisions call failed after "
                        f"{max_retries + 1} attempt(s): {last_error}") \
                        from None
        decision = self._parse(response, latency_ms, legal_ids, est_tokens)
        if budget is not None:
            usage = decision.metadata.get("usage") or {}
            budget.record(usage.get("input_tokens") or est_tokens,
                          decision.metadata.get("estimated_cost_usd", 0.0))
        return decision

    def _call(self, request, timeout):
        return self.client.decisions.create(**request)

    def _parse(self, response, latency_ms, legal_ids, est_tokens):
        answers = getattr(response, "answers", None) or []
        if not answers:
            raise InvalidAnswerError("empty answers array")
        answer = answers[0]
        answer_type = getattr(answer, "type", None)
        if answer_type == "refusal":
            raise RefusalError("Decisions refused best_action")
        if answer_type != "choice":
            raise InvalidAnswerError(
                f"unexpected answer type {answer_type!r}")
        name = getattr(answer, "name", None)
        if name is not None and name != QUESTION_NAME:
            raise InvalidAnswerError(
                f"unexpected answer name {name!r}")
        choice = getattr(answer, "choice", None)
        if not isinstance(choice, str) or choice not in legal_ids:
            raise InvalidAnswerError(
                f"choice {choice!r} is not a current candidate action_id")

        probabilities, prob_flags = _parse_probabilities(
            getattr(answer, "probabilities", None), legal_ids)
        confidence = getattr(answer, "confidence", None)
        if confidence is not None:
            if not _finite_unit(confidence):
                raise InvalidAnswerError(
                    f"confidence {confidence!r} outside [0,1]")

        usage = _parse_usage(getattr(response, "usage", None))
        input_tokens = usage.get("input_tokens") or est_tokens
        cost = input_tokens * PRICING["uncached_input_usd_per_mtok"] \
            / 1_000_000
        return PlayerDecision(
            action_id=choice,
            policy="decisions",
            reason="openai_decisions_choice",
            metadata={
                "provider": "live",
                "model": getattr(response, "model", self.model),
                "probabilities": probabilities,
                "probability_flags": prob_flags,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "usage": usage,
                "request_id": getattr(response, "id", None),
                "estimated_cost_usd": round(cost, 6),
                "error": None,
            })


def _finite_unit(value):
    return isinstance(value, (int, float)) and math.isfinite(value) \
        and 0.0 <= value <= 1.0


def _entry_field(entry, name):
    if isinstance(entry, dict):
        return entry.get(name)
    return getattr(entry, name, None)


def _parse_probabilities(raw, legal_ids):
    """Validate the probabilities array; flag, never renormalize."""
    if not raw:
        return None, ["absent"]
    seen = {}
    flags = []
    for entry in raw:
        value = _entry_field(entry, "value")
        probability = _entry_field(entry, "probability")
        if not isinstance(value, str) or value in seen:
            flags.append(f"duplicate_or_nonstring_value:{value!r}")
            continue
        if not _finite_unit(probability):
            flags.append(f"invalid_probability:{probability!r}")
            continue
        seen[value] = probability
    unknown = sorted(set(seen) - legal_ids)
    if unknown:
        flags.append(f"unknown_values:{unknown}")
    covered = sorted(legal_ids & set(seen))
    if covered == sorted(legal_ids):
        total = sum(seen[v] for v in covered)
        if abs(total - 1.0) > NORMALIZATION_TOLERANCE:
            flags.append(f"normalization_sum={total:.4f}")
    else:
        flags.append(f"partial_coverage:{len(covered)}/{len(legal_ids)}")
    return [{"value": v, "probability": seen[v]} for v in sorted(seen)], flags


def _parse_usage(usage):
    if usage is None:
        return None
    details = getattr(usage, "input_tokens_details", None)

    def d(name):
        return getattr(details, name, None) if details is not None else None

    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "cached_tokens": d("cached_tokens"),
        "cache_write_tokens": d("cache_write_tokens"),
    }


def make_provider(name, config, playback_records=None, live_client=None):
    if name == "mock":
        return MockProvider()
    if name == "playback":
        return PlaybackProvider(playback_records or {})
    if name == "live":
        return LiveProvider(client=live_client,
                            model=config.get("model", DEFAULT_MODEL))
    raise ValueError(f"unknown provider {name!r}")


def select_action(decision, config, rng=None):
    """Apply the configured selection mode to a live decision."""
    mode = config.get("selection_mode", "top")
    if mode == "top" or decision.metadata.get("provider") != "live":
        return decision.action_id, mode
    probs = decision.metadata.get("probabilities") or []
    flags = decision.metadata.get("probability_flags") or []
    if not probs or flags or rng is None:
        # Sample only with a complete, valid distribution (spec §6).
        return decision.action_id, "top_fallback"
    import random as _random
    values = [p["value"] for p in probs]
    weights = [p["probability"] for p in probs]
    return rng.choices(values, weights=weights, k=1)[0], mode
