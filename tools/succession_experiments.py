#!/usr/bin/env python3
"""Bounded V0.8 strategy experiments and alternative-play audits.

Offline policy probes and live Decisions games are labeled separately.
No scalar score claims to measure human fun. Live calls use the existing
AI driver and a shared budget; a ledger can carry the cap across cycles.
"""

import argparse
import copy
import fcntl
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_driver
import candidate_actions
import decisions_policy
import engine
import policies

IDS = ("P0", "P1", "P2", "P3")
PROFILES = ("collector", "early_support", "prestige_farmer", "counterleader")
POLICY_VERSION = "succession-probes-0.8.0"


def write_json(path, value):
    engine._atomic_write_json(str(path), value)


def append_json(path, value):
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


class LedgerBudget(decisions_policy.Budget):
    """One sequential caller owns a persistent experiment-wide cap.

    Reservations are persisted before requests. If a process stops after
    sending a request, its conservative reservation stays charged.
    """

    def __init__(self, path, max_calls, max_cost_usd, wall_clock_seconds=0):
        self.path = Path(path) if path else None
        self.lock = None
        super().__init__(max_calls=max_calls, max_cost_usd=max_cost_usd,
                         wall_clock_seconds=wall_clock_seconds)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.lock = self.path.with_suffix(self.path.suffix + ".lock").open("a+")
            try:
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.lock.close()
                raise ValueError("another live experiment owns the budget ledger") from None
            if self.path.exists():
                data = json.loads(self.path.read_text())
                if max_calls > data["max_calls"] or max_cost_usd > data["max_cost_usd"]:
                    self.close()
                    raise ValueError("cannot increase an existing ledger's caps; use an explicitly new authorized budget")
                self.max_calls = min(max_calls, data["max_calls"])
                self.max_cost_usd = min(max_cost_usd, data["max_cost_usd"])
                self.calls = data["calls"]
                self.input_tokens_seen = data["input_tokens"]
                self.spent_estimate_usd = data["estimated_cost_usd"]
            self.save()

    def save(self):
        if self.path:
            write_json(self.path, self.summary())

    def summary(self):
        return {"max_calls": self.max_calls, "max_cost_usd": self.max_cost_usd,
                "calls": self.calls, "input_tokens": self.input_tokens_seen,
                "estimated_cost_usd": round(self.spent_estimate_usd, 8),
                "accounting": "Successful input at uncached rate; failed or interrupted requests retain conservative reserves.",
                "pricing_source": "https://developers.openai.com/api/docs/guides/decisions#pricing-and-availability",
                "pricing_verified": "2026-11-08"}

    def check_before(self, tokens):
        self.save()
        super().check_before(tokens)

    def record(self, tokens, cost):
        super().record(tokens, cost)
        self.save()

    def close(self):
        if self.lock is not None and not self.lock.closed:
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_UN)
            self.lock.close()


def variants(base, economy_grid=False):
    if not economy_grid:
        return [("base", copy.deepcopy(base))]
    out = []
    for cap, early in itertools.product((2, 3, None), (True, False)):
        rules = copy.deepcopy(base)
        rules["glory"]["cap"] = cap
        rules["succession"]["support_in_city"] = early
        name = f"cap{cap if cap is not None else 'none'}-{'early' if early else 'late'}"
        out.append((name, rules))
    return out


def schedule(index, profiles=PROFILES):
    # For a fixed index, every rule variant gets the same policy/gate pair.
    # All 24 gate permutations occur before repeating. Policy identities
    # rotate after a complete gate-permutation block.
    gate_permutations = tuple(itertools.permutations(IDS))
    gate_order = gate_permutations[index % len(gate_permutations)]
    policy_rotation = (index // len(gate_permutations)) % len(IDS)
    assignment = {pid: profiles[(i + policy_rotation) % len(profiles)]
                  for i, pid in enumerate(IDS)}
    return gate_order, assignment


def _categories(obs):
    pending = obs.get("pending_claim")
    categories = set()
    for action in obs["legal_actions"]:
        kind = action["kind"]
        if kind == "move":
            continue
        if kind == "duel" and pending and action.get("target") == pending["player"]:
            kind = "counterclaim"
        categories.add(kind)
    return sorted(categories)


def run_offline(rules, seed, game_id, assignment, out_dir, before_action=None):
    state = engine.new_game(rules, seed, game_id, assignment)
    rng = random.Random(f"probe:{seed}")
    cap = 4 * (rules["level1"]["max_rounds"] + rules["level2"]["max_rounds"] + 3)
    for _ in range(cap):
        if engine.is_finished(state):
            break
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act(assignment[state["active_player"]], obs, rng)
        if before_action:
            before_action(state, obs, action_id)
        engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
    if not engine.is_finished(state):
        raise RuntimeError("offline game exceeded its explicit turn bound")
    engine.check_invariants(state)
    engine.write_run(str(out_dir), state)
    result = engine.result(state)
    return {"game_id": game_id, "seed": seed, "status": "finished",
            "provider": "offline-bots", "players": assignment,
            "rules_hash": engine.rules_hash(rules), "winner": result["winner"],
            "outcome": result["outcome"], "total_turns": result["total_turns"],
            "total_rounds": result["total_rounds"], "result": result}


def public_turn_audit(state, obs, chosen_action_id):
    """Log choice context without mapping hidden districts or future dice."""
    action = next(a for a in obs["legal_actions"] if a["action_id"] == chosen_action_id)
    categories = _categories(obs)
    productive_at_destination = any(a["kind"] == "explore" and a["destination"] == action["destination"]
                                    for a in obs["legal_actions"])
    pending = obs.get("pending_claim")
    return {"game_id": obs["game_id"], "turn_id": obs["turn_id"], "player": obs["viewer"],
            "phase": obs["phase"], "chosen_kind": action["kind"],
            "available_categories": categories,
            "choice_rich": len(categories) >= 2,
            "chosen_counterclaim": bool(pending and action["kind"] == "duel" and action.get("target") == pending["player"]),
            "avoidable_treasure_walk": action["kind"] == "move" and productive_at_destination,
            "pending_claim": copy.deepcopy(obs.get("pending_claim"))}


def _run_continuation(state, focal_player, profile, turn_bound, seed):
    rng = random.Random(seed)
    for _ in range(turn_bound):
        if engine.is_finished(state):
            break
        obs = engine.observe(state, state["active_player"])
        # Vary opponents while keeping the focal strategy constant.
        policy = "balanced" if state["active_player"] == focal_player else profile
        action_id, reason = policies.act(policy, obs, rng)
        engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
    if not engine.is_finished(state):
        return "truncated"
    return "win" if state["winner"] == focal_player else "draw" if state["winner"] is None else "loss"


def alternative_audit(snapshot, chosen_id, rollouts=4, turn_bound=200, seed=99001):
    """Compare actions on sampled worlds compatible with public evidence.

    Simulator copies may contain secrets; the model never receives them.
    Estimates are conditional on the continuation policies and sample size.
    """
    obs = engine.observe(snapshot, snapshot["active_player"])
    candidates, _ = candidate_actions.build_candidates(obs, snapshot["rules"])
    actions = {a["action_id"]: a for a in obs["legal_actions"]}
    # One representative of each strategic category, plus the played action.
    picks = {chosen_id: actions[chosen_id]}
    seen = set()
    for candidate in candidates:
        category = "counterclaim" if candidate["features"].get("counterclaim") else candidate["kind"]
        if category not in seen and category != "move":
            picks[candidate["action_id"]] = actions[candidate["action_id"]]
            seen.add(category)
    for candidate in candidates:
        if candidate["kind"] == "move":
            picks[candidate["action_id"]] = actions[candidate["action_id"]]
            break
    worlds = []
    for trial in range(rollouts):
        world = copy.deepcopy(snapshot)
        prng = random.Random(seed + trial)
        known = set(world["revealed"])
        unknown = [name for name in sorted(world["district_equipment"]) if name not in known]
        unknown_items = [world["district_equipment"][name] for name in unknown]
        prng.shuffle(unknown_items)
        for name, item in zip(unknown, unknown_items):
            world["district_equipment"][name] = item
        # Equal stream starts for all alternatives within the same trial.
        for stream in ("movement", "combat"):
            world["rng"][stream] = prng.randrange(1, 2 ** 32)
        worlds.append(world)
    comparisons = []
    for action_id, action in picks.items():
        outcomes = {"win": 0, "loss": 0, "draw": 0, "truncated": 0}
        profiles = ("balanced", "counterleader")
        for trial, world in enumerate(worlds):
            for profile in profiles:
                branch = copy.deepcopy(world)
                engine.apply_action(branch, branch["active_player"], branch["turn_id"], action_id, "alternative audit")
                outcome = _run_continuation(branch, obs["viewer"], profile, turn_bound, seed + trial)
                outcomes[outcome] += 1
        n = sum(outcomes.values())
        comparisons.append({"action_id": action_id, "kind": action["kind"],
                            "destination": action["destination"],
                            "spend_prestige": bool(action.get("spend_prestige")),
                            "outcomes": outcomes, "rollout_count": n,
                            "estimated_win_fraction": outcomes["win"] / n if n else None})
    return {"game_id": obs["game_id"], "turn_id": obs["turn_id"],
            "viewer": obs["viewer"], "played_action": chosen_id,
            "public_projection": candidate_actions.project_observation(obs, snapshot["rules"]),
            "alternatives": comparisons,
            "method": "Resampled compatible hidden worlds; paired future stream starts; balanced and counterleader opponents.",
            "limitations": "Small policy-dependent estimates, not exact action values or human-interest ratings. Truncated outcomes are reported separately."}


def rate_interval(wins, games):
    if games == 0:
        return {"wins": wins, "games": games, "rate": None, "wilson_95": None}
    z = 1.959963984540054
    rate = wins / games
    denominator = 1 + z*z/games
    center = (rate + z*z/(2*games)) / denominator
    radius = z * math.sqrt(rate*(1-rate)/games + z*z/(4*games*games)) / denominator
    return {"wins": wins, "games": games, "rate": rate,
            "wilson_95": [max(0, center-radius), min(1, center+radius)]}


def aggregate(games, turns):
    complete = [g for g in games if g["status"] == "finished"]
    wins_by_strategy, wins_by_gate = {}, {}
    draws = 0
    totals = {key: 0 for key in ("prestige_earned", "prestige_spent", "prestige_wasted_at_cap",
                                "equipment_collected", "support_gained", "claims_made",
                                "claims_cancelled", "response_turns", "idle_moves")}
    round_counts = []
    first_collector_wins = first_collector_games = 0
    for game in complete:
        result = game["result"]
        winner = result["winner"]
        draws += winner is None
        round_counts.append(result["total_rounds"])
        if winner:
            strategy = game["players"][winner]
            wins_by_strategy[strategy] = wins_by_strategy.get(strategy, 0) + 1
            gate = result["players"][winner].get("gate_id", "unknown")
            wins_by_gate[gate] = wins_by_gate.get(gate, 0) + 1
        if result.get("first_challenger"):
            first_collector_games += 1
            first_collector_wins += result["first_challenger"] == winner
        for player in result["players"].values():
            for key in totals:
                value = player.get(key, 0)
                totals[key] += len(value) if isinstance(value, list) else value
    complete_ids = {g["game_id"] for g in complete}
    complete_turns = [t for t in turns if t["game_id"] in complete_ids]
    challenged_claims = {(turn["game_id"], turn["pending_claim"]["claim_id"])
                        for turn in complete_turns if turn.get("chosen_counterclaim")}
    strategies = sorted({name for game in complete for name in game["players"].values()})
    claims_made = totals["claims_made"]
    return {"finished_games": len(complete), "incomplete_games": len(games) - len(complete),
            "draws": draws, "draw_fraction": draws / len(complete) if complete else None,
            "wins_by_strategy": wins_by_strategy, "wins_by_gate": wins_by_gate,
            "strategy_rates": {name: rate_interval(wins_by_strategy.get(name, 0),
                               sum(list(g["players"].values()).count(name) for g in complete))
                               for name in strategies},
            "gate_rates": {gate: rate_interval(wins_by_gate.get(gate, 0), len(complete)) for gate in IDS},
            "median_rounds": statistics.median(round_counts) if round_counts else None,
            "first_collector_wins": first_collector_wins, "first_collector_games": first_collector_games,
            "turns_observed": len(turns), "choice_rich_turns": sum(t["choice_rich"] for t in turns),
            "counterclaim_attempts": sum(t.get("chosen_counterclaim", False) for t in complete_turns),
            "claim_statistics_scope": "finished_games",
            "challenged_claims": len(challenged_claims),
            "challenged_claim_fraction": len(challenged_claims) / claims_made if claims_made else 0.0,
            "avoidable_treasure_walks": sum(t["avoidable_treasure_walk"] for t in turns),
            "resource_and_claim_totals": totals,
            "interpretation": "Diagnostic measures for mechanical incentives; none alone measures human fun."}


def markdown_report(payload):
    lines = ["# Succession experiment", "", f"Date: {time.strftime('%Y-%m-%d', time.gmtime())}.", "",
             f"Provider: `{payload['provider']}`. Split: `{payload['split']}`.", "",
             "Each result is a simulation. Human clarity, tension, and enjoyment require human playtests.", "",
             "| Variant | Finished | Incomplete | Draws | Median rounds | Choice-rich turns | Avoidable treasure walks |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, summary in payload["variants"].items():
        lines.append(f"| {name} | {summary['finished_games']} | {summary['incomplete_games']} | {summary['draws']} | {summary['median_rounds']} | {summary['choice_rich_turns']} | {summary['avoidable_treasure_walks']} |")
    lines += ["", "## Assessment", "", "Inspect the strategy and gate tables in `summary.json`. A strategy disappearing, repeated claim cancellation, or excessive farming needs a causal explanation and a new opponent probe.",
              "", "Alternative-play estimates are in `alternatives.jsonl`. They use sampled compatible hidden worlds and paired future random streams. Small differences are not evidence of a better rule.",
              "", "Screening and holdout seeds are separate. Do not tune a rule after reading its holdout result and then reuse that result as independent validation."]
    if payload.get("budget"):
        lines += ["", f"Live requests: {payload['budget']['calls']}. Estimated cost: ${payload['budget']['estimated_cost_usd']:.6f}."]
    return "\n".join(lines) + "\n"


def evaluate_rules(rules_path, out, games=24, seed_base=10000, split="screen",
                   profiles=PROFILES, audit_positions=2, rollouts=4,
                   audit_turns=200, economy_grid=False, provider="mock",
                   live_decisions=False, max_cost_usd=0.0,
                   max_decisions_calls=0, budget_ledger=None, live_seats=4):
    """Run one immutable rules candidate and return its written summary.

    A nonempty output directory is rejected. Incomplete live games remain
    incomplete and the returned exit_code is two; they are never draws.
    """
    argv = ["--rules", str(rules_path), "--out", str(out), "--games", str(games),
            "--seed-base", str(seed_base), "--split", split,
            "--profiles", ",".join(profiles), "--audit-positions", str(audit_positions),
            "--rollouts", str(rollouts), "--audit-turns", str(audit_turns),
            "--provider", provider, "--max-cost-usd", str(max_cost_usd),
            "--max-decisions-calls", str(max_decisions_calls), "--live-seats", str(live_seats)]
    if economy_grid:
        argv.append("--economy-grid")
    if live_decisions:
        argv.append("--live-decisions")
    if budget_ledger:
        argv.extend(["--budget-ledger", str(budget_ledger)])
    code = main(argv)
    result = json.loads((Path(out) / "summary.json").read_text())
    result["exit_code"] = code
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", default="rules_v08_succession.json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--games", type=int, default=24, help="Games per rule variant")
    parser.add_argument("--seed-base", type=int)
    parser.add_argument("--split", choices=("screen", "holdout"), default="screen")
    parser.add_argument("--provider", choices=("mock", "live"), default="mock")
    parser.add_argument("--live-decisions", action="store_true")
    parser.add_argument("--live-seats", type=int, choices=(1, 4), default=4)
    parser.add_argument("--max-cost-usd", type=float, default=0.0)
    parser.add_argument("--max-decisions-calls", type=int, default=0)
    parser.add_argument("--wall-clock-seconds", type=float, default=900)
    parser.add_argument("--budget-ledger")
    parser.add_argument("--economy-grid", action="store_true")
    parser.add_argument("--audit-positions", type=int, default=2)
    parser.add_argument("--rollouts", type=int, default=4)
    parser.add_argument("--audit-turns", type=int, default=200)
    parser.add_argument("--profiles", default=",".join(PROFILES))
    args = parser.parse_args(argv)
    if args.games < 1 or args.games > 768:
        parser.error("--games must be within 1..768 per variant")
    if not 0 <= args.audit_positions <= 12 or not 1 <= args.rollouts <= 32 or not 1 <= args.audit_turns <= 500:
        parser.error("audit limits: positions 0..12, rollouts 1..32, turns 1..500")
    profiles = tuple(args.profiles.split(","))
    if len(profiles) != 4:
        parser.error("--profiles must list four policy names")
    if args.provider == "live" and (not args.live_decisions or not math.isfinite(args.max_cost_usd) or args.max_cost_usd <= 0 or args.max_decisions_calls <= 0):
        parser.error("live play requires --live-decisions, --max-cost-usd and --max-decisions-calls")
    if args.provider != "live" and args.live_decisions:
        parser.error("--live-decisions requires --provider live")
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        parser.error("output directory is not empty; use a new directory for each experiment")
    rules = engine.load_rules(args.rules)
    if rules.get("gameplay_mode") != "succession-v1":
        parser.error("this evaluator needs a succession-v1 ruleset")
    out.mkdir(parents=True, exist_ok=True)
    base_seed = args.seed_base if args.seed_base is not None else 10000 if args.split == "screen" else 50000
    budget = LedgerBudget(args.budget_ledger, args.max_decisions_calls, args.max_cost_usd,
                          args.wall_clock_seconds) if args.provider == "live" else None
    payload = {"schema": "succession-experiments-1", "provider": "live-decisions" if budget else "offline-bots",
               "split": args.split, "seed_base": base_seed, "games_per_variant": args.games,
               "policy_version": POLICY_VERSION, "profiles": profiles,
               "rules_hash": engine.rules_hash(rules), "variants": {},
               "notes": "Gate permutations are covered in blocks of 24; policy identities rotate between blocks. Use at least 96 games for one full profile/gate rotation."}
    snapshots = []
    snapshot_categories = set()
    try:
        stop = False
        for name, variant in variants(rules, args.economy_grid):
            games, turns = [], []
            variant_dir = out / name
            variant_dir.mkdir()
            write_json(variant_dir / "rules.json", variant)
            for index in range(args.games):
                gate_order, assignment = schedule(index, profiles)
                game_rules = copy.deepcopy(variant)
                game_rules["succession"]["gate_assignment"] = "manual"
                game_rules["succession"]["gate_order"] = list(gate_order)
                seed = base_seed + index
                game_id = f"{name}-{args.split}-{seed}"
                if budget:
                    assignment = {pid: "decisions" if args.live_seats == 4 or i == index % 4 else assignment[pid]
                                  for i, pid in enumerate(IDS)}

                def before_action(state, obs, action_id):
                    turn = public_turn_audit(state, obs, action_id)
                    turns.append(turn)
                    append_json(variant_dir / "choices.jsonl", turn)
                    category = "response" if obs.get("pending_claim") else f"phase{obs['phase']}"
                    if len(snapshots) < args.audit_positions and len(turn["available_categories"]) >= 2 and category not in snapshot_categories:
                        snapshots.append((copy.deepcopy(state), action_id))
                        snapshot_categories.add(category)

                if budget:
                    config = ai_driver.load_decisions_config()
                    config.update(provider="live", model="gpt-6-luna", prompt_version="v08-succession-1",
                                  max_retries=0, strict_budget=True, fallback_on_live_error=False,
                                  budget_reserve_multiplier=5.0)
                    game = ai_driver.run_ai_game(game_rules, seed, game_id, assignment,
                                                str(variant_dir / game_id), provider="live", config=config,
                                                max_cost_usd=args.max_cost_usd,
                                                max_decisions_calls=args.max_decisions_calls,
                                                shared_budget=budget, before_action=before_action)
                    budget.save()
                else:
                    game = run_offline(game_rules, seed, game_id, assignment,
                                       variant_dir / game_id, before_action)
                games.append(game)
                append_json(variant_dir / "games.jsonl", game)
                print(f"{name}: {index+1}/{args.games} {game['status']}", flush=True)
                payload["variants"][name] = aggregate(games, turns)
                if budget:
                    payload["budget"] = budget.summary()
                write_json(out / "summary.json", payload)
                if game["status"] != "finished":
                    stop = True
                    break
            payload["variants"][name] = aggregate(games, turns)
            if stop:
                break
        for snapshot, action_id in snapshots:
            audit = alternative_audit(snapshot, action_id, args.rollouts, args.audit_turns)
            append_json(out / "alternatives.jsonl", audit)
        payload["alternative_positions"] = len(snapshots)
        if budget:
            budget.save()
            payload["budget"] = budget.summary()
        write_json(out / "summary.json", payload)
        (out / "report.md").write_text(markdown_report(payload), encoding="utf-8")
        print(json.dumps({"out": str(out), "provider": payload["provider"], "variants": payload["variants"],
                          "budget": payload.get("budget")}, sort_keys=True), flush=True)
        return 0 if not stop else 2
    finally:
        if budget:
            budget.save()
            budget.close()


if __name__ == "__main__":
    raise SystemExit(main())
