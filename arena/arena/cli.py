# ABOUTME: Command line entry point for Arena; a thin shell over match,
# ABOUTME: series, and fixtures. Exit codes: 0 finished, 1 incomplete, 2 config error.

import argparse
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Confirm

from arena import __version__, match as match_mod, series as series_mod
from arena.providers import REMOTE_PROVIDERS
from arena.rules_loader import RulesError
from arena.ui import (MatchStreamer, fixtures_table, scoreboard,
                      series_estimate, series_scoreboard, wizard)


def _resolve_match_path(path):
    if os.path.exists(path):
        return path
    fallback = os.path.join(match_mod.ARENA_DIR, path)
    if os.path.exists(fallback):
        return fallback
    raise match_mod.MatchConfigError(
        f"configuration file not found: {path} (also tried {fallback})")


def _run_match(args, console):
    config = match_mod.load_match(_resolve_match_path(args.match))
    run_dir = match_mod.make_run_dir(config)
    streamer = MatchStreamer(
        console,
        remote_seats={sc.seat for sc in config.seats
                      if sc.provider in REMOTE_PROVIDERS})
    summary = match_mod.run_match(config, run_dir, hooks=streamer)
    scoreboard(console, summary)
    return 1 if summary.get("incomplete") else 0


def _approve_spend(console, estimate, yes):
    """Gate a paid series: --yes, or a prompt on a TTY, or refuse."""
    if yes:
        return True
    if sys.stdout.isatty():
        return bool(Confirm.ask("Start the series?", default=False))
    console.print(
        "[red]refusing to spend without approval: pass --yes or run in "
        "a terminal[/red]")
    return False


def _run_series(args, console):
    spec = series_mod.load_series(_resolve_match_path(args.series))
    if spec.has_remote_players:
        estimate = series_mod.estimate_series(spec)
        series_estimate(console, estimate)
        if not _approve_spend(console, estimate, args.yes):
            return 2
    summary = series_mod.run_series(spec, console=console, stream=True)
    series_scoreboard(console, summary)
    games = summary["games"]
    return 1 if games["skipped"] or games["incomplete"] else 0


def _run_fixtures(args, console):
    from arena.providers import build_provider

    providers = []
    for name, model in series_mod.fixture_providers(
            os.environ, include_bots=args.fixtures_bots):
        providers.append(build_provider(name, model))
    fixtures = series_mod.load_fixtures()
    rows = series_mod.run_fixtures(providers, fixtures, {})
    fixtures_table(console, rows)
    return 0


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="arena",
        description="Decision models play Dioclet in the terminal.")
    parser.add_argument("--match", metavar="PATH",
                        help="match configuration file; skips the setup wizard")
    parser.add_argument("--series", metavar="PATH",
                        help="series configuration file; plays seeds x seat "
                             "rotations under one budget")
    parser.add_argument("--fixtures", action="store_true",
                        help="ask each provider once per frozen tactical "
                             "fixture and report the score")
    parser.add_argument("--fixtures-bots", action="store_true",
                        help="with --fixtures, also include the local bots")
    parser.add_argument("--yes", action="store_true",
                        help="approve the estimated spend of a series "
                             "without a prompt")
    parser.add_argument("--version", action="version",
                        version=f"arena {__version__}")
    args = parser.parse_args(argv)
    console = Console()
    try:
        if args.match:
            return _run_match(args, console)
        if args.series:
            return _run_series(args, console)
        if args.fixtures:
            return _run_fixtures(args, console)
        config = wizard(console)
    except (match_mod.MatchConfigError, RulesError) as exc:
        console.print(f"[red]config error:[/red] {exc}")
        return 2
    except KeyboardInterrupt:
        console.print("[dim]setup cancelled[/dim]")
        return 0
    run_dir = match_mod.make_run_dir(config)
    streamer = MatchStreamer(
        console,
        remote_seats={sc.seat for sc in config.seats
                      if sc.provider in REMOTE_PROVIDERS})
    summary = match_mod.run_match(config, run_dir, hooks=streamer)
    scoreboard(console, summary)
    return 1 if summary.get("incomplete") else 0


if __name__ == "__main__":
    raise SystemExit(main())
