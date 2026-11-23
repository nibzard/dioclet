# ABOUTME: Outcome predictions on candidate features, checked against the
# ABOUTME: engine with forced dice and forced hidden deals.
"""Phase 5 outcome tests.

Every predicted outcome must match what the engine produces: the same
prestige after the action, the same claim result, the same item or card.
Dice are forced through the engine's die function; hidden deals are
placed by the test and compared outcome by outcome. Probabilities come
from public data only and must sum to one.
"""

import copy
import json
import os
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidate_actions  # noqa: E402
import engine  # noqa: E402
import policies  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")

PERISTYLE = [9, 6]
NEAR_PERISTYLE = [8, 6]
PROBABILITY_TOLERANCE = 4e-6  # six-decimal rounding over at most six outcomes


def _rules():
    return engine.load_rules(RULES_PATH)


def _outcomes_for(obs, rules, kind, exactly=True, **match):
    """The outcomes list of one shortlisted candidate of this kind.

    Duels against one target exist at several destinations; the nearest
    destination then picks a deterministic candidate.
    """
    selected, _ = candidate_actions.build_candidates(obs, rules)
    found = [c for c in selected if c["kind"] == kind]
    for key, value in match.items():
        found = [c for c in found if c.get(key) == value]
    if exactly:
        assert len(found) == 1, f"expected one {kind} candidate, got {len(found)}"
    else:
        assert found, f"expected a {kind} candidate, got none"
        found = [min(found, key=lambda c: tuple(c["destination"]))]
    return found[0]


def _apply_forced(state, action_id, combat_rolls):
    """Apply one action to a copy with the combat dice forced.

    Two further rolls feed the movement dice of the next turn.
    """
    clone = copy.deepcopy(state)
    with patch.object(engine, "_die",
                      side_effect=list(combat_rolls) + [3, 3]):
        record = engine.apply_action(clone, clone["active_player"],
                                     clone["turn_id"], action_id)
    return clone, record


def _duel_state(rules, pending_player=None, defender_items=(),
                attacker_prestige=5):
    """A phase-2 seat with a duel against the seat on the Peristyle."""
    state = engine.new_game(rules, 7, "outcomes-duel",
                            dict.fromkeys(engine.IDS, "balanced"))
    state.update(turn_order=list(engine.IDS), round_start=0,
                 turn_index=0, active_player="P1")
    state["phase"] = 2
    state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"],
                                  equipment=list(defender_items))
    state["players"]["P1"].update(pos=NEAR_PERISTYLE[:],
                                  prestige=attacker_prestige,
                                  equipment=[])
    state["current_roll"], state["current_dice"] = 6, [3, 3]
    if pending_player:
        state["pending_claim"] = {"player": pending_player,
                                  "claim_id": state["turn_id"],
                                  "responded": [], "round": state["round"]}
    return state


class TestDuelOutcomes(unittest.TestCase):
    def test_counterclaim_outcomes_match_engine_over_every_die_pair(self):
        rules = _rules()
        state = _duel_state(rules, pending_player="P0")
        obs = engine.observe(state, "P1")
        duel = _outcomes_for(obs, rules, "duel", exactly=False, target="P0")
        outcomes = duel["features"]["outcomes"]
        by_condition = {o["condition"]: o for o in outcomes}
        self.assertEqual(set(by_condition), {"win", "lose"})
        odds = candidate_actions.duel_odds(
            {"id": "P1", "equipment": []}, {"id": "P0", "equipment": []},
            rules, obs["pending_claim"])
        self.assertEqual(by_condition["win"]["probability"],
                         round(odds["probability"], 6))
        self.assertEqual(by_condition["lose"]["probability"],
                         round(1 - odds["probability"], 6))
        self.assertAlmostEqual(
            sum(o["probability"] for o in outcomes), 1.0,
            delta=PROBABILITY_TOLERANCE)
        # A win must state the displacement the engine then performs: the
        # defender holds no lorica, so the gate return is certain.
        self.assertEqual(by_condition["win"]["effects"]["claimant_to_gate"],
                         True)
        wins = 0
        for attack_roll in range(1, 7):
            for defense_roll in range(1, 7):
                clone, record = _apply_forced(state, duel["action_id"],
                                              [attack_roll, defense_roll])
                event = next(e for e in record["events"]
                             if e["type"] == "duel")
                won = event["winner"] == "P1"
                wins += won
                predicted = by_condition["win" if won else "lose"]
                effects = predicted["effects"]
                self.assertEqual(effects["prestige_after"],
                                 clone["players"]["P1"]["prestige"],
                                 f"rolls {attack_roll},{defense_roll}")
                cancelled = clone["pending_claim"] is None
                self.assertEqual(effects["claim_cancelled"], cancelled,
                                 f"rolls {attack_roll},{defense_roll}")
                if won:
                    self.assertEqual(clone["players"]["P0"]["pos"],
                                     state["players"]["P0"]["gate"])
        self.assertEqual(wins, round(odds["probability"] * 36))

    def test_win_over_a_lorica_claimant_stays_silent_on_displacement(self):
        rules = _rules()
        state = _duel_state(rules, pending_player="P0",
                            defender_items=["lorica_segmentata"])
        obs = engine.observe(state, "P1")
        duel = _outcomes_for(obs, rules, "duel", exactly=False, target="P0")
        win = next(o for o in duel["features"]["outcomes"]
                   if o["condition"] == "win")
        self.assertNotIn("claimant_to_gate", win["effects"])
        self.assertTrue(win["effects"]["claim_cancelled"])
        clone, _ = _apply_forced(state, duel["action_id"], [6, 1])
        self.assertIsNone(clone["pending_claim"])
        self.assertEqual(clone["players"]["P0"]["pos"], PERISTYLE)

    def test_plain_duel_outcomes_match_engine_over_every_die_pair(self):
        rules = _rules()
        state = _duel_state(rules, attacker_prestige=2)
        obs = engine.observe(state, "P1")
        duel = _outcomes_for(obs, rules, "duel", exactly=False, target="P0")
        by_condition = {o["condition"]: o
                        for o in duel["features"]["outcomes"]}
        self.assertEqual(by_condition["win"]["effects"]["claim_cancelled"],
                         False)
        self.assertEqual(by_condition["lose"]["effects"]["claim_cancelled"],
                         False)
        for key in ("win", "lose"):
            self.assertNotIn("claimant_to_gate",
                             by_condition[key]["effects"])
        for attack_roll in range(1, 7):
            for defense_roll in range(1, 7):
                clone, record = _apply_forced(state, duel["action_id"],
                                              [attack_roll, defense_roll])
                event = next(e for e in record["events"]
                             if e["type"] == "duel")
                won = event["winner"] == "P1"
                predicted = by_condition["win" if won else "lose"]
                self.assertEqual(predicted["effects"]["prestige_after"],
                                 clone["players"]["P1"]["prestige"],
                                 f"rolls {attack_roll},{defense_roll}")
                self.assertIsNone(clone["pending_claim"])


class TestExploreOutcomes(unittest.TestCase):
    def _palace_state(self, rules):
        state = engine.new_game(rules, 7, "outcomes-explore",
                                dict.fromkeys(engine.IDS, "balanced"))
        state.update(turn_order=list(engine.IDS), round_start=0,
                     turn_index=0, active_player="P1")
        state["players"]["P1"].update(pos=[4, 0], prestige=2, equipment=[])
        state["current_roll"], state["current_dice"] = 4, [2, 2]
        return state

    def _explore_candidate(self, state, rules, district=None):
        if district:
            # Turn a setup reveal back over so the entry holds a hidden item.
            state["revealed"].pop(district, None)
        obs = engine.observe(state, "P1")
        return obs, _outcomes_for(obs, rules, "explore")

    def test_unrevealed_explore_names_only_hidden_items_at_equal_odds(self):
        rules = _rules()
        state = self._palace_state(rules)
        obs, explore = self._explore_candidate(state, rules, district="A")
        outcomes = explore["features"]["outcomes"]
        revealed = set(obs["revealed_districts"].values())
        owned = {item for player in obs["players"].values()
                 for item in player["equipment"]}
        named = [o["effects"]["item_gained"] for o in outcomes]
        district = explore["features"]["district"]
        self.assertNotIn(district, obs["revealed_districts"])
        self.assertTrue(named)
        for name in named:
            self.assertNotIn(name, revealed)
            self.assertNotIn(name, owned)
        self.assertEqual(len(named), len(set(named)))
        share = round(1 / len(outcomes), 6)
        for outcome in outcomes:
            self.assertEqual(outcome["probability"], share)
            self.assertEqual(outcome["condition"],
                             f"reveal {outcome['effects']['item_gained']}")
            self.assertEqual(outcome["effects"]["prestige_after"], 2)
            self.assertFalse(outcome["effects"]["claim_cancelled"])
        self.assertAlmostEqual(sum(o["probability"] for o in outcomes), 1.0,
                               delta=PROBABILITY_TOLERANCE)

    def test_unrevealed_explore_matches_engine_for_every_hidden_item(self):
        rules = _rules()
        state = self._palace_state(rules)
        obs, explore = self._explore_candidate(state, rules, district="A")
        outcomes = explore["features"]["outcomes"]
        district = explore["features"]["district"]
        self.assertEqual(len(outcomes),
                         len(obs["board"]["districts"])
                         - len(obs["revealed_districts"]))
        for outcome in outcomes:
            item = outcome["effects"]["item_gained"]
            clone = copy.deepcopy(state)
            clone["district_equipment"][district] = item
            engine.apply_action(clone, "P1", clone["turn_id"],
                                explore["action_id"])
            effects = outcome["effects"]
            self.assertEqual(effects["item_gained"],
                             clone["players"]["P1"]["equipment"][-1])
            self.assertEqual(clone["revealed"][district], item)
            self.assertEqual(effects["prestige_after"],
                             clone["players"]["P1"]["prestige"])

    def test_known_item_explore_is_one_certain_outcome(self):
        rules = _rules()
        state = self._palace_state(rules)
        district, item = next(iter(state["revealed"].items()))
        cell = state["rules"]["palace"]["map"]["treasure_entries"][district]
        state["players"]["P1"].update(pos=list(cell), prestige=2, equipment=[])
        obs, explore = self._explore_candidate(state, rules)
        self.assertEqual(explore["features"]["district"], district)
        outcomes = explore["features"]["outcomes"]
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["probability"], 1.0)
        self.assertEqual(outcomes[0]["effects"]["item_gained"], item)
        clone = copy.deepcopy(state)
        engine.apply_action(clone, "P1", clone["turn_id"],
                            explore["action_id"])
        self.assertEqual(outcomes[0]["effects"]["prestige_after"],
                         clone["players"]["P1"]["prestige"])
        self.assertIn(item, clone["players"]["P1"]["equipment"])


class TestGuardPostOutcomes(unittest.TestCase):
    def _guard_state(self, rules):
        state = engine.new_game(rules, 7, "outcomes-guard",
                                dict.fromkeys(engine.IDS, "balanced"))
        state.update(turn_order=list(engine.IDS), round_start=0,
                     turn_index=0, active_player="P1")
        state["players"]["P1"].update(pos=[6, 3], prestige=2, equipment=[])
        state["current_roll"], state["current_dice"] = 4, [2, 2]
        return state

    def test_guard_post_outcomes_match_engine_for_every_roll(self):
        rules = _rules()
        state = self._guard_state(rules)
        obs = engine.observe(state, "P1")
        guard = _outcomes_for(obs, rules, "guard_post")
        outcomes = guard["features"]["outcomes"]
        by_condition = {o["condition"]: o for o in outcomes}
        self.assertEqual(set(by_condition), {"win", "lose"})
        min_roll = rules["prestige"]["guard_post_min_roll"]
        self.assertEqual(by_condition["win"]["probability"],
                         round((7 - min_roll) / 6, 6))
        self.assertAlmostEqual(sum(o["probability"] for o in outcomes), 1.0,
                               delta=PROBABILITY_TOLERANCE)
        for roll in range(1, 7):
            clone, record = _apply_forced(state, guard["action_id"], [roll])
            event = next(e for e in record["events"]
                         if e["type"] == "guard_post")
            self.assertEqual(event["roll"], roll)
            predicted = by_condition["win" if event["success"] else "lose"]
            self.assertEqual(predicted["effects"]["prestige_after"],
                             clone["players"]["P1"]["prestige"], f"roll {roll}")
            self.assertFalse(predicted["effects"]["claim_cancelled"])

    def test_guard_post_win_shows_the_cap_loss(self):
        rules = _rules()
        rules["prestige"]["guard_post_reward"] = 2
        state = self._guard_state(rules)
        obs = engine.observe(state, "P1")
        guard = _outcomes_for(obs, rules, "guard_post")
        win = next(o for o in guard["features"]["outcomes"]
                   if o["condition"] == "win")
        # Two prestige at the cap of three: the award clamps to one.
        self.assertEqual(win["effects"]["prestige_after"],
                         rules["prestige"]["cap"])
        clone, _ = _apply_forced(state, guard["action_id"], [6])
        self.assertEqual(clone["players"]["P1"]["prestige"],
                         rules["prestige"]["cap"])


def _phase2_state(rules, revealed=None, claimant=False, pos_index=0):
    """A phase-2 seat on a dealt blind board, ready to act."""
    state = engine.new_game(rules, 7, "outcomes-phase2",
                            dict.fromkeys(engine.IDS, "balanced"))
    state.update(turn_order=list(engine.IDS), round_start=0,
                 turn_index=0, active_player="P1")
    state["phase"] = 2
    cells = state["rules"]["succession"]["map"]["card_spaces"]
    state["faction_sites"] = {f"{c[0]},{c[1]}": None for c in cells}
    for cell, name in zip(cells[:3], sorted(
            rules["succession"]["faction_cards"]["factions"])):
        state["faction_sites"][f"{cell[0]},{cell[1]}"] = name
    state["faction_sites_revealed"] = dict(revealed or {})
    home = (state["rules"]["succession"]["map"]["checkpoint"] if claimant
            else cells[pos_index])
    state["players"]["P1"].update(pos=list(home), prestige=2, equipment=[])
    state["current_roll"], state["current_dice"] = 4, [2, 2]
    if claimant:
        state["pending_claim"] = {"player": "P1",
                                  "claim_id": state["turn_id"],
                                  "responded": [], "round": state["round"]}
    return state


class TestSupportAndProclaimOutcomes(unittest.TestCase):
    def test_gain_support_outcome_matches_engine(self):
        rules = _rules()
        state = _phase2_state(rules, revealed={"3,0": "army"})
        obs = engine.observe(state, "P1")
        support = _outcomes_for(obs, rules, "gain_support", faction="army")
        outcomes = support["features"]["outcomes"]
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertEqual(outcome["condition"], "always")
        self.assertEqual(outcome["probability"], 1.0)
        self.assertEqual(outcome["effects"]["prestige_after"], 1)
        self.assertFalse(outcome["effects"]["claim_cancelled"])
        clone, _ = _apply_forced(state, support["action_id"], [])
        self.assertEqual(clone["players"]["P1"]["prestige"], 1)
        self.assertIn("army", clone["players"]["P1"]["support"])

    def test_claimant_support_cancels_the_claim_in_every_outcome(self):
        rules = _rules()
        revealed = {"7,6": "officials"}
        state = _phase2_state(rules, revealed=revealed, claimant=True)
        obs = engine.observe(state, "P1")
        support = _outcomes_for(obs, rules, "gain_support", faction="officials")
        outcomes = support["features"]["outcomes"]
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0]["effects"]["claim_cancelled"])
        self.assertEqual(outcomes[0]["effects"]["prestige_after"], 1)
        clone, _ = _apply_forced(state, support["action_id"], [])
        self.assertIsNone(clone["pending_claim"])
        self.assertIn("officials", clone["players"]["P1"]["support"])

    def test_proclaim_outcome_matches_engine(self):
        rules = _rules()
        state = _phase2_state(rules)
        checkpoint = state["rules"]["succession"]["map"]["checkpoint"]
        state["players"]["P1"].update(pos=list(checkpoint), prestige=3,
                                      support=["army", "elites"])
        obs = engine.observe(state, "P1")
        proclaim = _outcomes_for(obs, rules, "proclaim")
        outcomes = proclaim["features"]["outcomes"]
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertEqual(outcome["probability"], 1.0)
        self.assertEqual(outcome["effects"]["prestige_after"], 3)
        self.assertFalse(outcome["effects"]["claim_cancelled"])
        clone, _ = _apply_forced(state, proclaim["action_id"], [])
        self.assertEqual(clone["players"]["P1"]["prestige"], 3)
        self.assertEqual(clone["pending_claim"]["player"], "P1")

    def test_proclaim_outcome_carries_the_rules_cost(self):
        rules = _rules()
        rules["succession"]["proclaim_cost"] = 1
        state = _phase2_state(rules)
        checkpoint = state["rules"]["succession"]["map"]["checkpoint"]
        state["players"]["P1"].update(pos=list(checkpoint), prestige=3,
                                      support=["army", "elites"])
        obs = engine.observe(state, "P1")
        proclaim = _outcomes_for(obs, rules, "proclaim")
        outcome = proclaim["features"]["outcomes"][0]
        self.assertEqual(outcome["effects"]["prestige_after"], 2)
        clone, _ = _apply_forced(state, proclaim["action_id"], [])
        self.assertEqual(clone["players"]["P1"]["prestige"], 2)
        self.assertEqual(clone["pending_claim"]["player"], "P1")

    def test_claimant_duel_cancels_the_claim_whatever_the_dice(self):
        rules = _rules()
        state = _phase2_state(rules, claimant=True)
        state["players"]["P0"].update(pos=NEAR_PERISTYLE[:], prestige=1)
        obs = engine.observe(state, "P1")
        duel = _outcomes_for(obs, rules, "duel", exactly=False, target="P0")
        by_condition = {o["condition"]: o
                        for o in duel["features"]["outcomes"]}
        self.assertTrue(by_condition["win"]["effects"]["claim_cancelled"])
        self.assertTrue(by_condition["lose"]["effects"]["claim_cancelled"])
        for rolls, condition in (((6, 1), "win"), ((1, 6), "lose")):
            clone, _ = _apply_forced(state, duel["action_id"], list(rolls))
            self.assertIsNone(clone["pending_claim"], condition)
            self.assertEqual(by_condition[condition]["effects"]["prestige_after"],
                             clone["players"]["P1"]["prestige"], condition)


class TestSearchOutcomes(unittest.TestCase):
    def _search_candidate(self, state, rules):
        obs = engine.observe(state, "P1")
        return obs, _outcomes_for(obs, rules, "search_site", exactly=False)

    def _assert_outcomes_match_engine(self, state, rules, obs, search):
        cell = search["destination"]
        key = f"{cell[0]},{cell[1]}"
        self.assertNotIn(key, obs["board"]["card_spaces"]["revealed"])
        outcomes = search["features"]["outcomes"]
        remaining = {name for name in
                     rules["succession"]["faction_cards"]["factions"]
                     if name not in obs["board"]["card_spaces"]["revealed"]
                     .values()}
        total = (len(obs["board"]["card_spaces"]["candidates"])
                 - len(obs["board"]["card_spaces"]["revealed"]))
        self.assertEqual(len(outcomes),
                         len(remaining) + (1 if len(remaining) < total else 0))
        for outcome in outcomes:
            value = outcome["effects"]["card_revealed"]
            clone = copy.deepcopy(state)
            clone["faction_sites"][key] = value
            engine.apply_action(clone, "P1", clone["turn_id"],
                                search["action_id"])
            self.assertEqual(clone["faction_sites_revealed"][key], value)
            self.assertEqual(outcome["effects"]["prestige_after"],
                             clone["players"]["P1"]["prestige"])

    def test_fresh_board_deals_one_sixth_per_faction_and_blanks(self):
        rules = _rules()
        state = _phase2_state(rules, pos_index=2)
        obs, search = self._search_candidate(state, rules)
        outcomes = search["features"]["outcomes"]
        conditions = {o["condition"] for o in outcomes}
        self.assertEqual(conditions, {"reveal army", "reveal elites",
                                      "reveal officials", "reveal blank"})
        self.assertEqual(
            [o["probability"] for o in outcomes],
            [round(1 / 6, 6), round(1 / 6, 6), round(1 / 6, 6), 0.5])
        self.assertAlmostEqual(sum(o["probability"] for o in outcomes), 1.0,
                               delta=PROBABILITY_TOLERANCE)
        self._assert_outcomes_match_engine(state, rules, obs, search)

    def test_search_after_one_reveal_uses_the_remaining_counts(self):
        rules = _rules()
        revealed = {"3,0": "army"}
        state = _phase2_state(rules, revealed=revealed, pos_index=2)
        obs, search = self._search_candidate(state, rules)
        outcomes = search["features"]["outcomes"]
        self.assertEqual([o["condition"] for o in outcomes],
                         ["reveal elites", "reveal officials", "reveal blank"])
        self.assertEqual([o["probability"] for o in outcomes],
                         [0.2, 0.2, 0.6])
        self._assert_outcomes_match_engine(state, rules, obs, search)


class TestOutcomeInvariants(unittest.TestCase):
    OUTCOME_KINDS = {"duel", "guard_post", "gain_support", "proclaim",
                     "explore", "search_site", "inspect"}

    def test_sums_and_conditions_hold_across_a_real_game(self):
        rules = _rules()
        state = engine.new_game(rules, 2026, "outcomes-sweep")
        rng = random.Random(7)
        seen = set()
        turns = 0
        while not engine.is_finished(state) and turns < 200:
            obs = engine.observe(state, state["active_player"])
            selected, _ = candidate_actions.build_candidates(obs, rules)
            for candidate in selected:
                outcomes = candidate["features"].get("outcomes")
                if outcomes is None:
                    continue
                seen.add(candidate["kind"])
                self.assertIn(candidate["kind"], self.OUTCOME_KINDS)
                conditions = [o["condition"] for o in outcomes]
                self.assertEqual(len(conditions), len(set(conditions)))
                for outcome in outcomes:
                    self.assertTrue(0.0 <= outcome["probability"] <= 1.0)
                self.assertAlmostEqual(
                    sum(o["probability"] for o in outcomes), 1.0,
                    delta=PROBABILITY_TOLERANCE)
            action_id, _ = policies.act("tactical", obs, rng)
            engine.apply_action(state, state["active_player"],
                                obs["turn_id"], action_id)
            turns += 1
        self.assertTrue({"duel", "guard_post", "gain_support", "proclaim",
                         "explore", "search_site"} <= seen)

    def test_sentinels_of_hidden_state_never_reach_outcomes(self):
        rules = _rules()
        state = engine.new_game(rules, 7, "outcomes-sentinel",
                                dict.fromkeys(engine.IDS, "balanced"))
        state.update(turn_order=list(engine.IDS), round_start=0,
                     turn_index=0, active_player="P1")
        state["players"]["P1"].update(pos=[4, 0], prestige=2, equipment=[])
        state["current_roll"], state["current_dice"] = 4, [2, 2]
        # Turn the setup reveal of A back over so the seat explores a
        # hidden district, not a publicly named one.
        state["revealed"].pop("A", None)
        obs = engine.observe(state, "P1")
        obs["district_equipment"] = {"A": "SECRET_ITEM_SENTINEL"}
        obs["rng"] = "FUTURE_SENTINEL"
        obs["players"]["P1"]["abilities_used"] = "SECRET_ABILITY_SENTINEL"
        for action in obs["legal_actions"]:
            action["item"] = "ACTION_ITEM_SENTINEL"
        selected, _ = candidate_actions.build_candidates(obs, rules)
        blob = json.dumps(selected)
        for sentinel in ("SECRET_ITEM_SENTINEL", "FUTURE_SENTINEL",
                         "SECRET_ABILITY_SENTINEL", "ACTION_ITEM_SENTINEL"):
            self.assertNotIn(sentinel, blob)
        explore = next(c for c in selected if c["kind"] == "explore")
        named = [o["effects"]["item_gained"]
                 for o in explore["features"]["outcomes"]]
        revealed = set(obs["revealed_districts"].values())
        owned = {item for player in obs["players"].values()
                 for item in player["equipment"]}
        self.assertTrue(named)
        for name in named:
            self.assertNotIn(name, revealed)
            self.assertNotIn(name, owned)

    def test_search_outcomes_only_name_remaining_factions_or_blank(self):
        rules = _rules()
        state = _phase2_state(rules, revealed={"3,0": "army"}, pos_index=2)
        obs = engine.observe(state, "P1")
        search = _outcomes_for(obs, rules, "search_site", exactly=False)
        revealed = obs["board"]["card_spaces"]["revealed"]
        remaining = {name for name in
                     rules["succession"]["faction_cards"]["factions"]
                     if name not in revealed.values()}
        for outcome in search["features"]["outcomes"]:
            value = outcome["effects"]["card_revealed"]
            self.assertTrue(value is None or value in remaining)


if __name__ == "__main__":
    unittest.main()
