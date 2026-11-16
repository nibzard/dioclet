# ABOUTME: Behavior tests for the V0.9-era features that survive in the
# ABOUTME: adopted V0.10.2 rules: reveals, abilities, court, twin board.
"""Surviving V0.9 features, pinned to the adopted rules file.

Start reveals, distinct equipment abilities, the checkpoint claim, the
claim court (window, shame, blind faction cards), and the twin board are
now part of rules/imperial-rivals-v0.10.2.json, so these tests load that
file instead of the retired experiment variants.
"""
import copy
import json
import os
import random
import unittest
from unittest.mock import patch

import engine
import policies

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")
PROBES = ("collector", "early_support", "prestige_farmer", "counterleader")
# The Peristyle (succession checkpoint) and a street one circle away.
PERISTYLE = [9, 6]
NEAR_PERISTYLE = [8, 6]


def rules_raw():
    return engine.load_rules(RULES_PATH)


def game(value=None):
    state = engine.new_game(value or rules_raw(), 2026, "v09-test", dict.fromkeys(engine.IDS, "balanced"))
    state.update(turn_order=list(engine.IDS), round_start=0, turn_index=0, active_player="P1")
    state["current_roll"], state["current_dice"] = 6, [3, 3]
    return state


def take(state, kind, **fields):
    actions = engine.legal_actions(state)
    action = next(a for a in actions if a["kind"] == kind and all(a.get(k) == v for k, v in fields.items()))
    return engine.apply_action(state, state["active_player"], state["turn_id"], action["action_id"])


def active(state, pid):
    state["turn_index"] = engine.current_order(state).index(pid)
    state["active_player"] = pid
    state["current_roll"], state["current_dice"] = 6, [3, 3]


def duel_staged(state, attacker, defender, attacker_pos=(6, 4), defender_pos=(6, 6)):
    state["players"][attacker]["pos"] = list(attacker_pos)
    state["players"][defender]["pos"] = list(defender_pos)
    active(state, attacker)


class TestRulesValidation(unittest.TestCase):
    def test_start_reveals_bounds(self):
        for value in (7, -1, "2", 2.0):
            candidate = rules_raw()
            candidate["treasures"]["start_face_up"] = value
            with self.subTest(value=value), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)

    def test_misspelled_top_level_knob_rejected(self):
        candidate = rules_raw()
        candidate["start_reveals_typo"] = 2
        with self.assertRaisesRegex(engine.EngineError, "unknown top-level keys"):
            engine.validate_rules(candidate)

    def test_abilities_need_full_coverage_and_known_types(self):
        base = rules_raw()
        partial = copy.deepcopy(base)
        del partial["treasures"]["abilities"]["gladius"]
        with self.assertRaisesRegex(engine.EngineError, "missing treasures.abilities keys"):
            engine.validate_rules(partial)
        bad_type = copy.deepcopy(base)
        bad_type["treasures"]["abilities"]["gladius"]["type"] = "death_ray"
        with self.assertRaisesRegex(engine.EngineError, "type must be one of"):
            engine.validate_rules(bad_type)
        bad_value = copy.deepcopy(base)
        bad_value["treasures"]["abilities"]["gladius"]["value"] = 4
        with self.assertRaisesRegex(engine.EngineError, "integer from 0 to 3"):
            engine.validate_rules(bad_value)


class TestStartReveals(unittest.TestCase):
    def test_matched_seed_reproduces_setup_and_reveals_two(self):
        a = engine.new_game(rules_raw(), 300000, "a")
        b = engine.new_game(rules_raw(), 300000, "b")
        for field in ("gate_assignments", "turn_order", "district_equipment", "current_dice"):
            self.assertEqual(a[field], b[field], field)
        for stream in ("gates", "order", "movement", "combat", "equipment"):
            self.assertEqual(a["rng"][stream], b["rng"][stream], stream)
        self.assertEqual(len(b["revealed"]), 2)
        self.assertEqual(b["setup_reveals"], sorted(b["revealed"]))
        for name, item in b["revealed"].items():
            self.assertEqual(b["district_equipment"][name], item)

    def test_start_reveals_are_public_and_exploitable(self):
        state = game()
        obs = engine.observe(state, state["active_player"])
        self.assertEqual(obs["revealed_districts"], state["revealed"])
        self.assertEqual(len(obs["revealed_districts"]), 2)
        revealed_item = next(iter(state["revealed"].values()))
        self.assertIn(revealed_item, state["district_equipment"].values())
        # A player standing in a start-revealed district may explore it like any
        # revealed district, and hidden districts keep normal explore legality.
        district = next(iter(state["revealed"]))
        cell = state["rules"]["palace"]["map"]["treasure_entries"][district]
        state["players"]["P1"]["pos"] = list(cell)
        active(state, "P1")
        self.assertTrue(any(a["kind"] == "explore" and a["destination"] == cell
                            for a in engine.legal_actions(state)))
        state["players"]["P1"]["equipment"] = [state["revealed"][district]]
        self.assertFalse(any(a["kind"] == "explore" and a["destination"] == cell
                             for a in engine.legal_actions(state)))

    def test_hidden_districts_still_hidden(self):
        state = engine.new_game(rules_raw(), 300000, "b")
        entries = state["rules"]["palace"]["map"]["treasure_entries"]
        hidden = [n for n in entries if n not in state["revealed"]]
        state["district_equipment"][hidden[0]] = "PRIVATE-SENTINEL"
        obs = engine.observe(state, state["active_player"])
        self.assertNotIn("PRIVATE-SENTINEL", json.dumps(obs))
        self.assertTrue(all("item" not in a for a in obs["legal_actions"]))


class TestAbilities(unittest.TestCase):
    def test_gladius_flips_a_lost_duel(self):
        state = game()
        state["players"]["P1"]["equipment"] = ["gladius"]
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        duel = next(e for e in record["events"] if e["type"] == "duel")
        self.assertEqual(duel["attacker_bonus"], 1)
        self.assertEqual(duel["winner"], "P1")  # 4+1 vs 5 ties, and ties go to the attacker
        self.assertEqual(state["players"]["P1"]["stats"]["attack_bonus_uses"], 1)

    def test_scutum_saves_the_defender(self):
        state = game()
        state["players"]["P2"]["equipment"] = ["scutum"]
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[5, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        duel = next(e for e in record["events"] if e["type"] == "duel")
        self.assertEqual(duel["defender_bonus"], 1)
        self.assertEqual(duel["winner"], "P2")  # 5 vs 5+1; without scutum the tie goes to the attacker
        self.assertEqual(state["players"]["P2"]["stats"]["defense_bonus_uses"], 1)

    def test_pilum_applies_only_against_the_claimant(self):
        state = game()
        state["phase"] = 2
        # Two Prestige: the first duel is lost (shame costs one), and the
        # claim contest still needs its fee afterwards.
        state["players"]["P1"].update(equipment=["pilum"], prestige=2)
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["attacker_bonus"], 0)
        # Now P2 proclaims and becomes the claimant.
        state["players"]["P2"].update(pos=PERISTYLE[:], support=["army", "elites"])
        active(state, "P2")
        take(state, "proclaim")
        duel_staged(state, "P1", "P2", attacker_pos=tuple(NEAR_PERISTYLE),
                    defender_pos=tuple(PERISTYLE))
        with patch.object(engine, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["attacker_bonus"], 1)
        self.assertEqual(state["players"]["P1"]["stats"]["pilum_uses"], 1)

    def test_pugio_wins_ties_for_the_holder(self):
        # The base rule gives ties to the attacker; a defending pugio flips it.
        state = game()
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[4, 4, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["winner"], "P1")
        state = game()
        state["players"]["P2"]["equipment"] = ["pugio"]
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[4, 4, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["winner"], "P2")
        self.assertEqual(state["players"]["P2"]["stats"]["pugio_tiebreaks"], 1)
        self.assertTrue(any(e["type"] == "ability_used" and e.get("ability") == "pugio"
                            for e in record["events"]))

    def test_pugio_versus_pugio_falls_back_to_the_base_tie_rule(self):
        state = game()
        state["players"]["P1"]["equipment"] = ["pugio"]
        state["players"]["P2"]["equipment"] = ["pugio"]
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[4, 4, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["winner"], "P1")
        self.assertEqual(state["players"]["P1"]["stats"]["pugio_tiebreaks"], 0)

    def test_equipment_bonuses_do_not_stack(self):
        state = game()
        state["phase"] = 2
        state["players"]["P2"].update(pos=PERISTYLE[:], support=["army", "elites"])
        active(state, "P2")
        take(state, "proclaim")
        state["players"]["P1"].update(equipment=["gladius", "pilum"], prestige=1)
        duel_staged(state, "P1", "P2", attacker_pos=tuple(NEAR_PERISTYLE),
                    defender_pos=tuple(PERISTYLE))
        with patch.object(engine, "_die", side_effect=[3, 1, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        duel = next(e for e in record["events"] if e["type"] == "duel")
        self.assertEqual(duel["attacker_bonus"], 1)  # best of gladius/pilum, not the sum

    def test_galea_reveals_publicly_once(self):
        state = game()
        state["players"]["P0"].update(equipment=["galea"], pos=[6, 6])
        active(state, "P0")
        inspects = [a for a in engine.legal_actions(state) if a["kind"] == "inspect"]
        hidden = [n for n in state["rules"]["palace"]["map"]["treasure_entries"]
                  if n not in state["revealed"]]
        self.assertEqual(sorted(a["district"] for a in inspects), sorted(hidden))
        target = hidden[0]
        item = state["district_equipment"][target]
        record = take(state, "inspect", district=target)
        self.assertEqual(state["revealed"][target], item)  # public for everyone
        self.assertTrue(any(e["type"] == "district_revealed" and e["district"] == target
                            for e in record["events"]))
        self.assertEqual(state["players"]["P0"]["stats"]["galea_reveals"], 1)
        obs = engine.observe(state, state["active_player"])
        self.assertEqual(obs["revealed_districts"].get(target), item)
        self.assertTrue(all(a["kind"] != "inspect" for a in obs["legal_actions"]))
        engine.check_invariants(state)

    def test_lorica_prevents_displacement_once(self):
        state = game()
        state["phase"] = 2
        state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"],
                                      equipment=["lorica_segmentata"])
        active(state, "P0")
        take(state, "proclaim")

        def challenge_and_win():
            state["players"]["P1"].update(pos=NEAR_PERISTYLE[:], prestige=1)
            active(state, "P1")
            with patch.object(engine, "_die", side_effect=[6, 1, 3, 3]):
                take(state, "duel", target="P0", spend_prestige=False)

        challenge_and_win()
        self.assertIsNone(state["pending_claim"])  # the claim is still cancelled
        self.assertEqual(state["players"]["P0"]["pos"], PERISTYLE)  # but the claimant stays
        self.assertEqual(state["players"]["P0"]["stats"]["lorica_saves"], 1)
        self.assertEqual(state["players"]["P0"]["stats"]["times_displaced"], 0)
        active(state, "P0")
        take(state, "proclaim")
        challenge_and_win()
        self.assertEqual(state["players"]["P0"]["pos"],
                         engine._gate_cell(state, state["players"]["P0"]))
        self.assertEqual(state["players"]["P0"]["stats"]["times_displaced"], 1)

    def test_zero_value_ability_is_disabled(self):
        state = game()
        state["rules"]["treasures"]["abilities"]["gladius"]["value"] = 0
        state["players"]["P1"]["equipment"] = ["gladius"]
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["attacker_bonus"], 0)
        self.assertEqual(state["players"]["P1"]["stats"]["attack_bonus_uses"], 0)


class TestCheckpoint(unittest.TestCase):
    def rules_d(self):
        value = rules_raw()
        value["palace"]["checkpoint_items_required"] = 3
        return value

    def test_checkpoint_requirement_is_rule_driven(self):
        state = game(self.rules_d())
        state["players"]["P1"].update(pos=[6, 6], equipment=["gladius", "scutum", "pilum"])
        active(state, "P1")
        self.assertTrue(any(a["kind"] == "claim_checkpoint" for a in engine.legal_actions(state)))
        state["players"]["P1"]["equipment"] = ["gladius", "scutum"]
        self.assertFalse(any(a["kind"] == "claim_checkpoint" for a in engine.legal_actions(state)))
        obs = engine.observe(state, "P1")
        self.assertEqual(obs["progress"]["claim_required_equipment"], 3)
        self.assertEqual(obs["progress"]["players_with_full_equipment"], [])

    def test_default_rules_still_require_six(self):
        state = game()
        state["players"]["P1"].update(pos=[6, 6], equipment=["gladius", "scutum", "pilum"])
        active(state, "P1")
        self.assertFalse(any(a["kind"] == "claim_checkpoint" for a in engine.legal_actions(state)))

    def test_checkpoint_knobs_are_validated(self):
        for value in (0, 7, "3"):
            candidate = self.rules_d()
            candidate["palace"]["checkpoint_items_required"] = value
            with self.subTest(value=value), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)


class TestGames(unittest.TestCase):
    def play(self, rules, seed):
        state = engine.new_game(rules, seed, f"c-game-{seed}", dict(zip(engine.IDS, PROBES)))
        rng = random.Random(f"probe:{seed}")
        cap = 4 * (rules["palace"]["max_rounds"] + rules["succession"]["max_rounds"] + 3)
        for _ in range(cap):
            if engine.is_finished(state):
                break
            obs = engine.observe(state, state["active_player"])
            action_id, reason = policies.act(state["policies"][state["active_player"]], obs, rng)
            engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
        return state

    def test_game_finishes_with_invariants_and_ability_metrics(self):
        state = self.play(rules_raw(), 300000)
        self.assertTrue(engine.is_finished(state))
        engine.check_invariants(state)
        result = engine.result(state)
        counters = [p["attack_bonus_uses"] + p["defense_bonus_uses"] + p["pilum_uses"]
                    + p["pugio_tiebreaks"] + p["galea_reveals"] + p["lorica_saves"]
                    for p in result["players"].values()]
        self.assertGreater(sum(counters), 0)

    def test_games_are_deterministic_per_seed(self):
        first = engine.result(self.play(rules_raw(), 300007))
        second = engine.result(self.play(rules_raw(), 300007))
        self.assertEqual(first, second)

    def test_policy_uses_galea_when_nothing_is_known(self):
        state = game()
        state["revealed"] = {}  # the policy inspects only when nothing is known
        state["players"]["P0"].update(equipment=["galea"], pos=[6, 6])
        active(state, "P0")
        obs = engine.observe(state, "P0")
        action_id, reason = engine.choose_policy("collector", obs, random.Random(1))
        action = next(a for a in obs["legal_actions"] if a["action_id"] == action_id)
        self.assertEqual(action["kind"], "inspect")
        self.assertIn("galea", reason)


if __name__ == "__main__":
    unittest.main()


class TestCourt(unittest.TestCase):
    def rules_f3(self):
        value = rules_raw()
        return value

    def test_new_knobs_are_validated(self):
        for field, value in (("claim_window_rounds", 7), ("claim_window_rounds", -1),
                             ("proclaim_cost", "1")):
            candidate = self.rules_f3()
            candidate["succession"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)
        candidate = self.rules_f3()
        candidate["prestige"]["duel_loss_penalty"] = -1
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(candidate)

    def test_claim_survives_the_window_instead_of_acclamation(self):
        state = game(self.rules_f3())
        state["phase"] = 2
        state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"])
        active(state, "P0")
        take(state, "proclaim")
        for pid in ("P1", "P2", "P3"):  # all three rivals answer; no crown yet
            active(state, pid)
            take(state, "move")
        self.assertEqual(state["status"], "in_progress")
        state["players"]["P0"]["pos"] = PERISTYLE[:]
        for _ in range(16):  # let the rounds roll; nobody challenges
            if engine.is_finished(state):
                break
            actions = engine.legal_actions(state)
            kind = "maintain_claim" if any(a["kind"] == "maintain_claim" for a in actions) else "move"
            take(state, kind)
        self.assertEqual(state["winner"], "P0")
        self.assertEqual(state["end_reason"], "survived_window")
        engine.check_invariants(state)

    def test_window_zero_keeps_acclamation(self):
        state = game(self.rules_f3())
        state["rules"]["succession"]["claim_window_rounds"] = 0
        state["phase"] = 2
        state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"])
        active(state, "P0")
        take(state, "proclaim")
        for pid in ("P1", "P2", "P3"):
            active(state, pid)
            take(state, "move")
        self.assertEqual(state["winner"], "P0")
        self.assertEqual(state["end_reason"], "acclamation")

    def test_duel_loser_pays_shame(self):
        state = game(self.rules_f3())
        state["players"]["P1"]["prestige"] = 2
        state["players"]["P2"]["prestige"] = 1
        duel_staged(state, "P1", "P2")
        with patch.object(engine, "_die", side_effect=[6, 1, 3, 3]):
            take(state, "duel", target="P2", spend_prestige=False)
        # P2 lost: paid 1 shame; P1 won: earned the duel reward, no shame.
        self.assertEqual(state["players"]["P2"]["prestige"], 0)
        self.assertEqual(state["players"]["P2"]["stats"]["shame_prestige_paid"], 1)
        self.assertEqual(state["players"]["P1"]["stats"]["shame_prestige_paid"], 0)
        self.assertEqual(state["players"]["P1"]["prestige"], 3)  # 2 + duel reward, capped at 3

    def test_blind_support_search_reveals_and_pays(self):
        state = game(self.rules_f3())
        state["faction_sites"] = {"2,2": "elites", "4,2": "officials", "6,8": "army"}
        state["faction_sites_revealed"] = {}
        state["phase"] = 2
        state["players"]["P0"].update(pos=[6, 8], prestige=1)
        active(state, "P0")
        actions = engine.legal_actions(state)
        self.assertTrue(any(a["kind"] == "search_site" for a in actions))
        take(state, "search_site")
        self.assertEqual(state["faction_sites_revealed"]["6,8"], "army")
        active(state, "P0")
        self.assertTrue(any(a["kind"] == "gain_support" and a.get("faction") == "army"
                            for a in engine.legal_actions(state)))
        take(state, "gain_support")
        self.assertEqual(state["players"]["P0"]["support"], ["army"])
        engine.check_invariants(state)

    def test_blind_support_does_not_leak_the_deal(self):
        state = game(self.rules_f3())
        state["faction_sites"] = {"6,6": "PRIVATE-FACTION", "6,8": None}
        state["faction_sites_revealed"] = {}
        state["phase"] = 2
        obs = engine.observe(state, state["active_player"])
        blob = json.dumps(obs)
        self.assertNotIn("PRIVATE-FACTION", blob)
        self.assertIn("card_spaces", obs["board"])
        self.assertNotIn("factions", obs["board"])
        self.assertTrue(all("faction" not in a or a.get("faction") is None
                            or a["kind"] == "gain_support" for a in obs["legal_actions"]))

    def test_city_support_waits_for_a_revealed_card(self):
        # Without the blind deal the fallback sells support at the fixed
        # faction cells; once the cards are dealt, only a revealed card
        # that holds a faction sells support.
        state = game(self.rules_f3())
        state["phase"] = 2
        cell = engine._faction_cells(state["rules"])["elites"]
        state["players"]["P0"].update(pos=list(cell), prestige=1)
        active(state, "P0")
        self.assertTrue(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))
        key = f"{cell[0]},{cell[1]}"
        state["faction_sites"] = {"3,0": "army", key: None}
        state["faction_sites_revealed"] = {}
        self.assertFalse(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))

    def test_proclaim_cost_gates_the_claim(self):
        state = game(self.rules_f3())
        state["rules"]["succession"]["proclaim_cost"] = 1
        state["phase"] = 2
        state["players"]["P0"].update(pos=PERISTYLE[:], support=["army", "elites"], prestige=0)
        active(state, "P0")
        self.assertFalse(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))
        state["players"]["P0"]["prestige"] = 1
        self.assertTrue(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))

    def test_officials_do_not_sit_on_the_peristyle(self):
        rules = self.rules_f3()
        self.assertNotEqual(engine._faction_cells(rules)["officials"],
                            rules["succession"]["map"]["checkpoint"])


class TestGeometry(unittest.TestCase):
    def test_adopted_file_keeps_interior_placements(self):
        rules = rules_raw()
        engine.validate_rules(rules)
        self.assertEqual(rules["palace"]["map"]["treasure_entries"]["B"], [12, 3])
        self.assertEqual(rules["palace"]["map"]["treasure_entries"]["E"], [6, 9])
        self.assertEqual(rules["palace"]["map"]["guard_posts"],
                         [[6, 2], [12, 2], [6, 10], [12, 10]])

    def test_interior_districts_still_enter_their_own_blocks(self):
        rules = rules_raw()
        board_map = rules["palace"]["map"]
        buildings = {b["district"]: b for b in board_map["buildings"]}
        for name in ("B", "E"):
            bx, by = board_map["treasure_entries"][name]
            block = buildings[name]
            adjacent = any(
                (bx + dx, by + dy) ==
                (x, y)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                for x in range(block["x0"], block["x1"] + 1)
                for y in range(block["y0"], block["y1"] + 1))
            self.assertTrue(adjacent, f"district {name} lost contact with its block")

    def test_games_run_deterministically(self):
        def head():
            state = game()
            rng = random.Random("geo")
            for _ in range(40):
                obs = engine.observe(state, state["active_player"])
                action_id, _ = policies.act("balanced", obs, rng)
                engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, "probe")
            return json.dumps(state["events"], sort_keys=True)
        self.assertEqual(head(), head())


class TestDeadKeyGuard(unittest.TestCase):
    def test_unknown_duels_keys_are_rejected(self):
        # The S2 screen once zeroed a nonexistent combat.challenge_bonus
        # while the live knob stayed on: a silent no-op arm. Validation
        # still refuses keys the engine does not read.
        rules = rules_raw()
        rules["duels"]["challenge_bonus"] = 0
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(rules)


class TestNoPaidBoost(unittest.TestCase):
    def test_no_paid_boost_offer_exists(self):
        state = game()
        # Two adjacent seats with Prestige to burn: the retired trap offer
        # (pay 1 for a +0 boost) must stay gone.
        state["players"]["P0"].update(pos=[6, 6], prestige=3)
        state["players"]["P1"].update(pos=[7, 6], prestige=3)
        active(state, "P0")
        actions = engine.legal_actions(state)
        self.assertTrue(any(a["kind"] == "duel" for a in actions))
        self.assertFalse([a for a in actions if a.get("spend_prestige")])

    def test_the_contest_fee_gates_a_challenge(self):
        state = game()
        state["phase"] = 2
        state["players"]["P0"].update(pos=PERISTYLE[:], prestige=3, support=["army", "elites"])
        active(state, "P0")
        take(state, "proclaim")
        state["players"]["P1"].update(pos=NEAR_PERISTYLE[:], prestige=0)
        active(state, "P1")
        self.assertFalse([a for a in engine.legal_actions(state)
                          if a["kind"] == "duel" and a["target"] == "P0"])
        state["players"]["P1"]["prestige"] = 1
        contests = [a for a in engine.legal_actions(state)
                    if a["kind"] == "duel" and a["target"] == "P0"]
        self.assertTrue(contests)
        self.assertEqual(contests[0]["contest_cost"], 1)


class TestTwinBoard(unittest.TestCase):
    def rules_twin(self):
        return rules_raw()

    def test_twin_file_validates_and_declares_its_map(self):
        rules = self.rules_twin()
        engine.validate_rules(rules)
        twin = rules["succession"]["map"]
        self.assertEqual(twin["gates"]["north"], [6, 0])
        self.assertEqual(twin["checkpoint"], [9, 6])
        self.assertNotIn("treasure_entries", twin)
        self.assertIn("card_spaces", twin)

    def test_transition_moves_every_seat_to_the_succession_gate(self):
        rules = self.rules_twin()
        state = engine.new_game(rules, 7101, "twin-transition",
                                dict.fromkeys(engine.IDS, "balanced"))
        rng = random.Random("t:7101")
        b2 = engine.Board(rules, "succession")
        seen_succession = False
        for _ in range(4 * (rules["palace"]["max_rounds"] + rules["succession"]["max_rounds"] + 3)):
            if engine.is_finished(state):
                break
            obs = engine.observe(state, state["active_player"])
            action_id, reason = policies.act("balanced", obs, rng)
            engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
            if state["phase"] == 2 and not seen_succession:
                seen_succession = True
                for pid, player in state["players"].items():
                    self.assertEqual(player["pos"], list(b2.gates[player["gate_id"]]),
                                     f"{pid} did not return to the succession gate")
        self.assertTrue(seen_succession, "the game never reached the succession map")

    def test_no_support_offers_on_the_palace_map(self):
        rules = self.rules_twin()
        state = game(rules)
        state["phase"] = 1
        cell = engine._faction_cells(rules)["elites"]
        for player in state["players"].values():
            player.update(pos=list(cell), prestige=3)
        active(state, "P0")
        for action in engine.legal_actions(state):
            self.assertNotEqual(action["kind"], "gain_support")

    def test_support_offers_on_the_succession_map(self):
        rules = self.rules_twin()
        state = game(rules)
        state["phase"] = 2
        cell = engine._faction_cells(rules)["elites"]
        for player in state["players"].values():
            player.update(pos=list(cell), prestige=3)
        active(state, "P0")
        self.assertTrue([a for a in engine.legal_actions(state) if a["kind"] == "gain_support"])

    def test_succession_displacement_lands_on_the_succession_gate(self):
        rules = self.rules_twin()
        state = game(rules)
        state["phase"] = 2
        state["players"]["P1"].update(pos=PERISTYLE[:], prestige=3, support=["army", "elites"])
        state["players"]["P0"].update(pos=NEAR_PERISTYLE[:], prestige=3)
        state["pending_claim"] = {"player": "P1", "claim_id": state["turn_id"],
                                  "round": state["round"], "responded": []}
        active(state, "P0")
        duels = [a for a in engine.legal_actions(state)
                 if a["kind"] == "duel" and a["target"] == "P1"]
        self.assertTrue(duels)
        engine.apply_action(state, "P0", state["turn_id"], duels[0]["action_id"])
        pos = state["players"]["P1"]["pos"]
        # A beaten claimant returns to their gate ON THE SUCCESSION MAP;
        # a claimant who held the duel keeps the Peristyle.
        self.assertIn(pos, (PERISTYLE, engine._gate_cell(state, state["players"]["P1"])))

    def test_twin_game_runs_and_finishes(self):
        result = engine.result(game(self.rules_twin()))
        self.assertIn(result["outcome"], ("win", "draw"))

    def test_succession_gate_cannot_start_on_content(self):
        for gate, cell in (("north", PERISTYLE), ("north", [9, 4]), ("north", [3, 0])):
            candidate = rules_raw()
            candidate["succession"]["map"]["gates"][gate] = cell
            with self.subTest(gate=gate, cell=cell), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)
