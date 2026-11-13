"""V0.9 design experiment: start reveals and distinct equipment abilities."""
import copy
import json
import os
import random
import unittest
from unittest.mock import patch

import engine
import policies
import succession

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = ("collector", "early_support", "prestige_farmer", "counterleader")


def rules_v08_raw():
    return engine.load_rules(os.path.join(ROOT, "rules_v08_succession.json"))


def rules_v09b_raw():
    return engine.load_rules(os.path.join(ROOT, "rules_v09_reveal2.json"))


def rules_v09c_raw():
    return engine.load_rules(os.path.join(ROOT, "rules_v09_abilities.json"))


def rules_v09c(start_reveals=0):
    """Staged variant C: manual gates, free contests, chosen start reveals."""
    value = rules_v09c_raw()
    value["succession"]["gate_assignment"] = "manual"
    value["succession"]["contest_cost"] = 0
    value["start_reveals"] = start_reveals
    return value


def game(value=None):
    state = engine.new_game(value or rules_v09c(), 2026, "v09-test", dict.fromkeys(succession.IDS, "balanced"))
    state.update(turn_order=list(succession.IDS), round_start=0, turn_index=0, active_player="P1")
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


class TestV09RulesValidation(unittest.TestCase):
    def test_variant_files_validate(self):
        for loader in (rules_v09b_raw, rules_v09c_raw):
            with self.subTest(loader=loader.__name__):
                self.assertTrue(engine.validate_rules(loader()))

    def test_start_reveals_bounds(self):
        for value in (7, -1, "2", 2.0):
            candidate = rules_v09b_raw()
            candidate["start_reveals"] = value
            with self.subTest(value=value), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)

    def test_misspelled_top_level_knob_rejected(self):
        candidate = rules_v09b_raw()
        candidate["start_reveals_typo"] = 2
        with self.assertRaisesRegex(engine.EngineError, "unknown top-level keys"):
            engine.validate_rules(candidate)

    def test_abilities_need_full_coverage_and_known_types(self):
        base = rules_v09c()
        partial = copy.deepcopy(base)
        del partial["combat"]["abilities"]["gladius"]
        with self.assertRaisesRegex(engine.EngineError, "one ability for each"):
            engine.validate_rules(partial)
        bad_type = copy.deepcopy(base)
        bad_type["combat"]["abilities"]["gladius"]["type"] = "death_ray"
        with self.assertRaisesRegex(engine.EngineError, "type must be one of"):
            engine.validate_rules(bad_type)
        bad_value = copy.deepcopy(base)
        bad_value["combat"]["abilities"]["gladius"]["value"] = 4
        with self.assertRaisesRegex(engine.EngineError, "integer from 0 to 3"):
            engine.validate_rules(bad_value)

    def test_count_tiers_are_zero_in_abilities_file(self):
        rules = rules_v09c()
        for count in range(7):
            self.assertEqual(engine.equipment_bonus(count, rules), 0)

    def test_abilities_may_not_stack_with_nonzero_tiers(self):
        candidate = rules_v09c()
        candidate["combat"]["equipment_bonus_tiers"] = [{"min_count": 3, "max_count": 6, "bonus": 1}]
        with self.assertRaisesRegex(engine.EngineError, "replace the count tiers"):
            engine.validate_rules(candidate)

    def test_baseline_keeps_its_count_tier_bonus_in_duels(self):
        # Guards the regression where the duel rewrite dropped the tier term
        # for rules without an ability table.
        state = game(rules_v09c())
        state["rules"]["combat"].pop("abilities", None)
        state["rules"]["combat"]["equipment_bonus_tiers"] = [
            {"min_count": 0, "max_count": 2, "bonus": 0},
            {"min_count": 3, "max_count": 5, "bonus": 1},
            {"min_count": 6, "max_count": 6, "bonus": 2}]
        state["players"]["P1"]["equipment"] = ["gladius", "scutum", "pilum", "pugio", "galea", "lorica_segmentata"]
        duel_staged(state, "P1", "P2")
        with patch.object(succession, "_die", side_effect=[3, 4, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        duel = next(e for e in record["events"] if e["type"] == "duel")
        self.assertEqual(duel["attacker_bonus"], 2)  # six-item tier, and no ability table present


class TestV09StartReveals(unittest.TestCase):
    def test_matched_seed_keeps_every_shared_stream_identical(self):
        a = engine.new_game(rules_v08_raw(), 300000, "a")
        b = engine.new_game(rules_v09b_raw(), 300000, "b")
        c = engine.new_game(rules_v09c_raw(), 300000, "c")
        for field in ("gate_assignments", "turn_order", "district_equipment", "current_dice"):
            self.assertEqual(a[field], b[field], field)
            self.assertEqual(b[field], c[field], field)
        for stream in ("gates", "order", "movement", "combat"):
            self.assertEqual(a["rng"][stream], b["rng"][stream], stream)
        self.assertEqual(a["revealed"], {})
        self.assertEqual(b["revealed"], c["revealed"])
        self.assertEqual(len(b["revealed"]), 2)
        self.assertEqual(b["setup_reveals"], sorted(b["revealed"]))
        for name, item in b["revealed"].items():
            self.assertEqual(b["district_equipment"][name], item)

    def test_start_reveals_are_public_and_exploitable(self):
        state = game(rules_v09c(start_reveals=2))
        obs = engine.observe(state, state["active_player"])
        self.assertEqual(obs["revealed_districts"], state["revealed"])
        self.assertEqual(len(obs["revealed_districts"]), 2)
        revealed_item = next(iter(state["revealed"].values()))
        self.assertIn(revealed_item, state["district_equipment"].values())
        # A player standing in a start-revealed district may explore it like any
        # revealed district, and hidden districts keep normal explore legality.
        district = next(iter(state["revealed"]))
        cell = state["rules"]["board"]["districts"][district]
        state["players"]["P1"]["pos"] = list(cell)
        active(state, "P1")
        self.assertTrue(any(a["kind"] == "explore" and a["destination"] == cell
                            for a in engine.legal_actions(state)))
        state["players"]["P1"]["equipment"] = [state["revealed"][district]]
        self.assertFalse(any(a["kind"] == "explore" and a["destination"] == cell
                             for a in engine.legal_actions(state)))

    def test_hidden_districts_still_hidden_in_variant_b(self):
        state = engine.new_game(rules_v09b_raw(), 300000, "b")
        hidden = [n for n in state["rules"]["board"]["districts"] if n not in state["revealed"]]
        state["district_equipment"][hidden[0]] = "PRIVATE-SENTINEL"
        obs = engine.observe(state, state["active_player"])
        self.assertNotIn("PRIVATE-SENTINEL", json.dumps(obs))
        self.assertTrue(all("item" not in a for a in obs["legal_actions"]))


class TestV09Abilities(unittest.TestCase):
    def test_gladius_flips_a_lost_duel(self):
        state = game()
        state["players"]["P1"]["equipment"] = ["gladius"]
        duel_staged(state, "P1", "P2")
        with patch.object(succession, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        duel = next(e for e in record["events"] if e["type"] == "duel")
        self.assertEqual(duel["attacker_bonus"], 1)
        self.assertEqual(duel["winner"], "P1")  # 4+1 vs 5 ties, and ties go to the attacker
        self.assertEqual(state["players"]["P1"]["stats"]["attack_bonus_uses"], 1)

    def test_scutum_saves_the_defender(self):
        state = game()
        state["players"]["P2"]["equipment"] = ["scutum"]
        duel_staged(state, "P1", "P2")
        with patch.object(succession, "_die", side_effect=[5, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        duel = next(e for e in record["events"] if e["type"] == "duel")
        self.assertEqual(duel["defender_bonus"], 1)
        self.assertEqual(duel["winner"], "P2")  # 5 vs 5+1; without scutum the tie goes to the attacker
        self.assertEqual(state["players"]["P2"]["stats"]["defense_bonus_uses"], 1)

    def test_pilum_applies_only_against_the_claimant(self):
        state = game()
        state["phase"] = 2
        state["players"]["P1"]["equipment"] = ["pilum"]
        duel_staged(state, "P1", "P2")
        with patch.object(succession, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["attacker_bonus"], 0)
        # Now P2 proclaims and becomes the claimant.
        state["players"]["P2"].update(pos=[6, 6], support=["army", "elites"])
        active(state, "P2")
        take(state, "proclaim")
        duel_staged(state, "P1", "P2", attacker_pos=(6, 4), defender_pos=(6, 6))
        with patch.object(succession, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["attacker_bonus"], 1)
        self.assertEqual(state["players"]["P1"]["stats"]["pilum_uses"], 1)

    def test_pugio_wins_ties_for_the_holder(self):
        # The base rule gives ties to the attacker; a defending pugio flips it.
        state = game()
        duel_staged(state, "P1", "P2")
        with patch.object(succession, "_die", side_effect=[4, 4, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["winner"], "P1")
        state = game()
        state["players"]["P2"]["equipment"] = ["pugio"]
        duel_staged(state, "P1", "P2")
        with patch.object(succession, "_die", side_effect=[4, 4, 3, 3]):
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
        with patch.object(succession, "_die", side_effect=[4, 4, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["winner"], "P1")
        self.assertEqual(state["players"]["P1"]["stats"]["pugio_tiebreaks"], 0)

    def test_equipment_bonuses_do_not_stack(self):
        state = game()
        state["phase"] = 2
        state["players"]["P2"].update(pos=[6, 6], support=["army", "elites"])
        active(state, "P2")
        take(state, "proclaim")
        state["players"]["P1"]["equipment"] = ["gladius", "pilum"]
        duel_staged(state, "P1", "P2", attacker_pos=(6, 4), defender_pos=(6, 6))
        with patch.object(succession, "_die", side_effect=[3, 1, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        duel = next(e for e in record["events"] if e["type"] == "duel")
        self.assertEqual(duel["attacker_bonus"], 1)  # best of gladius/pilum, not the sum

    def test_galea_reveals_publicly_once(self):
        state = game()
        state["players"]["P0"].update(equipment=["galea"], pos=[6, 6])
        active(state, "P0")
        inspects = [a for a in engine.legal_actions(state) if a["kind"] == "inspect"]
        hidden = [n for n in state["rules"]["board"]["districts"] if n not in state["revealed"]]
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
        state["players"]["P0"].update(pos=[6, 6], support=["army", "elites"], equipment=["lorica_segmentata"])
        active(state, "P0")
        take(state, "proclaim")

        def challenge_and_win():
            state["players"]["P1"]["pos"] = [6, 8]
            active(state, "P1")
            with patch.object(succession, "_die", side_effect=[6, 1, 3, 3]):
                take(state, "duel", target="P0", spend_prestige=False)

        challenge_and_win()
        self.assertIsNone(state["pending_claim"])  # the claim is still cancelled
        self.assertEqual(state["players"]["P0"]["pos"], [6, 6])  # but the claimant stays
        self.assertEqual(state["players"]["P0"]["stats"]["lorica_saves"], 1)
        self.assertEqual(state["players"]["P0"]["stats"]["times_displaced"], 0)
        active(state, "P0")
        take(state, "proclaim")
        challenge_and_win()
        self.assertEqual(state["players"]["P0"]["pos"], state["players"]["P0"]["gate"])
        self.assertEqual(state["players"]["P0"]["stats"]["times_displaced"], 1)

    def test_zero_value_ability_is_disabled(self):
        state = game()
        state["rules"]["combat"]["abilities"]["gladius"]["value"] = 0
        state["players"]["P1"]["equipment"] = ["gladius"]
        duel_staged(state, "P1", "P2")
        with patch.object(succession, "_die", side_effect=[4, 5, 3, 3]):
            record = take(state, "duel", target="P2", spend_prestige=False)
        self.assertEqual(next(e for e in record["events"] if e["type"] == "duel")["attacker_bonus"], 0)
        self.assertEqual(state["players"]["P1"]["stats"]["attack_bonus_uses"], 0)


class TestV09Checkpoint(unittest.TestCase):
    def rules_d(self):
        value = engine.load_rules(os.path.join(ROOT, "rules_v09_checkpoint3.json"))
        value["succession"]["gate_assignment"] = "manual"
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
        self.assertEqual(obs["progress"]["players_with_full_equipment"], ["P1"] if len(state["players"]["P1"]["equipment"]) >= 3 else [])

    def test_default_rules_still_require_six(self):
        state = game()
        state["players"]["P1"].update(pos=[6, 6], equipment=["gladius", "scutum", "pilum"])
        active(state, "P1")
        self.assertFalse(any(a["kind"] == "claim_checkpoint" for a in engine.legal_actions(state)))

    def test_set_completion_reward_pays_once(self):
        state = game()
        state["rules"]["glory"]["set_completion_reward"] = 1
        district = next(n for n in sorted(state["rules"]["board"]["districts"]))
        cell = state["rules"]["board"]["districts"][district]
        missing = state["district_equipment"][district]
        five = [i for i in state["rules"]["equipment"] if i != missing][:5]
        state["players"]["P1"].update(pos=list(cell), equipment=five)
        active(state, "P1")
        record = take(state, "explore")
        self.assertEqual(len(state["players"]["P1"]["equipment"]), 6)
        self.assertEqual(state["players"]["P1"]["stats"]["set_completion_awards"], 1)
        self.assertTrue(any(e["type"] == "prestige_earned" and e["cause"] == "set_completion"
                            for e in record["events"]))
        self.assertEqual(state["players"]["P1"]["prestige"], 1)

    def test_new_knobs_are_validated(self):
        for field, value in (("claim_required_equipment", 0), ("claim_required_equipment", 7),
                             ("claim_required_equipment", "3")):
            candidate = self.rules_d()
            candidate["level1"][field.split(".", 1)[1] if "." in field else field] = value
            with self.subTest(value=value), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)
        candidate = self.rules_d()
        candidate["glory"]["set_completion_reward"] = -1
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(candidate)


class TestV09Games(unittest.TestCase):
    def play(self, rules, seed):
        state = engine.new_game(rules, seed, f"c-game-{seed}", dict(zip(succession.IDS, PROBES)))
        rng = random.Random(f"probe:{seed}")
        cap = 4 * (rules["level1"]["max_rounds"] + rules["level2"]["max_rounds"] + 3)
        for _ in range(cap):
            if engine.is_finished(state):
                break
            obs = engine.observe(state, state["active_player"])
            action_id, reason = policies.act(state["policies"][state["active_player"]], obs, rng)
            engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
        return state

    def test_variant_c_game_finishes_with_invariants_and_ability_metrics(self):
        state = self.play(rules_v09c_raw(), 300000)
        self.assertTrue(engine.is_finished(state))
        engine.check_invariants(state)
        result = engine.result(state)
        self.assertIn("ability_used", json.dumps(result["high_impact_events"]) if result["high_impact_events"] else "")
        counters = [p["attack_bonus_uses"] + p["defense_bonus_uses"] + p["pilum_uses"]
                    + p["pugio_tiebreaks"] + p["galea_reveals"] + p["lorica_saves"]
                    for p in result["players"].values()]
        self.assertGreater(sum(counters), 0)

    def test_variant_c_is_deterministic_per_seed(self):
        first = engine.result(self.play(rules_v09c_raw(), 300007))
        second = engine.result(self.play(rules_v09c_raw(), 300007))
        self.assertEqual(first, second)

    def test_policy_uses_galea_when_nothing_is_known(self):
        state = game()
        state["players"]["P0"].update(equipment=["galea"], pos=[6, 6])
        active(state, "P0")
        obs = engine.observe(state, "P0")
        action_id, reason = succession.choose_policy("collector", obs, random.Random(1))
        action = next(a for a in obs["legal_actions"] if a["action_id"] == action_id)
        self.assertEqual(action["kind"], "inspect")
        self.assertIn("galea", reason)


if __name__ == "__main__":
    unittest.main()


class TestV09Court(unittest.TestCase):
    def rules_f3(self):
        value = engine.load_rules(os.path.join(ROOT, "rules_v09f_court.json"))
        value["succession"].update(gate_assignment="manual", contest_cost=0)
        return value

    def test_new_knobs_are_validated(self):
        for field, value in (("claim_window_rounds", 7), ("claim_window_rounds", -1),
                             ("challenge_radius", 9), ("duel_loser_cost", -1),
                             ("proclaim_cost", "1"), ("blind_support", "yes")):
            candidate = self.rules_f3()
            candidate["succession"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(engine.EngineError):
                engine.validate_rules(candidate)

    def test_claim_survives_the_window_instead_of_acclamation(self):
        state = game(self.rules_f3())
        state["phase"] = 2
        state["players"]["P0"].update(pos=[6, 6], support=["army", "elites"])
        active(state, "P0")
        take(state, "proclaim")
        for pid in ("P1", "P2", "P3"):  # all three rivals answer; no crown yet
            active(state, pid)
            take(state, "move")
        self.assertEqual(state["status"], "in_progress")
        state["players"]["P0"]["pos"] = [6, 6]
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
        state["players"]["P0"].update(pos=[6, 6], support=["army", "elites"])
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
        with patch.object(succession, "_die", side_effect=[6, 1, 3, 3]):
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
        self.assertIn("support_sites", obs["board"])
        self.assertNotIn("factions", obs["board"])
        self.assertTrue(all("faction" not in a or a.get("faction") is None
                            or a["kind"] == "gain_support" for a in obs["legal_actions"]))

    def test_blind_support_disables_city_support(self):
        state = game(self.rules_f3())
        cell = [7, 6]  # the officials meeting place
        state["players"]["P0"].update(pos=cell, prestige=1)
        active(state, "P0")
        self.assertFalse(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))
        state["rules"]["succession"]["blind_support"] = False
        self.assertTrue(any(a["kind"] == "gain_support" for a in engine.legal_actions(state)))

    def test_proclaim_cost_gates_the_claim(self):
        state = game(self.rules_f3())
        state["rules"]["succession"]["proclaim_cost"] = 1
        state["phase"] = 2
        state["players"]["P0"].update(pos=[6, 6], support=["army", "elites"], prestige=0)
        active(state, "P0")
        self.assertFalse(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))
        state["players"]["P0"]["prestige"] = 1
        self.assertTrue(any(a["kind"] == "proclaim" for a in engine.legal_actions(state)))

    def test_officials_no_longer_sit_on_the_peristyle(self):
        rules = self.rules_f3()
        self.assertNotEqual(rules["succession"]["factions"]["officials"], rules["board"]["checkpoint"])


class TestV092Geometry(unittest.TestCase):
    def rules_v092(self):
        return engine.load_rules(os.path.join(ROOT, "rules_v092_succession.json"))

    def test_crossflow_file_validates_with_interior_placements(self):
        rules = self.rules_v092()
        engine.validate_rules(rules)
        self.assertEqual(rules["board"]["districts"]["B"], [12, 3])
        self.assertEqual(rules["board"]["districts"]["E"], [6, 9])
        self.assertEqual(rules["board"]["glory_posts"],
                         [[6, 2], [12, 2], [6, 10], [12, 10]])

    def test_interior_districts_still_enter_their_own_blocks(self):
        rules = self.rules_v092()
        buildings = {b["district"]: b for b in rules["board"]["buildings"]}
        for name in ("B", "E"):
            bx, by = rules["board"]["districts"][name]
            block = buildings[name]
            adjacent = any(
                (bx + dx, by + dy) ==
                (x, y)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                for x in range(block["x0"], block["x1"] + 1)
                for y in range(block["y0"], block["y1"] + 1))
            self.assertTrue(adjacent, f"district {name} lost contact with its block")

    def test_east_gate_reaches_the_far_treasure_faster_than_before(self):
        from board import Board
        before = Board(engine.load_rules(os.path.join(ROOT, "rules_v091_succession.json")))
        after = Board(self.rules_v092())
        east = tuple(before.gates["P1"])
        self.assertGreater(
            before.distance(east, tuple(before.districts["B"])),
            after.distance(east, tuple(after.districts["B"])))

    def test_crossflow_game_runs_deterministically(self):
        first = engine.result(game(self.rules_v092()))
        second = engine.result(game(self.rules_v092()))
        self.assertEqual((first["winner"], first["total_rounds"]),
                         (second["winner"], second["total_rounds"]))


class TestCombatKeyGuard(unittest.TestCase):
    def test_unknown_combat_keys_are_rejected(self):
        # The S2 screen once zeroed a nonexistent combat.challenge_bonus
        # while the live knob (succession.challenge_bonus) stayed on:
        # a silent no-op arm. Validation now refuses dead combat keys.
        rules = engine.load_rules(os.path.join(ROOT, "rules_v092_succession.json"))
        rules["combat"]["challenge_bonus"] = 0
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(rules)


class TestV093NoBoost(unittest.TestCase):
    def test_v093_file_validates_without_the_duel_boost(self):
        rules = engine.load_rules(os.path.join(ROOT, "rules_v093_succession.json"))
        engine.validate_rules(rules)
        self.assertEqual(rules["succession"]["challenge_bonus"], 0)
        self.assertNotIn("challenge_bonus", rules["combat"])

    def test_boost_purchase_never_appears_without_the_knob(self):
        rules = engine.load_rules(os.path.join(ROOT, "rules_v093_succession.json"))
        for action in engine.legal_actions(game(rules)):
            self.assertNotIn("spend_prestige", action)
