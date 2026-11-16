# ABOUTME: Exact-odds tests for the candidate-action math: duel, contest,
# ABOUTME: and threshold probabilities over the six-by-six die grid.
"""Offline tests for the exact odds in candidate_actions.

Only the pure probability helpers are tested here. The shortlist and
projection behavior over live observations is covered by
test_succession_decisions.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidate_actions  # noqa: E402


class TestExactOdds(unittest.TestCase):
    def test_duel_probability_equal_bonus_tie_attacker(self):
        self.assertAlmostEqual(
            candidate_actions.duel_win_probability(0, 0, True), 21 / 36)

    def test_duel_probability_equal_bonus_tie_defender(self):
        self.assertAlmostEqual(
            candidate_actions.duel_win_probability(0, 0, False), 15 / 36)

    def test_contest_offset(self):
        # +2 vs +0, strict win: count a+2 > b over the 6x6 grid = 26.
        self.assertAlmostEqual(
            candidate_actions.contest_probability(2, 0, False), 26 / 36)
        # 0 vs +2, ties win: a >= b+2 over the grid = 10.
        self.assertAlmostEqual(
            candidate_actions.contest_probability(0, 2, True), 10 / 36)

    def test_threshold(self):
        self.assertAlmostEqual(candidate_actions.threshold_probability(4), 0.5)
        self.assertAlmostEqual(candidate_actions.threshold_probability(5), 1 / 3)
        self.assertAlmostEqual(candidate_actions.threshold_probability(1), 1.0)


if __name__ == "__main__":
    unittest.main()
