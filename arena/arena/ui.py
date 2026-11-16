# ABOUTME: Rich terminal UI for Arena: setup wizard, live decision stream, scoreboard.
# ABOUTME: The wizard offers local bots always and remote providers only when keys exist.

import glob
import os

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from arena import match as match_mod
from arena.providers import (REMOTE_PROVIDERS, available_remote_providers,
                             default_model, local_provider_names)


def _provider_label(name, model):
    if model in (None, "", "local"):
        return name
    return f"{name}/{model}"


def wizard(console):
    """Ask for rules, seed, seats, and budget; return a validated MatchConfig."""
    rules_files = sorted(glob.glob(
        os.path.join(match_mod.ARENA_DIR, "rules", "*.json")))
    if not rules_files:
        raise match_mod.MatchConfigError(
            "no rules files found under arena/rules; add one first")
    labels = [os.path.relpath(path, match_mod.ARENA_DIR)
              for path in rules_files]
    rules_label = Prompt.ask("Rules file", choices=labels,
                             default=labels[0] if len(labels) == 1 else None)
    seed = IntPrompt.ask("Seed", default=42)
    menu = local_provider_names() + available_remote_providers(os.environ)
    defaults = ("tactical", "balanced", "greedy", "random")
    seat_specs = []
    for i in range(4):
        seat = f"P{i}"
        provider = Prompt.ask(f"{seat} provider", choices=menu,
                              default=defaults[i] if defaults[i] in menu
                              else menu[0])
        model = None
        if provider in REMOTE_PROVIDERS:
            model = Prompt.ask(f"{seat} model",
                               default=default_model(provider))
        seat_specs.append({"provider": provider, "model": model})
    max_calls = IntPrompt.ask("Budget: max provider calls (0 = no cap)",
                              default=400)
    max_usd = Prompt.ask("Budget: max USD (0 = no cap)", default="0.50")
    try:
        max_usd_value = float(max_usd)
    except ValueError:
        raise match_mod.MatchConfigError(
            f"budget max USD must be a number, got {max_usd!r}") from None
    console.print()
    console.print("[bold]Match setup[/bold]")
    console.print(f"rules   {rules_label}")
    console.print(f"seed    {seed}")
    for i, spec in enumerate(seat_specs):
        console.print(f"        P{i} "
                      f"{_provider_label(spec['provider'], spec['model'])}")
    console.print(f"budget  {max_calls} calls, ${max_usd_value:.2f}")
    if not Confirm.ask("Start the match?", default=True):
        raise KeyboardInterrupt
    return match_mod.make_config(rules_label, seed, seat_specs,
                                 {"max_calls": max_calls,
                                  "max_usd": max_usd_value})


class MatchStreamer:
    """Hooks object that renders the match as it runs."""

    def __init__(self, console, remote_seats=frozenset()):
        self.console = console
        self.remote_seats = set(remote_seats)
        self._status = None
        self._districts = {}

    def _stop_status(self):
        if self._status is not None:
            self._status.stop()
            self._status = None

    def on_turn_start(self, state, view):
        obs = view.observation
        self._districts = {tuple(cell): name for name, cell
                           in obs["board"].get("districts", {}).items()}
        if obs["active_player"] in self.remote_seats:
            seat = obs["active_player"]
            self._status = self.console.status(
                f"[dim]{seat} thinking...", spinner="dots")
            self._status.start()

    def on_decision(self, seat, provider, decision, record, attempt):
        self._stop_status()
        label = _provider_label(provider.name, provider.model)
        summary = match_mod._action_summary(record["action"], self._districts)
        line = (f"R{record['round']} T{record['turn_id']}  "
                f"{seat} {label}   → {summary}")
        if decision.probabilities and decision.action_id in \
                decision.probabilities:
            line += f"   p={decision.probabilities[decision.action_id]:.2f}"
        if decision.latency_ms:
            line += f"  {decision.latency_ms:.0f}ms"
        if decision.cost_usd:
            line += f"  ${decision.cost_usd:.5f}"
        if attempt > 1:
            line += "  [yellow](retry)[/yellow]"
        self.console.print(line)
        events = describe_events(record)
        if events:
            self.console.print(f"        {events}", style="dim")

    def on_failure(self, seat, provider, error_class, error, turn_id,
                   round_no):
        self._stop_status()
        label = _provider_label(provider.name, provider.model)
        self.console.print(
            f"[red]R{round_no} T{turn_id}  {seat} {label}   "
            f"FAILED {error_class}: {error}[/red]")

    def on_result(self, summary):
        self._stop_status()


def describe_events(record):
    """One short line for the engine events of one resolved action."""
    parts = []
    events = record.get("events", [])
    for i, ev in enumerate(events):
        kind = ev.get("type")
        if kind == "duel":
            text = (f"dice {ev.get('attacker_roll')} vs "
                    f"{ev.get('defender_roll')} → {ev.get('winner')} wins")
            for later in events[i + 1:]:
                if later.get("type") == "prestige_earned" \
                        and later.get("cause") == "duel" \
                        and later.get("player") == ev.get("winner"):
                    text += f", +{later['amount']} Prestige"
                    break
            parts.append(text)
        elif kind == "prestige_earned":
            if ev.get("cause") == "duel":
                continue
            parts.append(f"{ev.get('player', '?')} +{ev.get('amount')} Prestige")
        elif kind == "prestige_spent":
            parts.append(f"{ev.get('player', '?')} -{ev.get('amount')} Prestige")
        elif kind == "guard_post":
            outcome = "success" if ev.get("success") else "fail"
            parts.append(f"roll {ev.get('roll')} → {outcome}")
        elif kind == "equipment_collected":
            parts.append(f"{ev.get('player', '?')} takes {ev.get('item')}")
        elif kind == "district_revealed":
            parts.append(f"{ev.get('district')} holds {ev.get('item')}")
        elif kind == "explore_no_gain":
            parts.append("no gain (already owned)")
        elif kind == "support_gained":
            parts.append(f"{ev.get('player', '?')} wins "
                         f"{ev.get('faction')} support")
        elif kind == "claim_proclaimed":
            parts.append(f"{ev.get('player', '?')} proclaims a claim")
        elif kind == "claim_cancelled":
            parts.append("claim cancelled")
        elif kind == "claim_maintained":
            parts.append("claim maintained")
        elif kind == "claim_response":
            parts.append("claim response")
        elif kind == "first_challenger":
            parts.append(f"{ev.get('player', '?')} opens the succession")
        elif kind == "phase_transition":
            parts.append("phase 2 begins")
        elif kind == "game_won":
            parts.append(f"{ev.get('player', '?')} wins the game")
        elif kind == "game_draw":
            parts.append("draw")
        elif kind == "turn_skipped":
            parts.append(f"{ev.get('player', '?')} skips (lost turn)")
        elif kind == "support_site_revealed":
            parts.append("support site revealed")
        elif kind == "ability_used":
            parts.append("ability used")
        else:
            parts.append(str(kind))
    return "; ".join(parts)


def scoreboard(console, summary):
    """Print the end-of-match outcome and per-seat table."""
    if summary.get("incomplete"):
        console.print(f"[red]INCOMPLETE[/red] "
                      f"{summary.get('incomplete_reason', '')}")
    elif summary.get("winner"):
        console.print(f"[green]{summary['winner']} wins[/green] "
                      f"({summary.get('end_reason', '')})")
    else:
        console.print(f"Draw ({summary.get('end_reason', '')})")
    table = Table(title="Scoreboard")
    for column in ("Seat", "Player", "Decisions", "Calls", "Cost", "Errors"):
        table.add_column(column)
    for seat in sorted(summary.get("seats", {})):
        entry = summary["seats"][seat]
        table.add_row(seat,
                      _provider_label(entry["provider"], entry["model"]),
                      str(entry["decisions"]), str(entry["calls"]),
                      f"${entry['cost_usd']:.5f}",
                      str(len(entry["errors"])))
    console.print(table)
    if summary.get("run_dir"):
        console.print(f"[dim]run directory: {summary['run_dir']}[/dim]")
