# ABOUTME: Series runner, report metric, and tactical fixture tests.
# ABOUTME: Everything runs offline with local bots, test doubles, and frozen data.

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arena import cli, report, series as series_mod
from arena import match as match_mod
from arena.providers import Decision, ProviderError

ARENA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ARENA_DIR, "..", "rules",
                          "imperial-rivals-v0.10.2.json")
SHIPPED_SERIES = os.path.join(ARENA_DIR, "matches", "series-four-way.json")
FIXTURE_DIR = series_mod.FIXTURE_DIR
REMOTE_ENV = {
    "OPENAI_API_KEY": "test",
    "TYPESAFE_API_KEY": "test",
    "CLOUDFLARE_API_TOKEN": "test",
    "CLOUDFLARE_ACCOUNT_ID": "test",
    "PERPLEXITY_API_KEY": "test",
    "AI_GATEWAY_API_KEY": "test",
}


def tiny_rules(tmp_path, palace_rounds=1, succession_rounds=1):
    """A valid rules file with short phases, so offline games finish fast."""
    with open(RULES_PATH, "r", encoding="utf-8") as fh:
        rules = json.load(fh)
    rules["palace"]["max_rounds"] = palace_rounds
    rules["succession"]["max_rounds"] = succession_rounds
    # Every treasure face up from turn one, so the bot policies never
    # inspect an unrevealed district (same trick as test_match).
    rules["treasures"]["start_face_up"] = 6
    path = tmp_path / "tiny_rules.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    return str(path)


def bot_players():
    return [{"provider": "tactical"}, {"provider": "balanced"},
            {"provider": "greedy"}, {"provider": "random"}]


def write_series(tmp_path, rules_path, players=None, seeds=None,
                 budget=None, extra=None):
    doc = {"rules": rules_path, "players": players or bot_players(),
           "seeds": seeds if seeds is not None else [7],
           "rotate_seats": True, "shuffle_candidates": True}
    if budget is not None:
        doc["budget"] = budget
    if extra:
        doc.update(extra)
    path = tmp_path / "series.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


class FakeSeat:
    """A test double for a remote seat: first legal action, one unit of cost."""

    name = "pplx"
    model = "double"
    timeout_s = 0.0

    def __init__(self):
        self.calls = 0

    def decide(self, view):
        self.calls += 1
        return Decision(action_id=view.observation["legal_actions"][0]
                        ["action_id"],
                        latency_ms=1.0, cost_usd=0.01, reason="fake")


def fake_factory(seat_configs):
    built = []

    def build(seat_config):
        provider = FakeSeat()
        built.append((seat_config.seat, provider))
        return provider

    build.built = built
    return build


# ---------------------------------------------------------------------------
# Seat rotation
# ---------------------------------------------------------------------------

def test_seat_rotation_is_a_latin_square():
    players = [{"provider": f"bot{i}"} for i in range(4)]
    seen = {f"P{j}": [] for j in range(4)}
    for game in range(4):
        order = series_mod.seat_players(players, game, rotate=True)
        assert len(order) == 4
        for j, spec in enumerate(order):
            seen[f"P{j}"].append(spec["provider"])
    for seat, visitors in seen.items():
        assert sorted(visitors) == sorted(p["provider"] for p in players), \
            f"{seat} must host every player exactly once"


def test_seat_rotation_matches_the_formula():
    players = [{"provider": f"bot{i}"} for i in range(4)]
    for game in range(4):
        order = series_mod.seat_players(players, game, rotate=True)
        for i, spec in enumerate(players):
            assert order[(i + game) % 4] is spec


def test_seat_rotation_disabled_keeps_declaration_order():
    players = [{"provider": f"bot{i}"} for i in range(4)]
    for game in range(4):
        order = series_mod.seat_players(players, game, rotate=False)
        assert [spec["provider"] for spec in order] == \
            [p["provider"] for p in players]


# ---------------------------------------------------------------------------
# Series file validation
# ---------------------------------------------------------------------------

def test_load_series_accepts_a_valid_file(tmp_path, monkeypatch):
    for var, value in REMOTE_ENV.items():
        monkeypatch.setenv(var, value)
    path = write_series(
        tmp_path, "../rules/imperial-rivals-v0.10.2.json",
        players=[{"provider": "clef", "model": "clef-flash"},
                 {"provider": "pplx", "model": "pplx-decider-v1.3"},
                 {"provider": "gateway", "model": "nace-ai/drex-v2.0"},
                 {"provider": "gateway", "model": "baseten/elephant-1"}],
        seeds=[42, 43, 44, 45, 46],
        budget={"max_calls": 2200, "max_usd": 1.0})
    spec = series_mod.load_series(path)
    assert spec.seeds == [42, 43, 44, 45, 46]
    assert spec.budget.max_calls == 2200
    assert spec.budget.max_usd == 1.0
    assert spec.rotate_seats and spec.shuffle_candidates
    assert spec.has_remote_players
    assert spec.labels == ["clef/clef-flash", "pplx/pplx-decider-v1.3",
                           "gateway/nace-ai/drex-v2.0",
                           "gateway/baseten/elephant-1"]


def test_shipped_series_file_validates(monkeypatch):
    for var, value in REMOTE_ENV.items():
        monkeypatch.setenv(var, value)
    spec = series_mod.load_series(SHIPPED_SERIES)
    assert len(spec.seeds) == 3
    assert spec.has_remote_players
    assert spec.labels == ["clef/clef-flash", "pplx/pplx-decider-v1.3",
                           "clef/clef", "pplx/pplx-decider-flash-v1.3"]


def test_load_series_rejects_unknown_keys(tmp_path, monkeypatch):
    for var, value in REMOTE_ENV.items():
        monkeypatch.setenv(var, value)
    path = write_series(tmp_path, RULES_PATH, extra={"surprise": 1})
    with pytest.raises(match_mod.MatchConfigError, match="unknown top-level"):
        series_mod.load_series(path)


def test_load_series_requires_exactly_four_players(tmp_path):
    path = write_series(tmp_path, RULES_PATH, players=bot_players()[:3])
    with pytest.raises(match_mod.MatchConfigError, match="exactly 4"):
        series_mod.load_series(path)


def test_load_series_requires_seeds(tmp_path):
    path = write_series(tmp_path, RULES_PATH, seeds=[])
    with pytest.raises(match_mod.MatchConfigError, match="non-empty"):
        series_mod.load_series(path)
    path = write_series(tmp_path, RULES_PATH, seeds=[7, "8"])
    with pytest.raises(match_mod.MatchConfigError, match="integer"):
        series_mod.load_series(path)


def test_load_series_rejects_duplicate_players(tmp_path):
    players = [{"provider": "tactical"}, {"provider": "tactical"},
               {"provider": "greedy"}, {"provider": "random"}]
    path = write_series(tmp_path, RULES_PATH, players=players)
    with pytest.raises(match_mod.MatchConfigError, match="unique"):
        series_mod.load_series(path)


def test_load_series_requires_env_for_remote_players(tmp_path, monkeypatch):
    for var in REMOTE_ENV:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test")
    players = [{"provider": "pplx", "model": "pplx-decider-v1.3"},
               {"provider": "clef", "model": "clef-flash"},
               {"provider": "gateway", "model": "nace-ai/drex-v2.0"},
               {"provider": "greedy"}]
    path = write_series(tmp_path, RULES_PATH, players=players)
    with pytest.raises(match_mod.MatchConfigError,
                       match="CLOUDFLARE|AI_GATEWAY"):
        series_mod.load_series(path)


def test_load_series_rejects_non_boolean_flags(tmp_path):
    path = write_series(tmp_path, RULES_PATH, extra={"rotate_seats": "yes"})
    with pytest.raises(match_mod.MatchConfigError, match="boolean"):
        series_mod.load_series(path)


# ---------------------------------------------------------------------------
# Candidate shuffle
# ---------------------------------------------------------------------------

def test_shuffle_is_deterministic_and_a_permutation():
    candidates = [{"action_id": f"a{i:04d}"} for i in range(1, 17)]
    first = series_mod.shuffled_candidates(candidates, 42, 0, 5, "P1")
    second = series_mod.shuffled_candidates(candidates, 42, 0, 5, "P1")
    assert first == second
    assert {c["action_id"] for c in first} == \
        {c["action_id"] for c in candidates}
    assert len(first) == len(candidates)
    assert candidates == [{"action_id": f"a{i:04d}"} for i in range(1, 17)], \
        "the input list must stay in engine order"


def test_shuffle_varies_with_turn_and_seat():
    candidates = [{"action_id": f"a{i:04d}"} for i in range(1, 17)]
    orders = set()
    for turn in range(1, 31):
        for seat in ("P0", "P1"):
            order = series_mod.shuffled_candidates(candidates, 42, 0, turn,
                                                   seat)
            orders.add(tuple(c["action_id"] for c in order))
    assert len(orders) > 1, "different turns and seats must reshuffle"
    base = tuple(c["action_id"] for c in candidates)
    assert base not in orders or len(orders) > 10, \
        "the engine order should not dominate the sample"


def test_shuffle_seed_depends_on_every_input():
    keys = {series_mod.shuffle_seed(42, 0, 5, "P1")}
    keys.add(series_mod.shuffle_seed(43, 0, 5, "P1"))
    keys.add(series_mod.shuffle_seed(42, 1, 5, "P1"))
    keys.add(series_mod.shuffle_seed(42, 0, 6, "P1"))
    keys.add(series_mod.shuffle_seed(42, 0, 5, "P2"))
    assert len(keys) == 5


def test_shuffled_provider_wraps_the_view_and_records_the_pick():
    seen = {}

    class Inner:
        name = "pplx"
        model = "double"
        timeout_s = 0.0

        def decide(self, view):
            seen["candidates"] = view.candidates
            seen["observation"] = view.observation
            return Decision(action_id=view.candidates[0]["action_id"])

    candidates = [{"action_id": f"a{i:04d}"} for i in range(1, 17)]
    observation = {"turn_id": 5}
    view = series_mod.TurnView(observation=observation, projection={},
                               candidates=candidates, rules={})
    recorder = series_mod.ShuffleRecorder()
    provider = series_mod.ShuffledProvider(Inner(), recorder, 42, 0, "P3")
    decision = provider.decide(view)
    assert provider.name == "pplx" and provider.model == "double"
    assert [c["action_id"] for c in seen["candidates"]] != \
        [c["action_id"] for c in candidates]
    assert seen["observation"] is observation
    assert decision.action_id == seen["candidates"][0]["action_id"]
    totals = recorder.totals({"P3": "pplx/double"})
    assert totals == {"pplx/double": {"selected": 1, "turns": 1}}
    rows = recorder.as_list({"P3": "pplx/double"})
    assert rows[0]["seat"] == "P3" and rows[0]["turn_id"] == 5
    assert rows[0]["player"] == "pplx/double"
    assert rows[0]["selected"] == rows[0]["candidate_order"][0]


def test_shuffle_recorder_overwrites_retries_for_one_turn():
    recorder = series_mod.ShuffleRecorder()
    recorder.record_order("P1", 5, ["a0002", "a0001"])
    recorder.record_selected("P1", 5, "a0002")
    recorder.record_order("P1", 5, ["a0001", "a0002"])
    recorder.record_selected("P1", 5, "a0001")
    rows = recorder.as_list({"P1": "x"})
    assert len(rows) == 1
    assert rows[0]["candidate_order"] == ["a0001", "a0002"]
    assert rows[0]["selected"] == "a0001"


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def test_budget_stop_reason():
    budget = match_mod.Budget(max_calls=10, max_usd=1.0, calls=10,
                              spent_usd=0.2)
    assert "call cap" in series_mod.budget_stop_reason(budget)
    budget = match_mod.Budget(max_calls=10, max_usd=1.0, calls=3,
                              spent_usd=1.0)
    assert "cost cap" in series_mod.budget_stop_reason(budget)
    budget = match_mod.Budget(max_calls=10, max_usd=1.0, calls=3,
                              spent_usd=0.5)
    assert series_mod.budget_stop_reason(budget) is None
    assert series_mod.budget_stop_reason(match_mod.Budget()) is None


def _remote_series(tmp_path, monkeypatch, budget, rules_path=None):
    # Full rules keep a game long enough that the call cap trips mid-game;
    # pass tiny rules when the game is cut short anyway.
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test")
    players = [{"provider": "pplx", "model": "double"},
               {"provider": "greedy"}, {"provider": "random"},
               {"provider": "tactical"}]
    return write_series(tmp_path, rules_path or RULES_PATH, players=players,
                        seeds=[11], budget=budget)


def test_series_budget_stop_marks_games_skipped(tmp_path, monkeypatch):
    path = _remote_series(tmp_path, monkeypatch,
                          {"max_calls": 6, "max_usd": 0.0})
    spec = series_mod.load_series(path)
    summary = series_mod.run_series(spec, run_base=str(tmp_path / "runs"),
                                    provider_factory=fake_factory(None),
                                    hooks=object())
    assert summary["games"]["played"] == 1
    assert summary["games"]["skipped"] == 3
    assert summary["games"]["incomplete"] == 1
    assert summary["budget"]["calls"] == 6
    assert summary["budget"]["spent_usd"] == pytest.approx(0.06)
    skipped = [entry for entry in summary["game_list"]
               if entry["status"] == "skipped"]
    assert [entry["game"] for entry in skipped] == [1, 2, 3]
    assert all("cap reached" in entry["reason"] for entry in skipped)
    played = summary["game_list"][0]
    assert played["result"]["incomplete"] is True


def test_series_accumulates_cost_and_logs_shuffle(tmp_path, monkeypatch):
    path = _remote_series(tmp_path, monkeypatch,
                          {"max_calls": 0, "max_usd": 0.0})
    spec = series_mod.load_series(path)
    summary = series_mod.run_series(spec, run_base=str(tmp_path / "runs"),
                                    provider_factory=fake_factory(None),
                                    hooks=object())
    assert summary["games"]["played"] == 4
    assert summary["games"]["skipped"] == 0
    label = "pplx/double"
    stat = summary["players"][label]
    assert stat["games"] == 4
    assert stat["calls"] == summary["budget"]["calls"]
    assert stat["cost_usd"] == pytest.approx(stat["calls"] * 0.01, abs=1e-6)
    assert stat["position1"]["turns"] == stat["calls"]
    assert stat["position1"]["selected"] >= 0
    assert summary["total_cost_usd"] == pytest.approx(
        summary["budget"]["spent_usd"], abs=1e-6)
    game_dir = summary["game_list"][0]["run_dir"]
    sidecar = json.load(open(os.path.join(game_dir, "series-game.json"),
                             encoding="utf-8"))
    assert sidecar["seed"] == 11 and sidecar["game"] == 0
    assert sidecar["seat_players"]["P0"] == label
    assert sidecar["turns"], "remote turns must land in the sidecar"
    match_lines = [json.loads(line) for line in
                   open(os.path.join(game_dir, "match.jsonl"),
                        encoding="utf-8")]
    decisions = {(line["turn_id"], line["seat"]): line
                 for line in match_lines if line["type"] == "decision"}
    orders = set()
    for row in sidecar["turns"]:
        line = decisions[(row["turn_id"], row["seat"])]
        canonical = [c["action_id"] for c in line["candidates"]]
        assert sorted(row["candidate_order"]) == sorted(canonical)
        assert row["selected"] == line["action_id"]
        orders.add(tuple(row["candidate_order"]))
    assert len(orders) > 1, "the shown order must vary across turns"


def test_series_with_bots_writes_summary_and_sidecar(tmp_path):
    rules_path = tiny_rules(tmp_path)
    path = write_series(tmp_path, rules_path, seeds=[7])
    spec = series_mod.load_series(path)
    summary = series_mod.run_series(spec, run_base=str(tmp_path / "runs"))
    assert summary["games"]["played"] == 4
    assert summary["games"]["incomplete"] == 0
    assert summary["games"]["skipped"] == 0
    for label, stat in summary["players"].items():
        assert stat["games"] == 4
        assert stat["win_rate"] is not None
        assert stat["win_rate_wilson_95"][0] <= stat["win_rate"] \
            <= stat["win_rate_wilson_95"][1]
        assert stat["position1"]["turns"] == 0, \
            "bots do not consume the candidate list"
    wins = sum(s["wins"] for s in summary["players"].values())
    drawn = sum(1 for e in summary["game_list"]
                if e["result"]["outcome"] == "draw")
    incomplete = sum(1 for e in summary["game_list"]
                     if e["result"]["outcome"] == "incomplete")
    assert wins + drawn + incomplete == 4
    series_root = os.path.dirname(summary["game_list"][0]["run_dir"])
    assert os.path.exists(os.path.join(series_root, "summary.json"))
    for index, entry in enumerate(summary["game_list"]):
        assert os.path.exists(os.path.join(entry["run_dir"], "match.jsonl"))
        assert os.path.exists(os.path.join(entry["run_dir"], "engine"))
        sidecar = json.load(open(os.path.join(entry["run_dir"],
                                              "series-game.json"),
                                 encoding="utf-8"))
        assert sidecar["turns"] == []
        players = bot_players()
        for seat, label in sidecar["seat_players"].items():
            seat_index = int(seat[1:])
            player_index = (seat_index - index) % 4
            assert label == report.player_label(
                players[player_index]["provider"], None)


def test_series_marks_remaining_games_skipped_after_an_interrupt(
        tmp_path, monkeypatch):
    path = _remote_series(tmp_path, monkeypatch,
                          {"max_calls": 0, "max_usd": 0.0})
    spec = series_mod.load_series(path)

    class InterruptingSeat(FakeSeat):
        def decide(self, view):
            raise KeyboardInterrupt

    def factory(seat_config):
        if seat_config.seat == "P0":
            return InterruptingSeat()
        return FakeSeat()

    summary = series_mod.run_series(
        spec, run_base=str(tmp_path / "runs"), provider_factory=factory,
        hooks=object())
    assert summary["games"]["played"] == 1
    assert summary["games"]["skipped"] == 3
    assert all(entry["reason"] == "interrupted by the user"
               for entry in summary["game_list"]
               if entry["status"] == "skipped")


# ---------------------------------------------------------------------------
# Missed interventions
# ---------------------------------------------------------------------------

def decision_line(seat, action_id, pending, legal_actions):
    return {"seat": seat, "action_id": action_id,
            "observation": {"pending_claim": pending,
                            "legal_actions": legal_actions}}


def duel(action_id, target):
    return {"action_id": action_id, "kind": "duel", "target": target}


def test_missed_intervention_counts_a_failed_cancel():
    pending = {"player": "P2", "claim_id": 7}
    legal = [duel("a0001", "P2"), {"action_id": "a0002", "kind": "move"}]
    decisions = [decision_line("P1", "a0002", pending, legal)]
    result = {"end_reason": "survived_window", "winner": "P2"}
    assert report.count_missed_interventions(decisions, result) == {"P1": 1}


def test_missed_intervention_ignores_a_taken_duel():
    pending = {"player": "P2", "claim_id": 7}
    legal = [duel("a0001", "P2"), {"action_id": "a0002", "kind": "move"}]
    decisions = [decision_line("P1", "a0001", pending, legal)]
    result = {"end_reason": "survived_window", "winner": "P2"}
    assert report.count_missed_interventions(decisions, result) == {}


def test_missed_intervention_ignores_other_end_reasons_and_claims():
    pending = {"player": "P2", "claim_id": 7}
    legal = [duel("a0001", "P2"), {"action_id": "a0002", "kind": "move"}]
    decisions = [decision_line("P1", "a0002", pending, legal)]
    for end_reason in ("acclamation", "succession_timeout", None):
        result = {"end_reason": end_reason, "winner": "P2"}
        assert report.count_missed_interventions(decisions, result) == {}
    result = {"end_reason": "survived_window", "winner": "P1"}
    assert report.count_missed_interventions(decisions, result) == {}
    # A later claim by the same claimant won; the older pending claim at
    # P1's turn was not the winning claim, so only P3's turn counts.
    result = {"end_reason": "survived_window", "winner": "P2"}
    later = [decision_line("P3", "a0009",
                           {"player": "P2", "claim_id": 9}, legal)]
    counts = report.count_missed_interventions(decisions + later, result)
    assert counts == {"P3": 1}, \
        "only the winning claim counts; the superseded claim must not"


def test_missed_intervention_ignores_turns_without_a_counter_duel():
    pending = {"player": "P2", "claim_id": 7}
    legal = [{"action_id": "a0001", "kind": "move"}]
    decisions = [decision_line("P1", "a0001", pending, legal)]
    result = {"end_reason": "survived_window", "winner": "P2"}
    assert report.count_missed_interventions(decisions, result) == {}
    decisions = [decision_line("P2", "a0001", pending, legal)]
    assert report.count_missed_interventions(decisions, result) == {}, \
        "the claimant's own turn is not a missed intervention"


def test_missed_interventions_surface_in_a_series(tmp_path):
    rules_path = tiny_rules(tmp_path)
    path = write_series(tmp_path, rules_path, seeds=[7])
    spec = series_mod.load_series(path)
    summary = series_mod.run_series(spec, run_base=str(tmp_path / "runs"))
    for stat in summary["players"].values():
        assert isinstance(stat["missed_interventions"], int)
        assert stat["missed_interventions"] >= 0


# ---------------------------------------------------------------------------
# Wilson interval and percentiles
# ---------------------------------------------------------------------------

def test_wilson_interval_matches_published_values():
    assert report.wilson_interval(1, 10) == (0.0179, 0.4042)
    assert report.wilson_interval(8, 10) == (0.4902, 0.9433)


def test_wilson_interval_edges_and_properties():
    assert report.wilson_interval(0, 0) is None
    low, high = report.wilson_interval(0, 20)
    assert low == 0.0 and 0 < high < 0.2
    low, high = report.wilson_interval(20, 20)
    assert high == 1.0 and 0.8 < low < 1.0
    z = report.WILSON_Z_95
    for total in range(1, 40):
        for wins in range(total + 1):
            low, high = report.wilson_interval(wins, total, z)
            p = wins / total
            assert 0.0 <= low <= high <= 1.0
            assert low - 1e-3 <= p <= high + 1e-3
            width = high - low
            assert width < 1.0 + 1e-9


def test_percentile_interpolates_linearly():
    data = list(range(1, 101))
    assert report.percentile(data, 0.5) == 50.5
    assert report.percentile(data, 0.95) == 95.05
    assert report.percentile([10], 0.95) == 10
    assert report.percentile([], 0.5) is None
    from statistics import median, quantiles

    data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    assert report.percentile(data, 0.5) == median(data)
    expected = quantiles(data, n=20, method="inclusive")[-1]
    assert report.percentile(data, 0.95) == pytest.approx(expected)


def test_summary_latency_and_wilson_shapes(tmp_path):
    rules_path = tiny_rules(tmp_path)
    path = write_series(tmp_path, rules_path, seeds=[7])
    spec = series_mod.load_series(path)
    summary = series_mod.run_series(spec, run_base=str(tmp_path / "runs"))
    for stat in summary["players"].values():
        assert set(stat["latency_ms"]) == {"median", "p95"}
        assert stat["latency_ms"]["median"] is not None
        assert stat["latency_ms"]["p95"] >= stat["latency_ms"]["median"]
        wins, games = stat["wins"], stat["games"]
        assert report.wilson_interval(wins, games) == \
            stat["win_rate_wilson_95"]


# ---------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------

def test_estimate_uses_the_price_tables(monkeypatch):
    for var, value in REMOTE_ENV.items():
        monkeypatch.setenv(var, value)
    spec = series_mod.load_series(SHIPPED_SERIES)
    estimate = series_mod.estimate_series(spec)
    assert estimate["games"] == 12
    assert estimate["calls"] == 1320
    from arena.providers import clef, pplx

    rates = (clef.PRICING["clef-flash"] + clef.PRICING["clef"]
             + pplx.PRICING["pplx-decider-v1.3"]
             + pplx.PRICING["pplx-decider-flash-v1.3"])
    calls_each = 12 * (series_mod.EST_TURNS_PER_GAME / 4)
    tokens = calls_each * series_mod.EST_INPUT_TOKENS_PER_CALL
    expected = rates * tokens / 1_000_000
    assert estimate["cost_usd"] == pytest.approx(round(expected, 4))
    assert estimate["cost_usd"] < spec.budget.max_usd, \
        "the shipped series must fit its own budget"
    assert set(estimate["per_player"]) == set(spec.labels)


def test_estimate_ignores_local_players():
    spec = type("S", (), {"players": bot_players(), "seeds": [1, 2]})()
    estimate = series_mod.estimate_series(spec)
    assert estimate["calls"] == 0
    assert estimate["cost_usd"] == 0.0
    assert estimate["games"] == 8
    assert estimate["per_player"] == {}


# ---------------------------------------------------------------------------
# Tactical fixtures
# ---------------------------------------------------------------------------

HIDDEN_KEYS = ("faction_sites", "district_equipment")


def test_fixtures_are_frozen_and_public():
    fixtures = series_mod.load_fixtures()
    assert len(fixtures) == 3
    names = {doc["name"] for doc in fixtures}
    assert names == {"cancel-winning-claim", "proclaim-legal",
                     "gain-support-affordable"}

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in HIDDEN_KEYS, \
                    f"{path}.{key} is engine hidden state"
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    for doc in fixtures:
        walk(doc, doc["name"])
        card_spaces = doc["observation"]["board"].get("card_spaces")
        if card_spaces is not None:
            assert set(card_spaces) <= {"candidates", "revealed"}
        rebuilt = series_mod.fixture_view(doc, _fixture_rules(doc))[1]
        assert [c["action_id"] for c in rebuilt] == \
            [c["action_id"] for c in doc["candidates"]], \
            f"{doc['name']}: the frozen shortlist drifted from the engine"
        candidate_ids = {c["action_id"] for c in doc["candidates"]}
        assert set(doc["correct"]) <= candidate_ids


def _fixture_rules(doc):
    from arena.rules_loader import load_rules_strict

    return load_rules_strict(match_mod._resolve_rules_path(doc["rules"]))


def test_cancel_fixture_is_a_last_round_claim():
    doc = next(f for f in series_mod.load_fixtures()
               if f["name"] == "cancel-winning-claim")
    obs = doc["observation"]
    pending = obs["pending_claim"]
    assert pending and pending["player"] != obs["active_player"]
    window = obs["progress"]["claim_window_rounds"]
    assert window and obs["round"] - pending["round"] == window
    for action_id in doc["correct"]:
        action = next(a for a in obs["legal_actions"]
                      if a["action_id"] == action_id)
        assert action["kind"] == "duel"
        assert action["target"] == pending["player"]


def test_proclaim_and_support_fixtures_match_their_kinds():
    fixtures = {doc["name"]: doc for doc in series_mod.load_fixtures()}
    proclaim = fixtures["proclaim-legal"]["observation"]
    assert proclaim["phase"] == 2 and proclaim["pending_claim"] is None
    kinds = {a["kind"]: a["action_id"] for a in proclaim["legal_actions"]}
    assert set(fixtures["proclaim-legal"]["correct"]) <= {kinds["proclaim"]}
    support = fixtures["gain-support-affordable"]["observation"]
    assert support["phase"] == 2
    for action_id in fixtures["gain-support-affordable"]["correct"]:
        action = next(a for a in support["legal_actions"]
                      if a["action_id"] == action_id)
        assert action["kind"] == "gain_support"
        assert support["active_player"] in support["players"]


class Scripted:
    """A fixture double that always answers with a configured action."""

    name = "scripted"
    timeout_s = 0.0

    def __init__(self, name, model, pick):
        self.name = name
        self.model = model
        self._pick = pick

    def decide(self, view):
        if self._pick == "first":
            return Decision(action_id=view.candidates[0]["action_id"])
        if self._pick == "error":
            raise ProviderError("scripted failure")
        return Decision(action_id=self._pick)


def test_run_fixtures_scores_providers():
    fixtures = series_mod.load_fixtures()
    rules = {doc["rules"]: _fixture_rules(doc) for doc in fixtures}
    providers = [_ScriptedFor(fixtures, name, mode)
                 for name, mode in (("good", "correct"),
                                    ("wrong", "first"),
                                    ("broken", "error"))]
    rows = series_mod.run_fixtures(providers, fixtures, rules)
    assert len(rows) == 3
    by_name = {row["provider"]: row for row in rows}
    assert by_name["good"]["score"] == 3
    assert by_name["broken"]["score"] == 0
    assert by_name["broken"]["fixtures"][0]["error"] == "scripted failure"
    assert by_name["wrong"]["total"] == 3
    assert by_name["wrong"]["score"] < 3, \
        "picking the first shown candidate must not ace the fixtures"
    assert all(not item["candidates_drift"] for row in rows
               for item in row["fixtures"])


def _ScriptedFor(fixtures, name, mode):
    class _For(Scripted):
        def decide(self, view):
            # The frozen fixtures carry no name in the view; the runner
            # calls one provider per fixture in file order, so the double
            # keys off the observation turn id.
            for doc in fixtures:
                if doc["observation"]["turn_id"] == \
                        view.observation["turn_id"]:
                    if mode == "correct":
                        return Decision(action_id=doc["correct"][0])
                    if mode == "error":
                        raise ProviderError("scripted failure")
                    return Decision(
                        action_id=view.candidates[0]["action_id"])
            raise ProviderError("unknown fixture")

    return _For(name, name, mode)


def test_cli_fixture_run_offline_with_bots(monkeypatch):
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    for var in REMOTE_ENV:
        monkeypatch.delenv(var, raising=False)
    assert cli.main(["--fixtures", "--fixtures-bots"]) == 0


def test_cli_refuses_a_paid_series_without_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    for var in REMOTE_ENV:
        monkeypatch.delenv(var, raising=False)
    path = _remote_series(tmp_path, monkeypatch,
                          {"max_calls": 0, "max_usd": 0.0},
                          rules_path=tiny_rules(tmp_path))

    class NoTty:
        def isatty(self):
            return False

        def write(self, text):
            return len(text)

        def flush(self):
            return None

    monkeypatch.setattr(sys, "stdout", NoTty())
    assert cli.main(["--series", path]) == 2
