"""Single-writer AI game driver (V0.4).

Runs one game mixing built-in bots, the deterministic `tactical`
policy, and `decisions` policies backed by mock/playback/live
providers. The engine stays authoritative: every applied action comes
from the engine's own `legal_actions`, and provider metadata lives in
a separate `decisions.jsonl`, never inside the deterministic state.

Budget exhaustion or an unrecovered provider failure stops the game
cleanly and marks it incomplete — never a draw, never a silent
fallback counted as a model result. In the decision counters,
`attempted` counts turns that reached the provider boundary including
the one blocked by a budget cap; `budget.calls` counts requests
actually sent.
"""

import hashlib
import json
import os
import random

import candidate_actions
import decisions_policy
import engine
import policies
import tactical_policy

SEATS = ("P0", "P1", "P2", "P3")
DRIVER_VERSION = "ai-driver-0.4"


class GameIncomplete(Exception):
    """Raised when a game stops before a terminal engine result."""


def _hash_json(payload):
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_decisions_config(path="decisions_config.json"):
    with open(path, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    required = {"provider", "model", "candidate_cap", "prompt_version",
                "selection_mode", "max_retries", "timeout_seconds",
                "fallback_on_live_error", "persona"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"decisions config missing keys: {sorted(missing)}")
    if config["selection_mode"] not in ("top", "sample"):
        raise ValueError("selection_mode must be top or sample")
    if config["provider"] not in ("mock", "playback", "live"):
        raise ValueError("provider must be mock, playback, or live")
    if "pricing" in config:
        decisions_policy.set_pricing(config["pricing"])
    return config


def run_ai_game(rules, seed, game_id, players_by_seat, out_dir,
                provider="mock", config=None, live_client=None,
                max_decisions_calls=0, max_cost_usd=0.0,
                max_input_tokens=0, wall_clock_seconds=0.0,
                resume=False, progress=None):
    """Play one game; returns a summary dict.

    `players_by_seat` maps P0..P3 to policy names among the built-in
    bots, `tactical`, and `decisions`. Live providers require the
    caller to pass explicit budget caps (>0) — enforced before every
    call.
    """
    config = config or {"model": decisions_policy.DEFAULT_MODEL,
                        "candidate_cap": 16, "prompt_version": "v04-1",
                        "selection_mode": "top", "max_retries": 1,
                        "timeout_seconds": 20,
                        "fallback_on_live_error": False,
                        "persona": "win_focused"}
    if provider == "live" and not (max_decisions_calls or max_cost_usd):
        raise ValueError("live provider requires an explicit budget cap")

    # Run-dir collision handling: refuse unless resuming.
    if os.path.isdir(out_dir) and os.listdir(out_dir) and not resume:
        raise FileExistsError(
            f"{out_dir} exists and is not empty; pass resume=True to "
            f"continue it")
    os.makedirs(out_dir, exist_ok=True)

    decisions_path = os.path.join(out_dir, "decisions.jsonl")
    if resume and os.path.exists(os.path.join(out_dir, "state.json")):
        state = engine.load_run(out_dir)
        applied_turn_ids = {r["turn_id"] for r in state["events"]}
    else:
        state = engine.new_game(rules, seed, game_id, players_by_seat)
        applied_turn_ids = set()
        engine.write_run(out_dir, state)
        engine.reset_events_file(out_dir, state)
        with open(decisions_path, "w", encoding="utf-8") as fh:
            fh.write("")  # truncate: fresh game log

    budget = decisions_policy.Budget(
        max_calls=max_decisions_calls, max_cost_usd=max_cost_usd,
        max_input_tokens=max_input_tokens,
        wall_clock_seconds=wall_clock_seconds)
    playback_records = _load_playback(decisions_path, provider,
                                      applied_turn_ids)
    provider_impl = decisions_policy.make_provider(
        provider, config, playback_records=playback_records,
        live_client=live_client)
    policy_rng = random.Random(f"decisions-policy:{game_id}:{seed}")

    decision_count = {"attempted": 0, "applied": 0, "single_action": 0,
                      "refused": 0, "invalid": 0, "error": 0}
    incomplete_reason = None

    def log_decision(record):
        with open(decisions_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    while not engine.is_finished(state):
        active = state["active_player"]
        obs = engine.observe(state, active)
        policy_name = players_by_seat[active]

        if policy_name == "decisions":
            projection = candidate_actions.project_observation(obs, rules)
            candidates, excluded = candidate_actions.build_candidates(
                obs, rules, cap=config.get("candidate_cap", 16))
            legal_ids = {a["action_id"] for a in obs["legal_actions"]}
            assert {c["action_id"] for c in candidates} <= legal_ids
            audit = {
                "game_id": game_id, "turn_id": obs["turn_id"],
                "player": active, "policy": "decisions",
                "provider": provider,
                "observation_hash": candidate_actions.projection_hash(
                    projection),
                "projection_schema":
                    candidate_actions.PROJECTION_SCHEMA_VERSION,
                "legal_action_count": len(obs["legal_actions"]),
                "candidate_count": len(candidates),
                "candidates": [{"action_id": c["action_id"],
                                "kind": c["kind"],
                                "description": c["description"]}
                               for c in candidates],
                "excluded_count": len(excluded),
                "excluded": excluded,
                "model": config.get("model"),
                "prompt_version": config.get("prompt_version"),
                "config_hash": _hash_json(
                    {k: config.get(k) for k in sorted(config)
                     if k != "pricing"}),
            }
            if len(obs["legal_actions"]) == 1:
                # The choice API needs >= 2 options: no provider call.
                decision = decisions_policy.PlayerDecision(
                    action_id=obs["legal_actions"][0]["action_id"],
                    policy="decisions", reason="single_legal_action",
                    metadata={"provider": provider, "model": None,
                              "probabilities": None, "confidence": None,
                              "latency_ms": 0, "usage": None,
                              "estimated_cost_usd": 0.0, "error": None})
                selected_mode = "single"
                decision_count["single_action"] += 1
                decision_count["applied"] += 1
                action_id = decision.action_id
            else:
                decision_count["attempted"] += 1
                try:
                    decision = provider_impl.decide(
                        projection, candidates, config, budget)
                except decisions_policy.RefusalError as exc:
                    decision_count["refused"] += 1
                    incomplete_reason = f"refusal: {exc}"
                    break
                except decisions_policy.InvalidAnswerError as exc:
                    decision_count["invalid"] += 1
                    incomplete_reason = f"invalid answer: {exc}"
                    break
                except decisions_policy.BudgetExceededError as exc:
                    incomplete_reason = f"budget: {exc}"
                    break
                except decisions_policy.LiveUnavailableError as exc:
                    decision_count["error"] += 1
                    incomplete_reason = f"provider error: {exc}"
                    break
                if decision.action_id not in legal_ids:
                    decision_count["invalid"] += 1
                    incomplete_reason = "illegal action from provider"
                    break
                action_id, selected_mode = decisions_policy.select_action(
                    decision, config, rng=policy_rng)
                if action_id not in legal_ids:
                    decision_count["invalid"] += 1
                    incomplete_reason = "illegal action from selection"
                    break
                decision_count["applied"] += 1
            audit["chosen_action"] = decision.action_id
            audit["reason_code"] = decision.reason
            audit["metadata"] = decision.metadata
            audit["selected_mode"] = selected_mode
            reason = decision.reason
        elif policy_name == "tactical":
            action_id, reason = tactical_policy.choose(obs, rules)
        else:
            action_id, reason = policies.act(policy_name, obs, policy_rng)

        record = engine.apply_action(state, active, obs["turn_id"],
                                     action_id, reason)
        if policy_name == "decisions":
            audit["applied_action"] = record["action_id"]
            audit["engine_event_seq"] = record["event_seq"]
            log_decision(audit)
        engine.write_run(out_dir, state)
        if progress:
            progress(state, record)

    summary = {
        "game_id": game_id, "seed": seed,
        "rules_hash": engine.rules_hash(rules),
        "engine_version": engine.ENGINE_VERSION,
        "driver_version": DRIVER_VERSION,
        "provider": provider, "model": config.get("model"),
        "players": dict(players_by_seat),
        "decisions": decision_count,
        "budget": {"calls": budget.calls,
                   "input_tokens": budget.input_tokens_seen,
                   "estimated_cost_usd": round(
                       budget.spent_estimate_usd, 6)},
        "incomplete_reason": incomplete_reason,
        "status": "in_progress", "winner": None,
    }
    if incomplete_reason is None:
        engine.check_invariants(state)
        res = engine.result(state)
        engine.write_run(out_dir, state)
        summary.update({
            "status": "finished",
            "winner": res["winner"], "outcome": res["outcome"],
            "total_turns": res["total_turns"],
            "total_rounds": res["total_rounds"],
            "result": res,
        })
    else:
        _atomic_json(os.path.join(out_dir, "incomplete.json"), summary)
    return summary


def _load_playback(decisions_path, provider, applied_turn_ids):
    if provider != "playback":
        return {}
    records = {}
    if os.path.exists(decisions_path):
        with open(decisions_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("applied_action"):
                    records[(rec["game_id"], rec["turn_id"],
                             rec["player"])] = rec["applied_action"]
    return records


def _atomic_json(path, payload):
    engine._atomic_write_json(path, payload)
