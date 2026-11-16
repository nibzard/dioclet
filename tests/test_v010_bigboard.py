# ABOUTME: V0.10 big board tests: a palace-size succession map with
# ABOUTME: faction cards dealt face down on street sites (D51).
"""V0.10 big board: a palace-size succession map with faction cards (D51).

The succession map has the palace board's 19x13 footprint, so the real
board can carry it on its back. Pinwheel gates put every seat nine
steps from the Peristyle, and three faction cards plus three blanks are
dealt face down onto six street sites at the phase change.
"""
import json
import os
import random
import unittest

import candidate_actions
import engine
import policies

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_FILE = os.path.join(ROOT, "rules", "imperial-rivals-v0.10.2.json")


def rules():
    return engine.load_rules(RULES_FILE)


def play(value, seed):
    """Play one bot game to the end; return the state."""
    state = engine.new_game(value, seed, f"v010-{seed}", dict.fromkeys(engine.IDS, "balanced"))
    rng = random.Random(f"t:{seed}")
    for _ in range(4 * (value["palace"]["max_rounds"] + value["succession"]["max_rounds"] + 3)):
        if engine.is_finished(state):
            break
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act("balanced", obs, rng)
        engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
    return state


class TestBigBoardGeometry(unittest.TestCase):
    def test_file_validates_with_blind_cards_on_the_twin_map(self):
        value = rules()
        engine.validate_rules(value)
        self.assertEqual(value["succession"]["gate_assignment"], "random")
        self.assertEqual(len(value["succession"]["map"]["card_spaces"]), 6)
        self.assertEqual(value["succession"]["faction_cards"]["empty"], 3)

    def test_succession_map_has_the_palace_footprint(self):
        value = rules()
        self.assertEqual((value["succession"]["map"]["width"], value["succession"]["map"]["height"]),
                         (value["palace"]["map"]["width"], value["palace"]["map"]["height"]))

    def test_every_gate_is_nine_steps_from_the_peristyle(self):
        value = rules()
        b2 = engine.Board(value, "succession")
        cp = tuple(value["succession"]["map"]["checkpoint"])
        for gid, cell in b2.gates.items():
            with self.subTest(gate=gid):
                self.assertEqual(b2.distances(tuple(cell))[cp], 9)

    def test_every_gate_sees_the_same_site_distances(self):
        # The fairness contract: no gate starts closer to the cards.
        value = rules()
        b2 = engine.Board(value, "succession")
        sites = [tuple(c) for c in value["succession"]["map"]["card_spaces"]]
        profiles = {gid: sorted(b2.distances(tuple(c))[s] for s in sites)
                    for gid, c in b2.gates.items()}
        self.assertEqual(len({tuple(p) for p in profiles.values()}), 1, profiles)

    def test_sites_are_symmetric_under_a_half_turn(self):
        value = rules()
        twin = value["succession"]["map"]
        w, h = twin["width"], twin["height"]
        sites = {tuple(c) for c in twin["card_spaces"]}
        self.assertEqual({(w - 1 - x, h - 1 - y) for x, y in sites}, sites)


class TestSupportSiteValidation(unittest.TestCase):
    def rejects(self, mutate):
        value = rules()
        mutate(value)
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(value)

    def test_blind_cards_need_sites_on_a_twin_map(self):
        self.rejects(lambda v: v["succession"]["map"].pop("card_spaces"))

    def test_too_few_sites_are_rejected(self):
        self.rejects(lambda v: v["succession"]["map"].update(card_spaces=[[0, 0], [4, 6]]))

    def test_site_on_a_building_is_rejected(self):
        self.rejects(lambda v: v["succession"]["map"]["card_spaces"].__setitem__(0, [1, 1]))

    def test_site_on_a_gate_is_rejected(self):
        self.rejects(lambda v: v["succession"]["map"]["card_spaces"].__setitem__(0, [6, 0]))

    def test_site_on_the_checkpoint_is_rejected(self):
        self.rejects(lambda v: v["succession"]["map"]["card_spaces"].__setitem__(0, [9, 6]))

    def test_duplicate_sites_are_rejected(self):
        self.rejects(lambda v: v["succession"]["map"]["card_spaces"]
                     .__setitem__(1, v["succession"]["map"]["card_spaces"][0]))


class TestBigBoardDeal(unittest.TestCase):
    def reach_succession(self, seed):
        value = rules()
        state = engine.new_game(value, seed, f"v010-{seed}", dict.fromkeys(engine.IDS, "balanced"))
        rng = random.Random(f"t:{seed}")
        while state["phase"] == 1 and not engine.is_finished(state):
            obs = engine.observe(state, state["active_player"])
            action_id, reason = policies.act("balanced", obs, rng)
            engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
        self.assertEqual(state["phase"], 2, "the game never reached the succession map")
        return value, state

    def test_cards_are_dealt_onto_the_twin_map_sites(self):
        value, state = self.reach_succession(7301)
        sites = {f"{x},{y}" for x, y in value["succession"]["map"]["card_spaces"]}
        self.assertEqual(set(state["faction_sites"]), sites)
        dealt = sorted(f for f in state["faction_sites"].values() if f)
        self.assertEqual(dealt, sorted(value["succession"]["faction_cards"]["factions"]))

    def test_the_deal_stays_hidden_until_searched(self):
        value, state = self.reach_succession(7301)
        self.assertEqual(state.get("faction_sites_revealed"), {})
        obs = engine.observe(state, state["active_player"])
        self.assertEqual(obs["board"]["card_spaces"]["revealed"], {})
        self.assertEqual(sorted(obs["board"]["card_spaces"]["candidates"]),
                         sorted(value["succession"]["map"]["card_spaces"]))
        self.assertNotIn("factions", obs["board"])
        # The deal itself (site key -> faction) appears nowhere in the view.
        blob = json.dumps(obs)
        for key, faction in state["faction_sites"].items():
            if faction:
                self.assertNotIn(f'"{key}": "{faction}"', blob)

    def test_shortlist_keeps_every_search_and_names_it(self):
        value, state = self.reach_succession(7301)
        searches = set()
        for pid in engine.IDS:
            state["active_player"] = pid
            obs = engine.observe(state, pid)
            legal = {a["action_id"] for a in obs["legal_actions"] if a["kind"] == "search_site"}
            built = candidate_actions.build_candidates(obs, value)
            cands = built[0] if isinstance(built, tuple) else built
            kept = {c["action_id"]: c for c in cands if c["kind"] == "search_site"}
            self.assertEqual(set(kept), legal, pid)
            for c in kept.values():
                self.assertIn("Search the face-down faction card", c["description"])
            searches |= legal
        self.assertTrue(searches, "no seat could reach a card on this seed")

    def test_game_finishes_and_replays_the_same(self):
        a, b = play(rules(), 7302), play(rules(), 7302)
        self.assertTrue(engine.is_finished(a))
        engine.check_invariants(a)
        self.assertEqual(engine.result(a), engine.result(b))


class TestSuccessionGuardPosts(unittest.TestCase):
    """The adopted succession map carries four guard posts of its own (D52)."""

    def test_posts_are_fair_from_every_gate(self):
        value = rules()
        self.assertEqual(value["succession"]["map"]["guard_posts"],
                         [[0, 2], [18, 10], [2, 0], [16, 12]])
        b2 = engine.Board(value, "succession")
        posts = [tuple(c) for c in value["succession"]["map"]["guard_posts"]]
        profiles = {gid: sorted(b2.distances(tuple(c))[p] for p in posts)
                    for gid, c in b2.gates.items()}
        self.assertEqual(len({tuple(p) for p in profiles.values()}), 1, profiles)
        cp = tuple(value["succession"]["map"]["checkpoint"])
        self.assertEqual(len({b2.distances(cp)[p] for p in posts}), 1)


class TestSixBlockLayouts(unittest.TestCase):
    """The adopted V0.10.2 spread layout, checked directly (D53)."""

    def test_both_maps_carry_the_full_street_plan(self):
        value = rules()
        for section in ("palace", "succession"):
            b = engine.Board(value, section)
            with self.subTest(section=section):
                self.assertEqual(len(b.distances(b.gates["P0"])), 97)

    def test_layout_is_fair_from_every_gate(self):
        value = rules()
        b2 = engine.Board(value, "succession")
        cp = b2.checkpoint
        self.assertEqual({b2.distances(g)[cp] for g in b2.gates.values()}, {9})
        for key in ("card_spaces", "guard_posts"):
            cells = [tuple(c) for c in value["succession"]["map"][key]]
            profiles = {tuple(sorted(b2.distances(g)[c] for c in cells))
                        for g in b2.gates.values()}
            self.assertEqual(len(profiles), 1, key)


if __name__ == "__main__":
    unittest.main()
