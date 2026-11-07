"""Offline tests for the V0.4.1 analysis and reporting tools."""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analyze_v041
import tournament


MOCK_CONFIG = {
    "tournament_id": "t_analyze",
    "rules": "rules_v03_base.json",
    "provider": "mock",
    "schedules": [
        {"type": "rotation", "policies": ["decisions", "tactical",
                                          "balanced", "greedy"],
         "games": 4, "seed_base": 7501, "prefix": "az"},
    ],
    "budget": {"aggregate_max_cost_usd": 1.0, "per_game_max_calls": 120,
               "per_game_max_cost_usd": 0.05},
}


class AnalyzeTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="v041-analyze-")
        cfg_path = os.path.join(cls.tmp, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(MOCK_CONFIG, fh)
        cls.root = os.path.join(cls.tmp, "results", "v041")
        tournament.run_tournament(cfg_path, cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestAnalyze(AnalyzeTestBase):
    def test_analyze_runs_on_mock_tournament(self):
        payload = analyze_v041.analyze(self.root)
        agg = payload["aggregate"]
        self.assertEqual(agg["games_analyzed"], 4)
        self.assertEqual(agg["flags"], [])  # no mandatory exclusions
        # Mock ranking always picks a winning attack first, so the
        # analyzer must see full utilization in mock data.
        self.assertGreater(agg["win_attack"]["available"], 0)
        self.assertEqual(agg["win_attack"]["utilization"], 1.0)
        self.assertIsInstance(agg["duels"]["total"], int)
        self.assertGreaterEqual(agg["duels"]["low_value_share"], 0.0)

    def test_report_runs_on_mock_tournament(self):
        payload = analyze_v041.report(self.root)
        self.assertEqual(payload["games_completed"], 4)
        self.assertEqual(len(payload["games"]), 4)
        self.assertIn("decisions", payload["wins_by_policy"])
        self.assertIn("tactical", payload["wins_by_policy"])
        # Seat-game denominators per policy are 4 each.
        for block in payload["wins_by_policy"].values():
            self.assertEqual(block["seat_games"], 4)
        self.assertEqual(
            sum(m["games"] for m in payload["matchups"].values()), 4)
        self.assertEqual(payload["api"]["incomplete"], 0)
        self.assertIn("exploratory sample", payload["caution"])

    def test_description_parsing(self):
        candidates = [
            {"action_id": "a1", "kind": "duel",
             "description": "Duel P2 (exact win chance 58%; target has "
                            "1 Emperor hits, 2 Glory)."},
            {"action_id": "a2", "kind": "attack_emperor",
             "description": "Attack the Emperor without Glory; exact hit "
                            "chance 42% (wins the game on a hit)."},
            {"action_id": "a3", "kind": "move",
             "description": "Move to [2, 3] (2 step(s); now 1 from the "
                            "current goal)."},
        ]
        facts = analyze_v041.candidate_facts(candidates)
        self.assertEqual(facts["a1"]["duel_win_pct"], 58)
        self.assertEqual(facts["a2"]["hit_pct"], 42)
        self.assertTrue(facts["a2"]["wins_game"])
        self.assertEqual(facts["a3"]["goal_dist"], 1)

    def test_wilson_interval(self):
        ci = analyze_v041.wilson(8, 32)
        self.assertLess(ci["lo"], 0.25)
        self.assertGreater(ci["hi"], 0.25)


if __name__ == "__main__":
    unittest.main()
