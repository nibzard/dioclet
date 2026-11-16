# ABOUTME: Series runner for Arena: seeds x seat rotations under one budget,
# ABOUTME: candidate shuffling with a logged order, and the tactical fixture check.

import dataclasses
import glob
import hashlib
import importlib
import json
import os
import random
import time

from arena import engine_adapter as adapter
from arena import match as match_mod
from arena import report
from arena.providers import (ProviderError, REMOTE_PROVIDERS, TurnView,
                             default_model, local_provider_names)

ARENA_DIR = match_mod.ARENA_DIR
GAMES_PER_SEED = 4
SEATS = match_mod.SEATS
# One four-way remote game is about 110 turns; every player decides on
# about a quarter of them (the seats rotate).
EST_TURNS_PER_GAME = 110
# Plan anchor: a four-way remote game is about $0.02 at the November
# 2026 prices, which implies about 6000 input tokens per call.
EST_INPUT_TOKENS_PER_CALL = 6000
FIXTURE_DIR = os.path.join(ARENA_DIR, "tests", "fixtures", "tactical")
DEFAULT_FIXTURE_RULES = "../rules/imperial-rivals-v0.10.2.json"
SHUFFLE_DOMAIN = "series-shuffle"

_PRICING_MODULES = {
    "openai": "arena.providers.openai_decisions",
    "jev": "arena.providers.jev",
    "clef": "arena.providers.clef",
    "pplx": "arena.providers.pplx",
    "gateway": "arena.providers.gateway",
}


def seat_players(players, game_index, rotate):
    """Per-seat player specs for one game of the series.

    With rotation (a Latin square), the player at index i sits at seat
    P((i + game_index) % 4), so every player visits every seat once per
    seed. Without rotation the declaration order is the seat order.
    """
    count = len(players)
    return [players[((j - game_index) % count) if rotate else j]
            for j in range(count)]


def shuffle_seed(seed_value, game_index, turn_id, seat):
    """Deterministic RNG seed for one (seed, game, turn, seat) shuffle."""
    payload = (f"{SHUFFLE_DOMAIN}:{seed_value}:{game_index}:{turn_id}:"
               f"{seat}").encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def shuffled_candidates(candidates, seed_value, game_index, turn_id, seat):
    """A stable permutation of one candidate list for one turn and seat."""
    order = list(candidates)
    random.Random(shuffle_seed(seed_value, game_index, turn_id,
                               seat)).shuffle(order)
    return order


class ShuffleRecorder:
    """Holds the shown candidate order and the pick for each seat turn."""

    def __init__(self):
        self._entries = {}

    def record_order(self, seat, turn_id, order):
        entry = self._entries.setdefault((turn_id, seat), {})
        entry["turn_id"] = turn_id
        entry["seat"] = seat
        entry["candidate_order"] = list(order)
        entry.setdefault("selected", None)

    def record_selected(self, seat, turn_id, action_id):
        entry = self._entries.setdefault((turn_id, seat), {})
        entry["selected"] = action_id
        entry.setdefault("turn_id", turn_id)
        entry.setdefault("seat", seat)
        entry.setdefault("candidate_order", [])

    def as_list(self, seat_players_labels):
        """Sidecar rows in turn order, with the player label per seat."""
        rows = []
        for entry in self._entries.values():
            seat = entry["seat"]
            rows.append({"turn_id": entry["turn_id"], "seat": seat,
                         "player": seat_players_labels.get(seat),
                         "candidate_order": entry["candidate_order"],
                         "selected": entry["selected"]})
        return rows

    def totals(self, seat_players_labels):
        """Per-player {selected, turns} counts for the position-1 report."""
        out = {}
        for entry in self._entries.values():
            label = seat_players_labels.get(entry["seat"])
            if label is None:
                continue
            agg = out.setdefault(label, {"selected": 0, "turns": 0})
            agg["turns"] += 1
            order = entry.get("candidate_order") or []
            if order and entry.get("selected") == order[0]:
                agg["selected"] += 1
        return out


class ShuffledProvider:
    """One seat provider that sees its candidates in shuffled order.

    The observation (legal actions) keeps the engine order; only the
    candidate list the provider reads is permuted. The inner request in
    `Decision.exchange` shows the shuffled order.
    """

    def __init__(self, inner, recorder, seed_value, game_index, seat):
        self._inner = inner
        self._recorder = recorder
        self._seed_value = seed_value
        self._game_index = game_index
        self._seat = seat
        self.name = inner.name
        self.model = inner.model
        self.timeout_s = inner.timeout_s

    def decide(self, view):
        turn_id = view.observation["turn_id"]
        order = shuffled_candidates(view.candidates, self._seed_value,
                                    self._game_index, turn_id, self._seat)
        self._recorder.record_order(
            self._seat, turn_id, [c["action_id"] for c in order])
        decision = self._inner.decide(dataclasses.replace(view,
                                                          candidates=order))
        self._recorder.record_selected(self._seat, turn_id,
                                       decision.action_id)
        return decision


def budget_stop_reason(budget):
    """Why no further game may start, or None while budget remains."""
    if budget.max_calls and budget.calls >= budget.max_calls:
        return (f"call cap reached ({budget.calls}/{budget.max_calls} "
                f"calls)")
    if budget.max_usd and budget.spent_usd >= budget.max_usd:
        return (f"cost cap reached (${budget.spent_usd:.4f} of "
                f"${budget.max_usd:.2f})")
    return None


def load_series(path):
    """Load and validate a series configuration file.

    Validation reuses `match.make_config`, so provider names, models,
    remote environment keys, budget keys, and the rules file all pass
    through the same checks as a match file.
    """
    with open(path, "r", encoding="utf-8") as fh:
        try:
            doc = json.load(fh)
        except json.JSONDecodeError as exc:
            raise match_mod.MatchConfigError(
                f"{path} is not valid JSON: {exc}") from None
    if not isinstance(doc, dict):
        raise match_mod.MatchConfigError("the series file must be a JSON object")
    unknown = sorted(set(doc) - {"rules", "players", "seeds", "budget",
                                 "rotate_seats", "shuffle_candidates"})
    if unknown:
        raise match_mod.MatchConfigError(
            f"unknown top-level key '{unknown[0]}' (allowed keys: rules, "
            f"players, seeds, budget, rotate_seats, shuffle_candidates)")
    for key in ("rules", "players", "seeds"):
        if key not in doc:
            raise match_mod.MatchConfigError(f"missing key '{key}'")
    players = doc["players"]
    if not isinstance(players, list) or len(players) != 4:
        found = len(players) if isinstance(players, list) else "not a list"
        raise match_mod.MatchConfigError(
            f"'players' must list exactly 4 players, found {found}")
    for i, spec in enumerate(players):
        if not isinstance(spec, dict):
            raise match_mod.MatchConfigError(
                f"player {i + 1} must be an object")
        unknown = sorted(set(spec) - {"provider", "model"})
        if unknown:
            raise match_mod.MatchConfigError(
                f"unknown key '{unknown[0]}' in player {i + 1} "
                f"(allowed keys: provider, model)")
    seeds = doc["seeds"]
    if not isinstance(seeds, list) or not seeds:
        raise match_mod.MatchConfigError(
            "'seeds' must be a non-empty list of integers")
    for seed in seeds:
        if type(seed) is not int:
            raise match_mod.MatchConfigError(
                f"every seed must be an integer, found {seed!r}")
    rotate_seats = doc.get("rotate_seats", True)
    if not isinstance(rotate_seats, bool):
        raise match_mod.MatchConfigError("'rotate_seats' must be a boolean")
    shuffle_candidates = doc.get("shuffle_candidates", True)
    if not isinstance(shuffle_candidates, bool):
        raise match_mod.MatchConfigError(
            "'shuffle_candidates' must be a boolean")
    labels = [report.player_label(spec.get("provider"), spec.get("model"))
              for spec in players]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise match_mod.MatchConfigError(
            f"players must be unique; {duplicates[0]} appears more than once")
    # Full validation of providers, models, env keys, budget, and rules.
    config = match_mod.make_config(doc["rules"], seeds[0], players,
                                   doc.get("budget"))
    return SeriesSpec(rules_path=doc["rules"], rules=config.rules,
                      rules_hash=config.rules_hash, players=players,
                      seeds=seeds, budget=config.budget,
                      rotate_seats=rotate_seats,
                      shuffle_candidates=shuffle_candidates)


class SeriesSpec:
    """A validated series configuration."""

    def __init__(self, rules_path, rules, rules_hash, players, seeds,
                 budget, rotate_seats, shuffle_candidates):
        self.rules_path = rules_path
        self.rules = rules
        self.rules_hash = rules_hash
        self.players = players
        self.seeds = seeds
        self.budget = budget
        self.rotate_seats = rotate_seats
        self.shuffle_candidates = shuffle_candidates

    @property
    def has_remote_players(self):
        return any(spec.get("provider") in REMOTE_PROVIDERS
                   for spec in self.players)

    @property
    def labels(self):
        return [report.player_label(spec.get("provider"), spec.get("model"))
                for spec in self.players]


def estimate_series(spec):
    """Estimated games, calls, and cost for one series, from price tables."""
    games = len(spec.seeds) * GAMES_PER_SEED
    remote = [spec for spec in spec.players
              if spec.get("provider") in REMOTE_PROVIDERS]
    calls_per_game = EST_TURNS_PER_GAME * len(remote) // GAMES_PER_SEED
    per_player = {}
    total_cost = 0.0
    if remote:
        calls_each = games * (EST_TURNS_PER_GAME / GAMES_PER_SEED)
        for player in remote:
            rate = _rate_for(player)
            cost = (calls_each * EST_INPUT_TOKENS_PER_CALL / 1_000_000
                    * rate)
            label = report.player_label(player.get("provider"),
                                        player.get("model"))
            per_player[label] = {"calls": round(calls_each),
                                 "cost_usd": round(cost, 4)}
            total_cost += cost
    return {"games": games, "calls": games * calls_per_game,
            "cost_usd": round(total_cost, 4), "per_player": per_player,
            "assumptions": {"turns_per_game": EST_TURNS_PER_GAME,
                            "input_tokens_per_call":
                                EST_INPUT_TOKENS_PER_CALL}}


def _rate_for(player):
    """USD per million input tokens for one player, from its price table."""
    provider = player.get("provider")
    module = importlib.import_module(_PRICING_MODULES[provider])
    pricing = getattr(module, "PRICING", {})
    model = player.get("model")
    if model in pricing:
        return pricing[model]
    return pricing.get("*", 0.0)


def run_series(spec, run_base=None, provider_factory=None, hooks=None,
               console=None, stream=False):
    """Play every seed four times with rotated seats under one budget.

    All games share `spec.budget`; `run_match` mutates it, so a cap
    reached mid-game stops that game (it counts as incomplete) and no
    further game starts. Returns the series summary document, which is
    also written to <series dir>/summary.json.
    """
    started = time.monotonic()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    base = run_base or os.path.join(ARENA_DIR, "runs")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    series_id = f"{stamp}-{spec.rules_hash[:8]}-series"
    series_dir = os.path.join(base, series_id)
    os.makedirs(series_dir)
    planned = [(seed_index, seed, game_index)
               for seed_index, seed in enumerate(spec.seeds)
               for game_index in range(GAMES_PER_SEED)]
    entries = []
    shuffle_totals = {}
    for seed_index, seed, game_index in planned:
        seat_order = seat_players(spec.players, game_index, spec.rotate_seats)
        seat_labels = {SEATS[j]: report.player_label(
            spec_.get("provider"), spec_.get("model"))
            for j, spec_ in enumerate(seat_order)}
        stop = budget_stop_reason(spec.budget)
        if stop:
            entries.append({"seed": seed, "seed_index": seed_index,
                            "game": game_index, "status": "skipped",
                            "reason": stop, "run_dir": None,
                            "seat_players": seat_labels})
            continue
        seat_specs = [{"provider": spec_.get("provider"),
                       "model": spec_.get("model")}
                      for spec_ in seat_order]
        config = match_mod.make_config(spec.rules_path, seed, seat_specs)
        # One shared mutable Budget accumulates over the whole series.
        config.budget = spec.budget
        run_dir = os.path.join(series_dir, f"seed-{seed}-game-{game_index}")
        recorder = ShuffleRecorder()
        remote_seats = {SEATS[j] for j, spec_ in enumerate(seat_order)
                        if spec_.get("provider") in REMOTE_PROVIDERS}
        game_hooks = hooks
        if console is not None and stream:
            from arena.ui import MatchStreamer

            game_hooks = MatchStreamer(console, remote_seats)
            console.print(f"[bold]game {len(entries) + 1}/{len(planned)}[/bold]"
                          f" seed {seed} game {game_index}: "
                          + ", ".join(f"{seat}={seat_labels[seat]}"
                                      for seat in SEATS))
        factory = provider_factory
        inner_factory = None
        if factory is None:
            inner_factory = match_mod._default_provider_factory(
                config, match_mod.game_id(config))

        def build(seat_config):
            if inner_factory is not None:
                provider = inner_factory(seat_config)
            else:
                provider = provider_factory(seat_config)
            if spec.shuffle_candidates \
                    and seat_config.seat in remote_seats:
                return ShuffledProvider(provider, recorder, seed,
                                        game_index, seat_config.seat)
            return provider

        factory = build
        result = match_mod.run_match(config, run_dir, hooks=game_hooks,
                                     provider_factory=factory)
        game_log = report.parse_game_log(os.path.join(run_dir, "match.jsonl"))
        missed = report.count_missed_interventions(game_log["decisions"],
                                                   game_log["result"])
        per_seat = game_log["per_seat"]
        for seat, count in missed.items():
            if seat in per_seat:
                per_seat[seat]["missed_interventions"] = count
        for label, totals in recorder.totals(seat_labels).items():
            acc = shuffle_totals.setdefault(label,
                                            {"selected": 0, "turns": 0})
            acc["selected"] += totals["selected"]
            acc["turns"] += totals["turns"]
        _write_sidecar(series_dir, series_id, spec, seed, seed_index,
                       game_index, seat_labels, recorder)
        if console is not None and stream:
            _print_game_result(console, seat_labels, result)
        entries.append({"seed": seed, "seed_index": seed_index,
                        "game": game_index, "status": "played",
                        "run_dir": str(run_dir), "seat_players": seat_labels,
                        "result": {key: result.get(key) for key in
                                   ("outcome", "winner", "end_reason",
                                    "incomplete", "incomplete_reason",
                                    "total_turns", "total_rounds")},
                        "per_seat": per_seat})
        if result.get("end_reason") == "interrupted":
            for rest_seed_index, rest_seed, rest_game in \
                    planned[len(entries):]:
                rest_labels = {SEATS[j]: report.player_label(
                    spec_.get("provider"), spec_.get("model"))
                    for j, spec_ in enumerate(seat_players(
                        spec.players, rest_game, spec.rotate_seats))}
                entries.append({"seed": rest_seed,
                                "seed_index": rest_seed_index,
                                "game": rest_game, "status": "skipped",
                                "reason": "interrupted by the user",
                                "run_dir": None,
                                "seat_players": rest_labels})
            break
    meta = {"series_id": series_id, "rules_path": spec.rules_path,
            "rules_hash": spec.rules_hash,
            "rotate_seats": spec.rotate_seats,
            "shuffle_candidates": spec.shuffle_candidates,
            "budget": {"max_calls": spec.budget.max_calls,
                       "max_usd": spec.budget.max_usd,
                       "calls": spec.budget.calls,
                       "spent_usd": round(spec.budget.spent_usd, 6)},
            "started_utc": started_utc,
            "duration_s": round(time.monotonic() - started, 1)}
    summary = report.build_summary(spec.players, spec.seeds, entries,
                                   shuffle_totals, meta)
    summary_path = os.path.join(series_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    return summary


def _write_sidecar(series_dir, series_id, spec, seed, seed_index,
                   game_index, seat_labels, recorder):
    """Write the per-game candidate-order sidecar next to match.jsonl."""
    game_dir = os.path.join(series_dir, f"seed-{seed}-game-{game_index}")
    doc = {"series_id": series_id, "seed": seed,
           "seed_index": seed_index, "game": game_index,
           "shuffle_candidates": spec.shuffle_candidates,
           "seat_players": seat_labels, "turns": recorder.as_list(seat_labels)}
    path = os.path.join(game_dir, "series-game.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)


def _print_game_result(console, seat_labels, result):
    if result.get("incomplete"):
        console.print(f"[red]INCOMPLETE[/red] "
                      f"{result.get('incomplete_reason', '')}")
    elif result.get("winner"):
        winner = seat_labels.get(result["winner"], result["winner"])
        console.print(f"[green]{winner} wins[/green] "
                      f"({result.get('end_reason', '')})")
    else:
        console.print(f"Draw ({result.get('end_reason', '')})")


# ---------------------------------------------------------------------------
# Tactical fixtures
# ---------------------------------------------------------------------------

def load_fixtures(directory=FIXTURE_DIR):
    """Load the frozen tactical fixtures; each needs observation, candidates,
    and correct."""
    fixtures = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(path, "r", encoding="utf-8") as fh:
            try:
                doc = json.load(fh)
            except json.JSONDecodeError as exc:
                raise match_mod.MatchConfigError(
                    f"{path} is not valid JSON: {exc}") from None
        missing = [key for key in ("observation", "candidates", "correct")
                   if key not in doc]
        if missing:
            raise match_mod.MatchConfigError(
                f"{path} is missing {', '.join(missing)}")
        doc["_path"] = path
        doc.setdefault("name", os.path.splitext(os.path.basename(path))[0])
        fixtures.append(doc)
    return fixtures


def fixture_view(doc, rules):
    """Build the TurnView for a frozen observation, with a rebuilt shortlist."""
    obs = doc["observation"]
    candidates = adapter.candidates(obs, rules)[0]
    view = TurnView(observation=obs,
                    projection=adapter.projection(obs, rules),
                    candidates=candidates, rules=rules)
    return view, candidates


def run_fixtures(providers, fixtures, rules_by_path):
    """Ask each provider once per fixture; no retries, no budget.

    providers: built provider objects. rules_by_path: cache mapping a
    fixture's rules path to loaded rules. Returns one row per provider
    with per-fixture results and drift notes.
    """
    rows = []
    for provider in providers:
        row = {"provider": provider.name, "model": provider.model,
               "fixtures": []}
        for doc in fixtures:
            rules_path = doc.get("rules", DEFAULT_FIXTURE_RULES)
            if rules_path not in rules_by_path:
                resolved = match_mod._resolve_rules_path(rules_path)
                from arena.rules_loader import load_rules_strict

                rules_by_path[rules_path] = load_rules_strict(resolved)
            rules = rules_by_path[rules_path]
            view, rebuilt = fixture_view(doc, rules)
            rebuilt_ids = [c["action_id"] for c in rebuilt]
            drift = rebuilt_ids != [c["action_id"] for c in doc["candidates"]]
            try:
                decision = provider.decide(view)
                chosen, error = decision.action_id, None
            except ProviderError as exc:
                chosen, error = None, str(exc)
            row["fixtures"].append({
                "name": doc.get("name"),
                "action_id": chosen,
                "correct": chosen in set(doc["correct"]) if chosen else False,
                "error": error,
                "candidates_drift": drift})
        row["score"] = sum(1 for item in row["fixtures"] if item["correct"])
        row["total"] = len(row["fixtures"])
        rows.append(row)
    return rows


def fixture_providers(env, include_bots=False):
    """The (provider, model) pairs that --fixtures would ask, no building."""
    from arena.providers import available_remote_providers

    pairs = [(name, default_model(name))
             for name in available_remote_providers(env)]
    if include_bots:
        pairs.extend((name, None) for name in local_provider_names())
    return pairs
