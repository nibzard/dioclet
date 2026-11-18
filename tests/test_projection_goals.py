# ABOUTME: Projection goals tests: every named target carries the engine's own
# ABOUTME: street distance, an exact one-roll reach chance, and public prereqs.
"""Phase 7 goal tests.

Each goal names one destination the viewing seat could aim at. The
steps come from the engine's street graph, the next-turn chance is the
exact share of movement dice that reach the target, and the
prerequisites state only what the public board proves.
"""

import copy
import json
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidate_actions  # noqa: E402
import engine  # noqa: E402
import policies  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")

PERISTYLE = [9, 6]
EAST_GATE = [18, 6]
NEAR_PERISTYLE = [8, 6]
CARD_ARMY = [3, 0]  # the dealt army space in the hand deals below
CARD_STREET = [15, 6]  # three street steps from the east gate
CARD_FAR = [3, 0]  # 21 street steps from the east gate

GOAL_KEYS = {"name", "kind", "target", "steps", "reach_next_turn",
             "prerequisites", "prerequisites_met"}
REACH_KEYS = {"kind", "probability", "turns_at_best", "dice", "die_sides"}


def _rules():
    return engine.load_rules(RULES_PATH)


def _blind_state(rules, seed=7):
    """A phase-2 game with a hand-dealt blind board; P1 acts from the east gate."""
    state = engine.new_game(rules, seed, "projection-goals",
                            dict.fromkeys(engine.IDS, "balanced"))
    state.update(turn_order=list(engine.IDS), round_start=0,
                 turn_index=1, active_player="P1")
    state["phase"] = 2
    cells = state["rules"]["succession"]["map"]["card_spaces"]
    state["faction_sites"] = {f"{c[0]},{c[1]}": None for c in cells}
    for cell, name in zip(cells[:3],
                          sorted(rules["succession"]["faction_cards"]["factions"])):
        state["faction_sites"][f"{cell[0]},{cell[1]}"] = name
    state["faction_sites_revealed"] = {}
    for pid, player in state["players"].items():
        player.update(gate=state["rules"]["succession"]["map"]["gates"][
            {"P0": "north", "P1": "east", "P2": "south", "P3": "west"}[pid]],
            equipment=[], prestige=2, support=[])
    state["players"]["P1"]["pos"] = EAST_GATE[:]
    state["players"]["P1"]["gate_id"] = "east"
    state["current_roll"], state["current_dice"] = 6, [3, 3]
    return state


def _goals(state, rules, viewer=None):
    obs = engine.observe(state, viewer or state["active_player"])
    projection = candidate_actions.project_observation(obs, rules)
    return projection["goals"]


def _goal_by_name(goals, name):
    found = [g for g in goals if g["name"] == name]
    assert len(found) == 1, f"expected one goal named {name!r}, got {found}"
    return found[0]


def _engine_distance(rules, phase, start, target):
    board = engine._board(rules, phase)
    return engine._distances(board, start)[tuple(target)]


def _moves_to(obs, target):
    return any(a["kind"] == "move" and a["destination"] == list(target)
               for a in obs["legal_actions"])


class TestGoalDistances(unittest.TestCase):
    def test_peristyle_goal_states_distance_support_need_and_pay(self):
        rules = _rules()
        state = _blind_state(rules)
        state["players"]["P1"].update(support=["army"])
        goals = _goals(state, rules)
        goal = _goal_by_name(goals, "Peristyle")
        self.assertEqual(goal["kind"], "claim")
        self.assertEqual(goal["target"], PERISTYLE)
        self.assertEqual(goal["steps"],
                         _engine_distance(rules, 2, EAST_GATE, PERISTYLE))
        self.assertEqual(goal["steps"], 9)
        self.assertEqual(goal["reach_next_turn"],
                         {"kind": "exact", "probability": round(10 / 36, 6),
                          "dice": 2, "die_sides": 6})
        self.assertEqual(goal["prerequisites"], [
            {"need": "factions", "required": 2, "have": 1, "met": False},
            {"need": "prestige", "cost": rules["succession"]["proclaim_cost"],
             "have": 2, "met": True},
        ])
        self.assertFalse(goal["prerequisites_met"])

    def test_move_offered_exactly_when_the_steps_fit_one_roll(self):
        rules = _rules()
        state = _blind_state(rules)
        goals = _goals(state, rules)
        self.assertTrue(goals)
        for roll, dice in ((3, [1, 2]), (12, [6, 6])):
            state["current_roll"], state["current_dice"] = roll, dice
            obs = engine.observe(state, "P1")
            for goal in goals:
                offered = _moves_to(obs, goal["target"])
                with self.subTest(roll=roll, goal=goal["name"]):
                    self.assertEqual(offered, 0 < goal["steps"] <= roll)
                    self.assertEqual(
                        goal["steps"],
                        _engine_distance(rules, 2, EAST_GATE, goal["target"]))

    def test_reach_chance_equals_the_share_of_dice_pairs_the_engine_offers(self):
        rules = _rules()
        for target in (CARD_STREET, PERISTYLE):
            with self.subTest(target=target):
                state = _blind_state(rules)
                steps = _engine_distance(rules, 2, EAST_GATE, target)
                offered = 0
                for first in range(1, 7):
                    for second in range(1, 7):
                        state["current_dice"] = [first, second]
                        state["current_roll"] = first + second
                        obs = engine.observe(state, "P1")
                        reached = _moves_to(obs, target)
                        self.assertEqual(reached, first + second >= steps,
                                         f"rolls {first},{second}")
                        offered += reached
                self.assertEqual(offered, 36 - sum(
                    1 for a in range(1, 7) for b in range(1, 7)
                    if a + b < steps))
                goal = _goal_by_name(_goals(state, rules), _goal_name(target))
                self.assertEqual(goal["reach_next_turn"]["probability"],
                                 round(offered / 36, 6))

    def test_far_target_is_labeled_an_estimate_with_no_exact_chance(self):
        rules = _rules()
        state = _blind_state(rules)
        goals = _goals(state, rules)
        goal = _goal_by_name(goals, "card space D")  # the far [3,0] space
        self.assertEqual(goal["target"], CARD_FAR)
        self.assertEqual(goal["steps"], 21)
        self.assertEqual(goal["reach_next_turn"],
                         {"kind": "estimate", "turns_at_best": 2,
                          "dice": 2, "die_sides": 6})
        self.assertNotIn("probability", goal["reach_next_turn"])

    def test_played_moves_arrive_in_the_estimated_turns(self):
        rules = _rules()
        state = _blind_state(rules)
        goal = _goal_by_name(_goals(state, rules), "card space D")
        turns = 0
        while state["players"]["P1"]["pos"] != CARD_FAR:
            # Keep the seat of interest active; only its moves are counted.
            state["turn_index"], state["active_player"] = 1, "P1"
            state["current_roll"], state["current_dice"] = 12, [6, 6]
            obs = engine.observe(state, "P1")
            moves = [a for a in obs["legal_actions"] if a["kind"] == "move"]
            best = min(moves, key=lambda a: _engine_distance(
                rules, 2, a["destination"], CARD_FAR))
            engine.apply_action(state, "P1", obs["turn_id"],
                                best["action_id"])
            turns += 1
            self.assertLess(turns, 5)
        self.assertEqual(state["players"]["P1"]["pos"], CARD_FAR)
        self.assertEqual(turns, goal["reach_next_turn"]["turns_at_best"])

    def test_move_reach_probability_matches_the_single_die_threshold(self):
        rules = _rules()
        rules["movement"]["dice"] = 1
        for distance in range(1, 14):
            with self.subTest(distance=distance):
                self.assertEqual(
                    candidate_actions.move_reach_probability(distance, rules),
                    candidate_actions.threshold_probability(distance, 6))


def _goal_name(target):
    return {tuple(CARD_STREET): "card space C", tuple(PERISTYLE): "Peristyle"}[
        tuple(target)]


class TestGoalPrerequisites(unittest.TestCase):
    def test_face_down_spaces_state_only_public_composition(self):
        rules = _rules()
        state = _blind_state(rules)
        goals = _goals(state, rules)
        # Nothing is searched yet, so every candidate space is face down.
        face_down = [g for g in goals if g["name"].startswith("card space ")]
        self.assertEqual(len(face_down),
                         len(rules["succession"]["map"]["card_spaces"]))
        for goal in face_down:
            self.assertEqual(goal["prerequisites"],
                             [{"need": "card", "state": "face down",
                               "met": False}])
            self.assertFalse(goal["prerequisites_met"])
            self.assertEqual(goal["hidden_cards"],
                             {"total": 6, "factions": 3, "blanks": 3})
            self.assertNotIn("army", json.dumps(goal))
            self.assertNotIn("elites", json.dumps(goal))
            self.assertNotIn("officials", json.dumps(goal))

    def test_revealed_space_names_the_faction_and_the_cost(self):
        rules = _rules()
        state = _blind_state(rules)
        state["faction_sites_revealed"] = {f"{CARD_ARMY[0]},{CARD_ARMY[1]}":
                                           "army"}
        goals = _goals(state, rules)
        goal = _goal_by_name(goals, "Army support")
        self.assertEqual(goal["target"], CARD_ARMY)
        self.assertEqual(goal["prerequisites"], [
            {"need": "card", "state": "face up", "faction": "army",
             "met": True},
            {"need": "prestige", "cost": rules["succession"]["support_cost"],
             "have": 2, "met": True},
        ])
        self.assertTrue(goal["prerequisites_met"])
        self.assertEqual(goal["steps"], 21)

    def test_seat_that_cannot_pay_shows_the_unmet_prestige(self):
        rules = _rules()
        state = _blind_state(rules)
        state["faction_sites_revealed"] = {f"{CARD_ARMY[0]},{CARD_ARMY[1]}":
                                           "army"}
        state["players"]["P1"]["prestige"] = 0
        goal = _goal_by_name(_goals(state, rules), "Army support")
        self.assertEqual(goal["prerequisites"][1],
                         {"need": "prestige",
                          "cost": rules["succession"]["support_cost"],
                          "have": 0, "met": False})
        self.assertFalse(goal["prerequisites_met"])

    def test_open_board_names_factions_without_card_state(self):
        rules = _rules()
        state = _blind_state(rules)
        state["faction_sites"] = None
        state["faction_sites_revealed"] = None
        goals = _goals(state, rules)
        for faction in sorted(rules["succession"]["faction_cards"]["factions"]):
            goal = _goal_by_name(goals, f"{faction.capitalize()} support")
            self.assertEqual(goal["prerequisites"], [{
                "need": "prestige",
                "cost": rules["succession"]["support_cost"],
                "have": 2, "met": True}])
            self.assertTrue(goal["prerequisites_met"])

    def test_claimant_goal_holds_the_claim_at_zero_steps(self):
        rules = _rules()
        state = _blind_state(rules)
        state.update(turn_index=0, active_player="P0")
        state["players"]["P0"]["pos"] = PERISTYLE[:]
        state["pending_claim"] = {"player": "P0",
                                  "claim_id": state["turn_id"],
                                  "responded": [], "round": state["round"]}
        goal = _goal_by_name(_goals(state, rules), "Peristyle")
        self.assertEqual(goal["prerequisites"],
                         [{"need": "hold_claim", "met": True}])
        self.assertEqual(goal["steps"], 0)
        self.assertTrue(goal["prerequisites_met"])
        self.assertEqual(goal["reach_next_turn"]["probability"], 1.0)

    def test_palace_goals_name_the_checkpoint_districts_and_one_guard_post(self):
        rules = _rules()
        state = engine.new_game(rules, 11, "projection-goals-palace",
                                dict.fromkeys(engine.IDS, "balanced"))
        goals = _goals(state, rules)
        me = next(p for p in (state["players"][state["active_player"]],))
        checkpoint = rules["palace"]["map"]["checkpoint"]
        claim = _goal_by_name(goals, "Checkpoint")
        self.assertEqual(claim["kind"], "claim")
        self.assertEqual(claim["target"], checkpoint)
        self.assertEqual(claim["steps"],
                         _engine_distance(rules, 1, me["pos"], checkpoint))
        self.assertEqual(claim["prerequisites"], [{
            "need": "items",
            "required": rules["palace"]["checkpoint_items_required"],
            "have": 0, "met": False}])
        districts = [g for g in goals if g["kind"] == "treasure"]
        self.assertEqual(len(districts), len(rules["palace"]["map"]["treasure_entries"]))
        for goal in districts:
            self.assertEqual(goal["target"],
                             rules["palace"]["map"]["treasure_entries"][
                                 goal["name"].removeprefix("district ")])
            self.assertEqual(goal["prerequisites"], [])
            self.assertTrue(goal["prerequisites_met"])
            revealed = state["revealed"].get(
                goal["name"].removeprefix("district "))
            if revealed is None:
                self.assertNotIn("item", goal)
            else:
                self.assertEqual(goal["item"], revealed)
        guards = [g for g in goals if g["kind"] == "prestige"]
        self.assertEqual(len(guards), 1)
        posts = rules["palace"]["map"]["guard_posts"]
        nearest = min(posts, key=lambda c: (
            _engine_distance(rules, 1, me["pos"], c), c))
        self.assertEqual(guards[0]["target"], nearest)
        self.assertEqual(guards[0]["steps"],
                         _engine_distance(rules, 1, me["pos"], nearest))
        self.assertGreater(guards[0]["steps"], 0)
        self.assertEqual(guards[0]["prerequisites"], [{
            "need": "prestige_below_cap", "cap": rules["prestige"]["cap"],
            "have": 0, "met": True}])
        self.assertEqual([g["kind"] for g in goals].count("support"), 0)

    def test_seat_at_the_prestige_cap_cannot_guard(self):
        rules = _rules()
        state = engine.new_game(rules, 11, "projection-goals-cap",
                                dict.fromkeys(engine.IDS, "balanced"))
        state["players"][state["active_player"]]["prestige"] = \
            rules["prestige"]["cap"]
        goal = _goal_by_name(_goals(state, rules), "Guard post")
        self.assertFalse(goal["prerequisites"][0]["met"])
        self.assertFalse(goal["prerequisites_met"])

    def test_guard_goal_skips_the_post_underfoot(self):
        rules = _rules()
        state = engine.new_game(rules, 11, "projection-goals-underfoot",
                                dict.fromkeys(engine.IDS, "balanced"))
        post = rules["palace"]["map"]["guard_posts"][0]
        state["players"][state["active_player"]]["pos"] = list(post)
        goal = _goal_by_name(_goals(state, rules), "Guard post")
        self.assertNotEqual(goal["target"], post)
        self.assertGreater(goal["steps"], 0)


class TestGoalAudience(unittest.TestCase):
    def test_two_viewers_get_their_own_distances_and_prerequisites(self):
        rules = _rules()
        revealed = {f"{CARD_ARMY[0]},{CARD_ARMY[1]}": "army"}
        east = _blind_state(rules)
        east["faction_sites_revealed"] = dict(revealed)
        east["players"]["P1"].update(prestige=0, support=[])
        west = copy.deepcopy(east)
        west.update(turn_index=2, active_player="P2")
        # Elites so the army space stays a live goal for both viewers.
        west["players"]["P2"].update(pos=NEAR_PERISTYLE[:], prestige=2,
                                     support=["elites"])
        east_goals = _goals(east, rules, viewer="P1")
        west_goals = _goals(west, rules, viewer="P2")
        self.assertNotEqual(json.dumps(east_goals), json.dumps(west_goals))
        far = _goal_by_name(east_goals, "Peristyle")
        near = _goal_by_name(west_goals, "Peristyle")
        self.assertEqual(far["steps"],
                         _engine_distance(rules, 2, EAST_GATE, PERISTYLE))
        self.assertEqual(near["steps"],
                         _engine_distance(rules, 2, NEAR_PERISTYLE,
                                          PERISTYLE))
        self.assertEqual(far["steps"], 9)
        self.assertEqual(near["steps"], 1)
        far_factions, near_factions = (
            next(p for p in g["prerequisites"] if p["need"] == "factions")
            for g in (far, near))
        self.assertEqual((far_factions["have"], near_factions["have"]),
                         (0, 1))
        far_pay, near_pay = (
            next(p for p in _goal_by_name(goals, "Army support")
                 ["prerequisites"] if p["need"] == "prestige")
            for goals in (east_goals, west_goals))
        self.assertEqual((far_pay["met"], near_pay["met"]), (False, True))


class TestGoalDiscipline(unittest.TestCase):
    def test_goals_read_only_public_fields(self):
        rules = _rules()
        state = _blind_state(rules)
        obs = engine.observe(state, "P1")
        obs["rng"] = "FUTURE_SENTINEL"
        obs["district_equipment"] = {"A": "SECRET_ITEM_SENTINEL"}
        obs["faction_sites"] = {"3,0": "SECRET_FACTION_SENTINEL"}
        # The blind board must answer card questions from card_spaces,
        # never from the open-map faction cells.
        obs["board"]["factions"] = {"3,0": "SECRET_FACTION_SENTINEL"}
        obs["players"]["P1"]["abilities_used"] = "SECRET_ABILITY_SENTINEL"
        for action in obs["legal_actions"]:
            action["item"] = "ACTION_ITEM_SENTINEL"
        projection = candidate_actions.project_observation(obs, rules)
        blob = json.dumps(projection["goals"])
        for sentinel in ("FUTURE_SENTINEL", "SECRET_ITEM_SENTINEL",
                         "SECRET_FACTION_SENTINEL", "SECRET_ABILITY_SENTINEL",
                         "ACTION_ITEM_SENTINEL"):
            self.assertNotIn(sentinel, blob)
        for goal in projection["goals"]:
            self.assertLessEqual(set(goal), GOAL_KEYS | {"hidden_cards", "item"})
            self.assertLessEqual(set(goal["reach_next_turn"]), REACH_KEYS)
            self.assertEqual(goal["prerequisites_met"],
                             all(p["met"] for p in goal["prerequisites"]))

    def test_goal_shape_holds_across_a_real_game(self):
        rules = _rules()
        state = engine.new_game(rules, 2026, "goals-sweep")
        rng = random.Random(7)
        phases = set()
        turns = 0
        while not engine.is_finished(state) and turns < 400:
            obs = engine.observe(state, state["active_player"])
            phases.add(obs["phase"])
            goals = candidate_actions.project_observation(obs, rules)["goals"]
            me = obs["players"][obs["viewer"]]
            start = tuple(me["position"])
            self.assertTrue(goals)
            self.assertEqual(len({g["name"] for g in goals}), len(goals),
                             "goal names repeat within one turn")
            for goal in goals:
                self.assertIn(goal["kind"],
                              ("claim", "support", "treasure", "prestige"))
                self.assertGreaterEqual(goal["steps"], 0)
                self.assertEqual(
                    goal["steps"],
                    _engine_distance(rules, obs["phase"], start,
                                     goal["target"]))
                self.assertEqual(goal["prerequisites_met"],
                                 all(p["met"] for p in goal["prerequisites"]))
                reach = goal["reach_next_turn"]
                span = rules["movement"]["dice"] * rules["movement"]["die_sides"]
                self.assertEqual(reach["kind"],
                                 "exact" if goal["steps"] <= span else "estimate")
                if reach["kind"] == "exact":
                    self.assertTrue(0.0 <= reach["probability"] <= 1.0)
                    self.assertNotIn("turns_at_best", reach)
                else:
                    self.assertNotIn("probability", reach)
                    self.assertEqual(reach["turns_at_best"],
                                     -(-goal["steps"] // span))
            if obs["phase"] == 1:
                self.assertNotIn("support", {g["kind"] for g in goals})
            action_id, _ = policies.act("tactical", obs, rng)
            engine.apply_action(state, state["active_player"],
                                obs["turn_id"], action_id)
            turns += 1
        self.assertEqual(phases, {1, 2})


if __name__ == "__main__":
    unittest.main()
