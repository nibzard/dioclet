# ABOUTME: Command line entry point for Arena; a thin shell over match and ui.
# ABOUTME: Exit codes: 0 finished, 1 incomplete, 2 configuration error.

import argparse
import os

from dotenv import load_dotenv
from rich.console import Console

from arena import __version__, match as match_mod
from arena.providers import REMOTE_PROVIDERS
from arena.rules_loader import RulesError
from arena.ui import MatchStreamer, scoreboard, wizard


def _resolve_match_path(path):
    if os.path.exists(path):
        return path
    fallback = os.path.join(match_mod.ARENA_DIR, path)
    if os.path.exists(fallback):
        return fallback
    raise match_mod.MatchConfigError(
        f"match file not found: {path} (also tried {fallback})")


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="arena",
        description="Decision models play Dioclet in the terminal.")
    parser.add_argument("--match", metavar="PATH",
                        help="match configuration file; skips the setup wizard")
    parser.add_argument("--version", action="version",
                        version=f"arena {__version__}")
    args = parser.parse_args(argv)
    console = Console()
    try:
        if args.match:
            config = match_mod.load_match(_resolve_match_path(args.match))
        else:
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
