#!/usr/bin/env python3
"""CLI for the Diocletian's Palace simulator (SPEC §9).

All commands print JSON on stdout; errors go to stderr with a nonzero exit
code. Every path is explicit; run directories hold the only game state.
"""

import argparse
import json
import os
import random
import sys

import engine
import policies
import report

COMMANDS = ("validate", "new", "observe", "act", "auto", "batch", "report",
            "replay")


def _print_json(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def _fail(code, message):
    print(json.dumps({"error": code, "message": message}, sort_keys=True),
          file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_validate(args):
    rules = engine.load_rules(args.rules)
    _print_json({
        "ok": True,
        "rules_file": os.path.abspath(args.rules),
        "rules_version": rules["rules_version"],
        "game_name": rules["game_name"],
        "rules_hash": engine.rules_hash(rules),
        "engine_version": engine.ENGINE_VERSION,
    })


def cmd_new(args):
    rules = engine.load_rules(args.rules)
    pol = _parse_policies(args.policies)
    game_id = os.path.basename(os.path.normpath(args.out))
    state = engine.new_game(rules, args.seed, game_id, pol)
    engine.write_run(args.out, state)
    engine.reset_events_file(args.out, state)
    obs = engine.observe(state, state["active_player"])
    _print_json({
        "run_dir": os.path.abspath(args.out),
        "game_id": state["game_id"],
        "seed": state["seed"],
        "rules_hash": state["rules_hash"],
        "turn_order": state["turn_order"],
        "policies": state.get("policies", {}),
        "first_active_player": state["active_player"],
        "first_turn_id": state["turn_id"],
        "first_movement_die": state["current_roll"],
        "legal_action_count": len(obs["legal_actions"]),
    })


def _parse_policies(spec):
    if not spec:
        return None
    parts = spec.split(",")
    if len(parts) == 1:
        return {pid: parts[0] for pid in report.SEATS}
    if len(parts) != 4:
        _fail("invalid_policies",
              "policies must be one name or four comma-separated names "
              "for P0,P1,P2,P3")
    for name in parts:
        if name not in policies.POLICIES:
            _fail("invalid_policies", f"unknown policy {name!r}")
    return {pid: name for pid, name in zip(report.SEATS, parts)}


def cmd_observe(args):
    state = engine.load_run(args.run)
    try:
        obs = engine.observe(state, args.player)
    except engine.EngineError as exc:
        _fail(exc.code, str(exc))
    _print_json(obs)


def cmd_act(args):
    state = engine.load_run(args.run)
    try:
        record = engine.apply_action(state, args.player, args.turn_id,
                                     args.action_id, args.note)
    except engine.EngineError as exc:
        _fail(exc.code, str(exc))
    engine.write_run(args.run, state)
    payload = {
        "applied": True,
        "turn_id": record["turn_id"],
        "player": record["player"],
        "action_id": record["action_id"],
        "events": record["events"],
        "position_after": record["position_after"],
        "glory_after": record["glory_after"],
        "equipment_count_after": record["equipment_count_after"],
        "status": state["status"],
        "next_active_player": state["active_player"]
        if state["status"] == "in_progress" else None,
        "next_turn_id": state["turn_id"]
        if state["status"] == "in_progress" else None,
    }
    if engine.is_finished(state):
        payload["result"] = engine.result(state)
    _print_json(payload)


def cmd_auto(args):
    state = engine.load_run(args.run)
    pol = state.get("policies") or {}
    if args.policies:
        pol = _parse_policies(args.policies)
    if not pol:
        pol = {pid: "balanced" for pid in report.SEATS}
    state["policies"] = pol
    prng = random.Random(f"policy:{state['game_id']}:{state['seed']}")
    turns = 0
    while not engine.is_finished(state):
        turns += 1
        if turns > 2000:
            _fail("no_termination", "auto-play exceeded 2000 turns")
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act(pol[state["active_player"]], obs, prng)
        engine.apply_action(state, state["active_player"], obs["turn_id"],
                            action_id, reason)
    engine.check_invariants(state)
    engine.write_run(args.run, state)
    _print_json(engine.result(state))


def cmd_batch(args):
    rules = engine.load_rules(args.rules)
    if args.schedule == "experiment":
        if args.games % 4 != 0:
            _fail("invalid_games",
                  "the experiment schedule requires a multiple of 4 games")
        schedule = report.schedule_for
    else:
        pol = _parse_policies(args.policies or "balanced")

        def schedule(index, games=0, _pol=pol):
            return dict(_pol)
    rows, summary, _states = report.run_batch(
        rules, args.out, args.games, args.seed_base, schedule,
        os.path.abspath(args.rules))
    _print_json({
        "out_dir": os.path.abspath(args.out),
        "games": summary["games"],
        "wins": summary["wins"],
        "draws": summary["draws"],
        "win_rate": summary["win_rate"],
        "median_total_rounds": summary["durations"]["total_rounds"]["median"],
    })


def cmd_report(args):
    path = os.path.join(args.input, "summary.json")
    if not os.path.exists(path):
        rows = _read_csv_rows(args.input)
        _print_json(report.summarize(rows))
        return
    with open(path, "r", encoding="utf-8") as fh:
        _print_json(json.load(fh))


def _read_csv_rows(input_dir):
    import csv
    csv_path = os.path.join(input_dir, "games.csv")
    if not os.path.exists(csv_path):
        _fail("missing_input", f"no summary.json or games.csv in {input_dir}")
    rows = []
    with open(csv_path, "r", newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            row = {}
            for key, value in raw.items():
                try:
                    row[key] = int(value)
                except (TypeError, ValueError):
                    row[key] = value
            rows.append(row)
    return rows


def cmd_ai_auto(args):
    import ai_driver
    rules = engine.load_rules(args.rules)
    names = args.players.split(",")
    if len(names) != 4:
        _fail("invalid_players",
              "--players needs four comma-separated names for P0..P3")
    valid = set(policies.POLICIES) | {"tactical", "decisions"}
    for name in names:
        if name not in valid:
            _fail("invalid_players",
                  f"unknown player policy {name!r}; expected one of "
                  f"{sorted(valid)}")
    if args.provider == "live" and not args.live_decisions:
        _fail("live_not_enabled",
              "live Decisions requires the explicit --live-decisions flag")
    if args.provider == "live" and not (args.max_decisions_calls
                                        or args.max_cost_usd):
        _fail("missing_budget",
              "live Decisions requires --max-decisions-calls and/or "
              "--max-cost-usd")
    try:
        config = ai_driver.load_decisions_config(args.decisions_config)
    except (OSError, ValueError) as exc:
        _fail("invalid_config", str(exc))
    if args.model:
        config["model"] = args.model
    if args.selection_mode:
        config["selection_mode"] = args.selection_mode
    players = {pid: name for pid, name in zip(report.SEATS, names)}
    game_id = os.path.basename(os.path.normpath(args.out))
    live_client = None
    if args.provider == "live":
        if not os.environ.get("OPENAI_API_KEY"):
            _fail("missing_key",
                  "OPENAI_API_KEY is not set; live Decisions unavailable")
        live_client = None  # LiveProvider constructs OpenAI() itself
    try:
        summary = ai_driver.run_ai_game(
            rules, args.seed, game_id, players, args.out,
            provider=args.provider, config=config,
            live_client=live_client,
            max_decisions_calls=args.max_decisions_calls,
            max_cost_usd=args.max_cost_usd,
            max_input_tokens=args.max_input_tokens_estimate,
            wall_clock_seconds=args.timeout_minutes * 60,
            resume=args.resume)
    except FileExistsError as exc:
        _fail("run_dir_exists", str(exc))
    _print_json({k: v for k, v in summary.items() if k != "result"})


def cmd_tournament(args):
    import tournament
    try:
        result = tournament.run_tournament(
            args.config, args.out, live=args.live_decisions,
            resume=args.resume, dry=args.dry_run)
    except (ValueError, OSError) as exc:
        _fail("invalid_tournament", str(exc))
    except SystemExit as exc:
        _fail("live_not_enabled", str(exc))
    _print_json(result)


def cmd_replay(args):
    run = os.path.abspath(args.run)
    with open(os.path.join(run, "rules.snapshot.json"), "r",
              encoding="utf-8") as fh:
        rules = json.load(fh)
    with open(os.path.join(run, "metadata.json"), "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(run, "events.jsonl"), "r", encoding="utf-8") as fh:
        logged = [json.loads(line) for line in fh if line.strip()]

    state = engine.new_game(rules, meta["seed"], meta["game_id"],
                            meta.get("policies") or None)
    for record in logged:
        if record["action"]["kind"] == "skip_turn":
            continue  # engine regenerates skip records automatically
        engine.apply_action(state, record["player"], record["turn_id"],
                            record["action_id"], record.get("reason"))

    def normalize_events(events):
        return [{k: v for k, v in rec.items()}
                for rec in events]

    replayed = normalize_events(state["events"])
    original = normalize_events(logged)
    result_ok = events_ok = None
    if args.verify:
        with open(os.path.join(run, "result.json"), "r", encoding="utf-8") as fh:
            original_result = json.load(fh)
        replay_result = engine.result(state)
        result_ok = replay_result == original_result
        events_ok = replayed == original
    _print_json({
        "run": run,
        "seed": meta["seed"],
        "turns_replayed": len(replayed),
        "status": state["status"],
        "winner": state["winner"],
        "events_match": events_ok,
        "result_match": result_ok,
        "verified": (events_ok and result_ok) if args.verify else None,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="sim.py",
                                     description="Diocletian's Palace simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate a rules JSON file")
    p.add_argument("--rules", required=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("new", help="create a persistent game")
    p.add_argument("--rules", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--out", required=True, help="run directory to create")
    p.add_argument("--policies", default=None,
                   help="one policy name or four for P0,P1,P2,P3")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("observe", help="side-effect-free player observation")
    p.add_argument("--run", required=True)
    p.add_argument("--player", required=True)
    p.set_defaults(func=cmd_observe)

    p = sub.add_parser("act", help="submit one action for the active player")
    p.add_argument("--run", required=True)
    p.add_argument("--player", required=True)
    p.add_argument("--turn-id", type=int, required=True)
    p.add_argument("--action-id", required=True)
    p.add_argument("--note", default=None)
    p.set_defaults(func=cmd_act)

    p = sub.add_parser("auto", help="finish a game with built-in policies")
    p.add_argument("--run", required=True)
    p.add_argument("--policies", default=None)
    p.set_defaults(func=cmd_auto)

    p = sub.add_parser("batch", help="run many headless games")
    p.add_argument("--rules", required=True)
    p.add_argument("--games", type=int, required=True)
    p.add_argument("--seed-base", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--policies",
                   default="balanced,balanced,balanced,balanced")
    p.add_argument("--schedule", default="fixed",
                   choices=["fixed", "experiment"],
                   help="fixed uses --policies; experiment follows SPEC §13")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("report", help="summarize a batch directory")
    p.add_argument("--input", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("ai-auto", help="play a game with AI policies "
                                        "(decisions/tactical/bots)")
    p.add_argument("--rules", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--players", default="decisions,decisions,decisions,"
                                        "decisions")
    p.add_argument("--provider", default="mock",
                   choices=["mock", "playback", "live"])
    p.add_argument("--live-decisions", action="store_true",
                   help="explicit opt-in required for provider=live")
    p.add_argument("--model", default=None)
    p.add_argument("--decisions-config", default="decisions_config.json")
    p.add_argument("--selection-mode", default=None,
                   choices=["top", "sample"])
    p.add_argument("--max-decisions-calls", type=int, default=0)
    p.add_argument("--max-cost-usd", type=float, default=0.0)
    p.add_argument("--max-input-tokens-estimate", type=int, default=0)
    p.add_argument("--timeout-minutes", type=float, default=0.0)
    p.add_argument("--resume", action="store_true")
    p.set_defaults(func=cmd_ai_auto)

    p = sub.add_parser("tournament", help="run a tournament from a JSON "
                                          "config (V0.4.1)")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True, help="e.g. results/v041")
    p.add_argument("--live-decisions", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_tournament)

    p = sub.add_parser("replay", help="replay a run and optionally verify")
    p.add_argument("--run", required=True)
    p.add_argument("--verify", action="store_true")
    p.set_defaults(func=cmd_replay)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except engine.EngineError as exc:
        _fail(exc.code, str(exc))
    except FileNotFoundError as exc:
        _fail("missing_file", str(exc))


if __name__ == "__main__":
    main()
