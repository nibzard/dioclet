"""Reproducible AI tournament runner (V0.4.1).

Orchestrates multiple AI games from a JSON tournament configuration
under `results/v041/`. Games are resumable without duplication,
per-game and aggregate API budgets are enforced, failures stop the
tournament gracefully without ever substituting a policy, and
everything needed for offline analysis is preserved per game.
"""

import argparse
import json
import os
import sys

import ai_driver
import decisions_policy
import engine

TOURNAMENT_VERSION = "tournament-0.4.1"

# Measured on the V0.4 pilots (results/v04_live, runs/v04_*):
# ~1,122 input tokens and ~$0.000112 per Decisions call.
PILOT_TOKENS_PER_CALL = 1122
PILOT_COST_PER_CALL = 0.000112


def build_schedule(spec):
    """Expand a tournament spec into an explicit, reproducible list.

    Spec forms:
      {"type": "mirror", "policy": "decisions", "games": 32,
       "seed_base": 5101, "prefix": "ta"}
      {"type": "rotation", "policies": ["decisions", "tactical",
       "balanced", "greedy"], "games": 16, "seed_base": 5201,
       "prefix": "tb1"}   # every policy visits every seat once
      {"type": "pairs", "a": "decisions", "b": "tactical",
       "games": 16, "seed_base": 5301, "prefix": "tb2"}
    """
    games = []
    kind = spec["type"]
    if kind == "mirror":
        for i in range(spec["games"]):
            games.append({
                "game_id": f"{spec['prefix']}{i + 1:02d}",
                "seed": spec["seed_base"] + i,
                "players": {p: spec["policy"] for p in ai_driver.SEATS},
            })
    elif kind == "rotation":
        pols = spec["policies"]
        if len(pols) != 4:
            raise ValueError("rotation needs exactly four policies")
        if spec["games"] % 4:
            raise ValueError("rotation games must be a multiple of four")
        # Seat shift per game: every policy occupies every seat equally.
        for i in range(spec["games"]):
            shift = i % 4
            players = {p: pols[(j + shift) % 4]
                       for j, p in enumerate(ai_driver.SEATS)}
            games.append({
                "game_id": f"{spec['prefix']}{i + 1:02d}",
                "seed": spec["seed_base"] + i,
                "players": players,
            })
    elif kind == "pairs":
        # Alternating seat patterns, then swapped, so neither policy
        # gains a systematic seat or turn-order advantage.
        patterns = [
            {p: spec["a"] for p in ("P0", "P2")} |
            {p: spec["b"] for p in ("P1", "P3")},
            {p: spec["a"] for p in ("P1", "P3")} |
            {p: spec["b"] for p in ("P0", "P2")},
        ]
        for i in range(spec["games"]):
            games.append({
                "game_id": f"{spec['prefix']}{i + 1:02d}",
                "seed": spec["seed_base"] + i,
                "players": patterns[i % 2],
            })
    else:
        raise ValueError(f"unknown schedule type {kind!r}")
    return games


def load_config(path):
    with open(path, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    for key in ("tournament_id", "rules", "provider", "schedules",
                "budget"):
        if key not in config:
            raise ValueError(f"tournament config missing {key!r}")
    config["games"] = []
    for spec in config["schedules"]:
        config["games"].extend(build_schedule(spec))
    ids = [g["game_id"] for g in config["games"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate game ids in tournament")
    return config


def game_dir(root, game_id):
    return os.path.join(root, "games", game_id)


def aggregate_usage(root):
    """Sum actual usage from every game's decisions.jsonl."""
    calls = tokens = 0
    cost = 0.0
    games_dir = os.path.join(root, "games")
    if not os.path.isdir(games_dir):
        return {"calls": 0, "input_tokens": 0, "estimated_cost_usd": 0.0}
    for name in sorted(os.listdir(games_dir)):
        path = os.path.join(games_dir, name, "decisions.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                meta = json.loads(line).get("metadata") or {}
                if meta.get("provider") != "live":
                    continue
                usage = meta.get("usage") or {}
                if usage.get("input_tokens"):
                    calls += 1
                    tokens += usage["input_tokens"]
                    cost += meta.get("estimated_cost_usd", 0.0)
    return {"calls": calls, "input_tokens": tokens,
            "estimated_cost_usd": round(cost, 6)}


def estimate_decisions_turns(game):
    """Rough per-game call estimate from the seat assignment."""
    per_seat = {"decisions": 1, "tactical": 0, "balanced": 0,
                "greedy": 0, "aggressive": 0, "random": 0}
    seats = sum(per_seat.get(p, 0) for p in game["players"].values())
    return round(65 * seats / 4) if seats else 0  # ~65 turns per game


def dry_run(config, root):
    games = config["games"]
    calls = sum(estimate_decisions_turns(g) for g in games)
    tokens = calls * PILOT_TOKENS_PER_CALL
    cost = calls * PILOT_COST_PER_CALL
    budget = config["budget"]
    per_game = min(
        budget.get("per_game_max_calls", 0) or float("inf"),
        (budget.get("per_game_max_cost_usd", 0) or float("inf"))
        / max(PILOT_COST_PER_CALL, 1e-12))
    already = aggregate_usage(root)
    return {
        "tournament_id": config["tournament_id"],
        "provider": config["provider"],
        "games": len(games),
        "games_already_complete": sum(
            os.path.exists(os.path.join(game_dir(root, g["game_id"]),
                                        "result.json")) for g in games),
        "estimated_decisions_calls": calls,
        "estimated_input_tokens": tokens,
        "estimated_cost_usd": round(cost, 4),
        "aggregate_cap_usd": budget.get("aggregate_max_cost_usd"),
        "within_aggregate_cap": (
            cost + already["estimated_cost_usd"]
            <= (budget.get("aggregate_max_cost_usd") or 0)),
        "projected_per_game_calls_cap": per_game
        if per_game != float("inf") else None,
        "already_spent": already,
        "note": "Estimates from V0.4 pilot averages (~1,122 tokens and "
                "~$0.000112 per call); not a billing guarantee.",
    }


def run_tournament(config_path, root, live=False, resume=False,
                   dry=False, progress_every=1):
    config = load_config(config_path)
    provider = config["provider"]
    if provider == "live" and not live and not dry:
        raise SystemExit("live tournament requires --live-decisions")

    if dry:  # no directories, no writes, no games
        return dry_run(config, root)

    os.makedirs(os.path.join(root, "games"), exist_ok=True)
    with open(os.path.join(root,
                           f"tournament_{config['tournament_id']}.json"),
              "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in config.items() if k != "games"},
                  fh, indent=2, sort_keys=True)
        fh.write("\n")

    budget_cfg = config["budget"]
    agg_cap = budget_cfg.get("aggregate_max_cost_usd", 0)
    decisions_config = ai_driver.load_decisions_config(
        config.get("decisions_config", "decisions_config.json"))
    if config.get("model"):
        decisions_config["model"] = config["model"]

    statuses = []
    for index, game in enumerate(config["games"], start=1):
        gid = game["game_id"]
        gdir = game_dir(root, gid)
        if os.path.exists(os.path.join(gdir, "result.json")):
            statuses.append({"game_id": gid, "status": "already_complete"})
            continue
        spent = aggregate_usage(root)
        if agg_cap and spent["estimated_cost_usd"] >= agg_cap:
            statuses.append({"tournament": "stopped",
                             "reason": f"aggregate cost cap reached "
                                       f"(${spent['estimated_cost_usd']:.4f})"})
            break
        projected = spent["estimated_cost_usd"] + \
            estimate_decisions_turns(game) * PILOT_COST_PER_CALL
        if agg_cap and projected > agg_cap:
            statuses.append({"tournament": "stopped",
                             "reason": "aggregate cost cap would be exceeded",
                             "projected": round(projected, 4)})
            break
        try:
            summary = ai_driver.run_ai_game(
                engine.load_rules(config["rules"]),
                game["seed"], gid, game["players"], gdir,
                provider=provider, config=decisions_config,
                max_decisions_calls=budget_cfg.get("per_game_max_calls", 0),
                max_cost_usd=budget_cfg.get("per_game_max_cost_usd", 0.0),
                max_input_tokens=budget_cfg.get("per_game_max_tokens", 0),
                wall_clock_seconds=budget_cfg.get(
                    "per_game_wall_clock_seconds", 0.0),
                resume=resume or os.path.exists(
                    os.path.join(gdir, "state.json")),
            )
        except decisions_policy.DecisionsError as exc:
            statuses.append({"game_id": gid, "status": "stopped",
                             "reason": str(exc)})
            break
        statuses.append({
            "game_id": gid,
            "status": summary["status"],
            "winner": summary.get("winner"),
            "incomplete_reason": summary.get("incomplete_reason"),
            "budget": summary.get("budget"),
        })
        if summary["status"] != "finished":
            statuses.append({"tournament": "stopped",
                             "reason": f"game {gid} incomplete: "
                                       f"{summary.get('incomplete_reason')}"})
            break
        if progress_every and index % progress_every == 0:
            print(f"  {index}/{len(config['games'])} games done "
                  f"(spent ${aggregate_usage(root)['estimated_cost_usd']:.4f})",
                  flush=True)

    report = {
        "tournament_id": config["tournament_id"],
        "tournament_version": TOURNAMENT_VERSION,
        "engine_commit": engine.ENGINE_VERSION,
        "provider": provider,
        "model": config.get("model", decisions_config.get("model")),
        "statuses": statuses,
        "usage": aggregate_usage(root),
    }
    with open(os.path.join(root, "tournament_status.json"), "w",
              encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True, help="results/v041 root")
    parser.add_argument("--live-decisions", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = run_tournament(args.config, args.out, live=args.live_decisions,
                            resume=args.resume, dry=args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
