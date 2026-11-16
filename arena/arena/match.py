# ABOUTME: Match configuration, budget, and the single-game run loop for Arena.
# ABOUTME: The loop writes match.jsonl and the engine run directory as the game plays.

import json
import os
import random
import time
from dataclasses import dataclass, field

import engine

from arena import engine_adapter as adapter
from arena.providers import (Decision, ProviderError, REMOTE_PROVIDERS,
                             REQUIRED_ENV, TurnView, build_provider, local)
from arena.rules_loader import load_rules_strict

ARENA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEATS = ("P0", "P1", "P2", "P3")
# Version of the match.jsonl record shapes. Change it when a shape changes.
LOG_SCHEMA = "arena-match-v1"


class MatchConfigError(Exception):
    """A match configuration breaks the Arena match contract."""


class BudgetExceeded(Exception):
    """The match budget stopped the game before a provider call."""


@dataclass
class SeatConfig:
    seat: str
    provider: str
    model: str | None = None


@dataclass
class Budget:
    max_calls: int = 0
    max_usd: float = 0.0
    calls: int = 0
    spent_usd: float = 0.0

    def guard(self):
        if self.max_calls and self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"call cap reached ({self.calls}/{self.max_calls} calls)")
        if self.max_usd and self.spent_usd >= self.max_usd:
            raise BudgetExceeded(
                f"cost cap reached (${self.spent_usd:.4f} of "
                f"${self.max_usd:.2f})")


@dataclass
class MatchConfig:
    rules_path: str
    rules: dict
    rules_hash: str
    seed: int
    seats: list
    budget: Budget = field(default_factory=Budget)


def _resolve_rules_path(path):
    if os.path.isabs(path):
        return path
    return os.path.join(ARENA_DIR, path)


def make_config(rules_path, seed, seat_specs, budget_spec=None):
    """Validate a parsed match configuration and load its rules."""
    if not isinstance(rules_path, str) or not rules_path:
        raise MatchConfigError("'rules' must be a path string")
    if type(seed) is not int:
        raise MatchConfigError("'seed' must be an integer")
    if not isinstance(seat_specs, list) or len(seat_specs) != 4:
        raise MatchConfigError(
            f"'seats' must list exactly 4 seats (the rules fix 4 players), "
            f"found {len(seat_specs) if isinstance(seat_specs, list) else 'not a list'}")
    known = set(local.NAMES) | set(REMOTE_PROVIDERS)
    seats = []
    for i, spec in enumerate(seat_specs):
        if not isinstance(spec, dict):
            raise MatchConfigError(f"seat {SEATS[i]} must be an object")
        unknown = sorted(set(spec) - {"provider", "model"})
        if unknown:
            raise MatchConfigError(
                f"unknown key '{unknown[0]}' in seat {SEATS[i]} "
                f"(allowed keys: provider, model)")
        if "provider" not in spec:
            raise MatchConfigError(f"seat {SEATS[i]} is missing 'provider'")
        provider = spec["provider"]
        if provider not in known:
            raise MatchConfigError(
                f"seat {SEATS[i]} has unknown provider {provider!r}; "
                f"expected one of {sorted(known)}")
        model = spec.get("model")
        if model is not None and not isinstance(model, str):
            raise MatchConfigError(f"seat {SEATS[i]} model must be a string")
        if provider in REMOTE_PROVIDERS:
            missing = [var for var in REQUIRED_ENV[provider]
                       if not os.environ.get(var)]
            if missing:
                raise MatchConfigError(
                    f"seat {SEATS[i]} uses provider {provider!r} but the "
                    f"environment lacks {', '.join(missing)}")
        seats.append(SeatConfig(seat=SEATS[i], provider=provider, model=model))
    budget = Budget()
    if budget_spec is not None:
        if not isinstance(budget_spec, dict):
            raise MatchConfigError("'budget' must be an object")
        unknown = sorted(set(budget_spec) - {"max_calls", "max_usd"})
        if unknown:
            raise MatchConfigError(
                f"unknown budget key '{unknown[0]}' "
                f"(allowed keys: max_calls, max_usd)")
        max_calls = budget_spec.get("max_calls", 0)
        max_usd = budget_spec.get("max_usd", 0.0)
        if type(max_calls) is not int or max_calls < 0:
            raise MatchConfigError("budget.max_calls must be an integer >= 0")
        if isinstance(max_usd, bool) or not isinstance(max_usd, (int, float)) \
                or max_usd < 0:
            raise MatchConfigError("budget.max_usd must be a number >= 0")
        budget = Budget(max_calls=max_calls, max_usd=float(max_usd))
    resolved = _resolve_rules_path(rules_path)
    if not os.path.exists(resolved):
        raise MatchConfigError(f"rules file not found: {resolved}")
    try:
        rules = load_rules_strict(resolved)
    except Exception as exc:
        raise MatchConfigError(f"rules file rejected: {exc}") from None
    return MatchConfig(rules_path=rules_path, rules=rules,
                       rules_hash=engine.rules_hash(rules), seed=seed,
                       seats=seats, budget=budget)


def load_match(path):
    """Load and validate a match configuration file."""
    with open(path, "r", encoding="utf-8") as fh:
        try:
            doc = json.load(fh)
        except json.JSONDecodeError as exc:
            raise MatchConfigError(f"{path} is not valid JSON: {exc}") from None
    if not isinstance(doc, dict):
        raise MatchConfigError("the match file must be a JSON object")
    unknown = sorted(set(doc) - {"rules", "seed", "seats", "budget"})
    if unknown:
        raise MatchConfigError(
            f"unknown top-level key '{unknown[0]}' "
            f"(allowed keys: rules, seed, seats, budget)")
    for key in ("rules", "seed", "seats"):
        if key not in doc:
            raise MatchConfigError(f"missing key '{key}'")
    return make_config(doc["rules"], doc["seed"], doc["seats"],
                       doc.get("budget"))


def game_id(config):
    return f"arena-{config.seed}-{config.rules_hash[:8]}"


def make_run_dir(config, base=None):
    """Create arena/runs/<timestamp>-<game_id> and return its path."""
    base = base or os.path.join(ARENA_DIR, "runs")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    candidate = os.path.join(base, f"{stamp}-{game_id(config)}")
    suffix = 1
    while os.path.exists(candidate):
        suffix += 1
        candidate = os.path.join(
            base, f"{stamp}-{game_id(config)}-{suffix}")
    os.makedirs(candidate)
    return candidate


def _hook(hooks, name, *args):
    fn = getattr(hooks, name, None)
    if callable(fn):
        fn(*args)


class _StopMatch(Exception):
    """Internal: the match stops early; carries the failure record."""

    def __init__(self, seat, provider, error_class, error, turn_id, round_no,
                 attempts=()):
        super().__init__(f"{seat}: {error_class}: {error}")
        self.seat = seat
        self.provider = provider
        self.error_class = error_class
        self.error = error
        self.turn_id = turn_id
        self.round_no = round_no
        self.attempts = list(attempts)


def _action_summary(action, districts):
    kind = action.get("kind")
    dest = tuple(action.get("destination", ()))

    def at():
        return f"({dest[0]},{dest[1]})" if len(dest) == 2 else ""

    if kind == "move":
        return f"move {at()}".strip()
    if kind == "explore":
        return f"explore {districts.get(dest, at())}"
    if kind == "duel":
        text = f"duel {action.get('target', '?')}"
        if action.get("spend_prestige"):
            text += " +prestige"
        if action.get("spend_glory"):
            text += " +glory"
        return text
    if kind == "guard_post":
        return f"guard post {at()}".strip()
    if kind == "claim_checkpoint":
        return "claim checkpoint"
    if kind == "attempt_seal":
        text = f"seal at {at()}".strip()
        if action.get("spend_glory"):
            text += " (spend glory)"
        return text
    if kind == "attack_emperor":
        text = "attack emperor"
        if action.get("spend_glory"):
            text += " +glory"
        return text
    if kind == "proclaim":
        return "proclaim claim"
    if kind == "maintain_claim":
        return "maintain claim"
    if kind == "gain_support":
        return f"gain {action.get('faction', '?')} support"
    if kind == "search_site":
        return f"search {at()}".strip()
    return f"{kind} {at()}".strip()


def _default_provider_factory(config, gid):
    def build(seat_config):
        if seat_config.provider in REMOTE_PROVIDERS:
            return build_provider(seat_config.provider, seat_config.model)
        return local.build(
            seat_config.provider,
            rng=random.Random(f"arena:{gid}:{seat_config.seat}"))

    return build


def run_match(config, run_dir, hooks=None, provider_factory=None):
    """Play one match; return the summary dict (also the last match.jsonl line)."""
    gid = game_id(config)
    factory = provider_factory or _default_provider_factory(config, gid)
    providers = {sc.seat: factory(sc) for sc in config.seats}
    stats = {sc.seat: {"provider": sc.provider,
                       "model": providers[sc.seat].model,
                       "decisions": 0, "calls": 0, "cost_usd": 0.0,
                       "errors": []}
             for sc in config.seats}
    state = adapter.new_game(config.rules, config.seed, gid)
    engine_dir = os.path.join(run_dir, "engine")
    match_path = os.path.join(run_dir, "match.jsonl")
    os.makedirs(run_dir, exist_ok=True)

    def emit(payload):
        with open(match_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")

    emit({"type": "match_start", "schema": LOG_SCHEMA, "game_id": gid,
          "rules": {"path": config.rules_path, "rules_hash": config.rules_hash,
                    "doc": config.rules},
          "engine_version": state["engine_version"],
          "seed": config.seed,
          "seats": [{"seat": sc.seat, "provider": sc.provider,
                     "model": sc.model} for sc in config.seats],
          "budget": {"max_calls": config.budget.max_calls,
                     "max_usd": config.budget.max_usd},
          "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    engine.write_run(engine_dir, state)

    remote_seats = {sc.seat for sc in config.seats
                    if sc.provider in REMOTE_PROVIDERS}
    seq = 0
    failure = None
    interrupted = False
    view = None
    try:
        while not adapter.finished(state):
            obs = adapter.observe(state)
            view = TurnView(observation=obs,
                            projection=adapter.projection(obs, config.rules),
                            candidates=adapter.candidates(
                                obs, config.rules)[0],
                            rules=config.rules)
            _hook(hooks, "on_turn_start", state, view)
            seat = obs["active_player"]
            provider = providers[seat]
            legal = obs["legal_actions"]
            attempts = []
            if len(legal) == 1:
                decision = Decision(action_id=legal[0]["action_id"],
                                    reason="single_legal_action")
                attempt = 0
            else:
                is_remote = seat in remote_seats
                attempt = None
                error_class = error_text = None
                for try_index in (1, 2):
                    if is_remote:
                        try:
                            config.budget.guard()
                        except BudgetExceeded as exc:
                            raise _StopMatch(seat, provider, "BudgetExceeded",
                                             str(exc), obs["turn_id"],
                                             obs["round"], attempts) from None
                    try:
                        decision = provider.decide(view)
                    except ProviderError as exc:
                        error_class, error_text = type(exc).__name__, str(exc)
                        attempts.append({"attempt": try_index, "ok": False,
                                         "error_class": error_class,
                                         "error": error_text,
                                         "exchange": exc.exchange})
                        continue
                    if decision.action_id not in view.legal_ids:
                        error_class = "InvalidAnswerError"
                        error_text = (f"illegal action_id "
                                      f"{decision.action_id!r}")
                        attempts.append({"attempt": try_index, "ok": False,
                                         "error_class": error_class,
                                         "error": error_text,
                                         "exchange": decision.exchange})
                        continue
                    attempts.append({"attempt": try_index, "ok": True,
                                     "exchange": decision.exchange})
                    attempt = try_index
                    break
                if attempt is None:
                    raise _StopMatch(seat, provider, error_class,
                                     error_text or "provider failure",
                                     obs["turn_id"], obs["round"], attempts)
                if is_remote:
                    config.budget.calls += 1
                    config.budget.spent_usd += decision.cost_usd
            record = adapter.apply(state, decision.action_id,
                                   decision.reason)
            stats[seat]["decisions"] += 1
            if seat in remote_seats and attempt >= 1:
                stats[seat]["calls"] += 1
                stats[seat]["cost_usd"] += decision.cost_usd
            seq += 1
            districts = {tuple(cell): name for name, cell
                         in obs["board"].get("districts", {}).items()}
            p_chosen = None
            if decision.probabilities:
                p_chosen = decision.probabilities.get(decision.action_id)
            emit({"type": "decision", "seq": seq, "round": record["round"],
                  "turn_id": record["turn_id"], "phase": record["phase"],
                  "seat": seat, "provider": provider.name,
                  "model": provider.model,
                  "action_id": decision.action_id,
                  "action_kind": record["action"]["kind"],
                  "action_summary": _action_summary(record["action"],
                                                    districts),
                  "p_chosen": p_chosen,
                  "latency_ms": decision.latency_ms,
                  "cost_usd": decision.cost_usd, "usage": decision.usage,
                  "attempt": attempt, "reason": decision.reason,
                  "legal_count": len(legal),
                  "candidate_count": len(view.candidates),
                  "probabilities": decision.probabilities,
                  "confidence": decision.confidence,
                  "attempts": attempts,
                  "observation": obs, "projection": view.projection,
                  "candidates": view.candidates,
                  "play": record})
            _hook(hooks, "on_decision", seat, provider, decision, record,
                  attempt)
            engine.write_run(engine_dir, state)
    except _StopMatch as stop:
        failure = stop
        stats[stop.seat]["errors"].append(
            {"error_class": stop.error_class, "error": stop.error,
             "turn_id": stop.turn_id, "round": stop.round_no})
        emit({"type": "failure", "turn_id": stop.turn_id,
              "round": stop.round_no, "phase": state["phase"],
              "seat": stop.seat, "provider": stop.provider.name,
              "model": stop.provider.model,
              "error_class": stop.error_class, "error": stop.error,
              "attempts": stop.attempts,
              "observation": view.observation if view else None,
              "projection": view.projection if view else None,
              "candidates": view.candidates if view else None})
        engine.write_run(engine_dir, state)
    except KeyboardInterrupt:
        interrupted = True

    engine_result = None
    if interrupted:
        outcome, winner = "interrupted", None
        end_reason = "interrupted"
        total_turns = len(state["events"])
        total_rounds = state["round"]
        incomplete_reason = "interrupted by the user"
    elif failure is None:
        adapter.check_invariants(state)
        res = adapter.result(state)
        engine_result = res
        outcome, winner = res["outcome"], res["winner"]
        end_reason = res["end_reason"]
        total_turns = res["total_turns"]
        total_rounds = res["total_rounds"]
        incomplete_reason = None
    else:
        outcome, winner = "incomplete", None
        end_reason = "incomplete"
        total_turns = len(state["events"])
        total_rounds = state["round"]
        incomplete_reason = (f"{failure.seat} "
                             f"{failure.provider.name}/{failure.provider.model}: "
                             f"{failure.error_class}: {failure.error}")
    summary = {"type": "result", "outcome": outcome, "winner": winner,
               "end_reason": end_reason,
               "incomplete": failure is not None or interrupted,
               "incomplete_reason": incomplete_reason,
               "total_turns": total_turns, "total_rounds": total_rounds,
               "seats": {seat: {**stats[seat], "cost_usd": round(
                   stats[seat]["cost_usd"], 6)} for seat in SEATS},
               "run_dir": str(run_dir)}
    emit({**{k: v for k, v in summary.items() if k != "run_dir"},
          "engine_result": engine_result})
    engine.write_run(engine_dir, state)
    # An interrupt can stop an atomic write before its rename.
    for name in os.listdir(engine_dir):
        if name.endswith(".tmp"):
            os.remove(os.path.join(engine_dir, name))
    _hook(hooks, "on_result", summary)
    return summary
