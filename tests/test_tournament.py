"""Offline tests for the V0.4.1 tournament runner."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_driver  # noqa: E402
import tournament  # noqa: E402


MOCK_CONFIG = {
    "tournament_id": "t_mock",
    "rules": "rules_v03_base.json",
    "provider": "mock",
    "schedules": [
        {"type": "mirror", "policy": "decisions", "games": 2,
         "seed_base": 7001, "prefix": "mk"},
        {"type": "rotation", "policies": ["decisions", "tactical",
                                          "balanced", "greedy"],
         "games": 4, "seed_base": 7101, "prefix": "mr"},
    ],
    "budget": {"aggregate_max_cost_usd": 1.0, "per_game_max_calls": 120,
               "per_game_max_cost_usd": 0.05},
}


def write_config(tmp, config):
    path = os.path.join(tmp, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config, fh)
    return path


class TestSchedules(unittest.TestCase):
    def test_rotation_visits_every_seat_equally(self):
        spec = {"type": "rotation", "games": 16,
                "policies": ["decisions", "tactical", "balanced",
                             "greedy"], "seed_base": 1, "prefix": "x"}
        games = tournament.build_schedule(spec)
        self.assertEqual(len(games), 16)
        for policy in ("decisions", "tactical", "balanced", "greedy"):
            seats = [list(g["players"]).index(pid)
                     for g in games
                     for pid, pol in g["players"].items() if pol == policy]
            self.assertEqual(len(seats), 16)
            self.assertEqual(sorted(seats), [0, 0, 0, 0, 1, 1, 1, 1,
                                             2, 2, 2, 2, 3, 3, 3, 3])

    def test_pairs_alternate_seats(self):
        spec = {"type": "pairs", "a": "decisions", "b": "tactical",
                "games": 6, "seed_base": 1, "prefix": "p"}
        games = tournament.build_schedule(spec)
        for i, game in enumerate(games):
            a_seats = sorted(pid for pid, p in game["players"].items()
                             if p == "decisions")
            self.assertEqual(len(a_seats), 2)
            if i % 2:
                self.assertEqual(a_seats, ["P1", "P3"])
            else:
                self.assertEqual(a_seats, ["P0", "P2"])

    def test_seeds_and_ids_reproducible(self):
        spec = {"type": "mirror", "policy": "decisions", "games": 3,
                "seed_base": 5101, "prefix": "ta"}
        self.assertEqual(tournament.build_schedule(spec),
                         tournament.build_schedule(spec))


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="v041-tourney-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = os.path.join(self.tmp, "results", "v041")

    def test_mock_tournament_completes_and_reports(self):
        path = write_config(self.tmp, MOCK_CONFIG)
        report = tournament.run_tournament(path, self.root)
        self.assertEqual(len(report["statuses"]), 6)
        for entry in report["statuses"]:
            self.assertEqual(entry.get("status"), "finished", entry)
        self.assertEqual(report["usage"]["calls"], 0)  # mock = no live cost
        for gid in ("mk01", "mk02", "mr01", "mr02", "mr03", "mr04"):
            self.assertTrue(os.path.exists(os.path.join(
                self.root, "games", gid, "result.json")))
            self.assertTrue(os.path.exists(os.path.join(
                self.root, "games", gid, "decisions.jsonl")))

    def test_resume_skips_completed_games(self):
        path = write_config(self.tmp, MOCK_CONFIG)
        tournament.run_tournament(path, self.root)
        # Remove one finished game entirely; keep the rest.
        shutil.rmtree(os.path.join(self.root, "games", "mr02"))
        report = tournament.run_tournament(path, self.root,
                                           resume=True)
        statuses = [e for e in report["statuses"]]
        self.assertEqual(
            sum(1 for e in statuses if e.get("status") == "already_complete"),
            5)
        self.assertTrue(os.path.exists(os.path.join(
            self.root, "games", "mr02", "result.json")))

    def test_dry_run_estimates_without_playing(self):
        path = write_config(self.tmp, MOCK_CONFIG)
        estimate = tournament.run_tournament(path, self.root, dry=True)
        self.assertEqual(estimate["games"], 6)
        self.assertGreater(estimate["estimated_decisions_calls"], 0)
        self.assertEqual(estimate["games_already_complete"], 0)
        self.assertFalse(os.path.exists(os.path.join(self.root, "games")))

    def test_live_requires_flag(self):
        config = json.loads(json.dumps(MOCK_CONFIG))
        config["provider"] = "live"
        path = write_config(self.tmp, config)
        with self.assertRaises(SystemExit):
            tournament.run_tournament(path, self.root, live=False)

    def test_budget_stop_preserves_completed_games(self):
        config = json.loads(json.dumps(MOCK_CONFIG))
        config["schedules"] = [
            {"type": "mirror", "policy": "decisions", "games": 3,
             "seed_base": 7201, "prefix": "bz"}]
        path = write_config(self.tmp, config)

        def incomplete_then_finished(rules, seed, game_id, players, out,
                                     **kwargs):
            if game_id == "bz01":
                for key in ("status", "winner", "incomplete_reason",
                            "decisions", "budget"):
                    pass
                os.makedirs(out, exist_ok=True)
                summary = {"status": "in_progress", "winner": None,
                           "incomplete_reason": "budget: call cap reached",
                           "decisions": {"attempted": 2, "applied": 2},
                           "budget": {"calls": 2, "input_tokens": 2000,
                                      "estimated_cost_usd": 0.0002}}
                with open(os.path.join(out, "incomplete.json"), "w") as fh:
                    json.dump(summary, fh)
                return summary
            return {"status": "finished", "winner": "P1",
                    "incomplete_reason": None, "decisions": {},
                    "budget": {"calls": 0, "input_tokens": 0,
                               "estimated_cost_usd": 0.0}}

        with mock.patch.object(ai_driver, "run_ai_game",
                               side_effect=incomplete_then_finished):
            report = tournament.run_tournament(path, self.root)
        self.assertEqual(report["statuses"][0]["status"], "in_progress")
        self.assertTrue(any(e.get("tournament") == "stopped"
                            for e in report["statuses"]))
        self.assertFalse(os.path.exists(os.path.join(
            self.root, "games", "bz01", "result.json")))
        self.assertTrue(os.path.exists(os.path.join(
            self.root, "games", "bz01", "incomplete.json")))
        # Later games were never started after the stop.
        self.assertFalse(os.path.exists(os.path.join(
            self.root, "games", "bz02")))


if __name__ == "__main__":
    unittest.main()
