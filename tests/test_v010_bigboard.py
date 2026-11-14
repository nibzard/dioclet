"""V0.10 big board: a palace-size succession map with faction cards (D51).

The succession map has the palace board's 19x13 footprint, so the real
board can carry it on its back. Pinwheel gates put every seat nine
steps from the Peristyle, and three faction cards plus three blanks are
dealt face down onto six street sites at the phase change.
"""
import json
import os
import random
import sys
import unittest

import candidate_actions
import engine
import policies
import succession

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_FILE = os.path.join(ROOT, "rules_v010_bigboard.json")


def rules():
    return engine.load_rules(RULES_FILE)


def play(value, seed):
    """Play one bot game to the end; return the state."""
    state = engine.new_game(value, seed, f"v010-{seed}", dict.fromkeys(succession.IDS, "balanced"))
    rng = random.Random(f"t:{seed}")
    for _ in range(4 * (value["level1"]["max_rounds"] + value["level2"]["max_rounds"] + 3)):
        if engine.is_finished(state):
            break
        obs = engine.observe(state, state["active_player"])
        action_id, reason = policies.act("balanced", obs, rng)
        engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
    return state


class TestBigBoardGeometry(unittest.TestCase):
    def test_file_validates_with_blind_support_on_the_twin_map(self):
        value = rules()
        engine.validate_rules(value)
        self.assertTrue(value["succession"]["blind_support"])
        self.assertEqual(len(value["board_level2"]["support_sites"]), 6)

    def test_succession_map_has_the_palace_footprint(self):
        value = rules()
        self.assertEqual((value["board_level2"]["width"], value["board_level2"]["height"]),
                         (value["board"]["width"], value["board"]["height"]))

    def test_every_gate_is_nine_steps_from_the_peristyle(self):
        value = rules()
        b2 = engine.Board(value, "board_level2")
        cp = tuple(value["board_level2"]["checkpoint"])
        for gid, cell in b2.gates.items():
            with self.subTest(gate=gid):
                self.assertEqual(b2.distances(tuple(cell))[cp], 9)

    def test_every_gate_sees_the_same_site_distances(self):
        # The fairness contract: no gate starts closer to the cards.
        value = rules()
        b2 = engine.Board(value, "board_level2")
        sites = [tuple(c) for c in value["board_level2"]["support_sites"]]
        profiles = {gid: sorted(b2.distances(tuple(c))[s] for s in sites)
                    for gid, c in b2.gates.items()}
        self.assertEqual(len({tuple(p) for p in profiles.values()}), 1, profiles)

    def test_sites_are_symmetric_under_a_half_turn(self):
        value = rules()
        w, h = value["board_level2"]["width"], value["board_level2"]["height"]
        sites = {tuple(c) for c in value["board_level2"]["support_sites"]}
        self.assertEqual({(w - 1 - x, h - 1 - y) for x, y in sites}, sites)


class TestSupportSiteValidation(unittest.TestCase):
    def rejects(self, mutate):
        value = rules()
        mutate(value)
        with self.assertRaises(engine.EngineError):
            engine.validate_rules(value)

    def test_blind_support_needs_sites_on_a_twin_map(self):
        self.rejects(lambda v: v["board_level2"].pop("support_sites"))

    def test_too_few_sites_are_rejected(self):
        self.rejects(lambda v: v["board_level2"].update(support_sites=[[0, 0], [4, 6]]))

    def test_site_on_a_building_is_rejected(self):
        self.rejects(lambda v: v["board_level2"]["support_sites"].__setitem__(0, [1, 1]))

    def test_site_on_a_gate_is_rejected(self):
        self.rejects(lambda v: v["board_level2"]["support_sites"].__setitem__(0, [6, 0]))

    def test_site_on_the_checkpoint_is_rejected(self):
        self.rejects(lambda v: v["board_level2"]["support_sites"].__setitem__(0, [9, 6]))

    def test_duplicate_sites_are_rejected(self):
        self.rejects(lambda v: v["board_level2"]["support_sites"].__setitem__(0, [4, 6]))


class TestBigBoardDeal(unittest.TestCase):
    def reach_phase2(self, seed):
        value = rules()
        state = engine.new_game(value, seed, f"v010-{seed}", dict.fromkeys(succession.IDS, "balanced"))
        rng = random.Random(f"t:{seed}")
        while state["phase"] == 1 and not engine.is_finished(state):
            obs = engine.observe(state, state["active_player"])
            action_id, reason = policies.act("balanced", obs, rng)
            engine.apply_action(state, state["active_player"], obs["turn_id"], action_id, reason)
        self.assertEqual(state["phase"], 2, "the game never reached the succession map")
        return value, state

    def test_cards_are_dealt_onto_the_twin_map_sites(self):
        value, state = self.reach_phase2(7301)
        sites = {f"{x},{y}" for x, y in value["board_level2"]["support_sites"]}
        self.assertEqual(set(state["faction_sites"]), sites)
        dealt = sorted(f for f in state["faction_sites"].values() if f)
        self.assertEqual(dealt, sorted(value["succession"]["factions"]))

    def test_the_deal_stays_hidden_until_searched(self):
        value, state = self.reach_phase2(7301)
        self.assertEqual(state.get("faction_sites_revealed"), {})
        obs = engine.observe(state, state["active_player"])
        self.assertEqual(obs["board"]["support_sites"]["revealed"], {})
        self.assertEqual(sorted(obs["board"]["support_sites"]["candidates"]),
                         sorted(value["board_level2"]["support_sites"]))
        self.assertNotIn("factions", obs["board"])
        # The deal itself (site key -> faction) appears nowhere in the view.
        blob = json.dumps(obs)
        for key, faction in state["faction_sites"].items():
            if faction:
                self.assertNotIn(f'"{key}": "{faction}"', blob)

    def test_shortlist_keeps_every_search_and_names_it(self):
        value, state = self.reach_phase2(7301)
        searches = set()
        for pid in succession.IDS:
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


class TestSuccessionGuardPostsExperiment(unittest.TestCase):
    """rules_v10_l2posts.json: the V0.10 board plus four guard posts (experiment)."""

    def test_adopted_file_is_the_experiment_file(self):
        # D52: 0.10.1-bigboard adopts the experiment arm unchanged.
        adopted = engine.load_rules(os.path.join(ROOT, "rules_v0101_bigboard.json"))
        posts = engine.load_rules(os.path.join(ROOT, "rules_v10_l2posts.json"))
        engine.validate_rules(adopted)
        self.assertEqual(adopted["rules_version"], "0.10.1-bigboard")
        for value in (adopted, posts):
            value.pop("rules_version")
            value.pop("game_name")
        self.assertEqual(adopted, posts)

    def test_posts_file_differs_from_v010_only_by_the_posts(self):
        base, posts = rules(), engine.load_rules(os.path.join(ROOT, "rules_v10_l2posts.json"))
        engine.validate_rules(posts)
        self.assertEqual(posts["board_level2"]["glory_posts"], [[0, 3], [18, 9], [3, 0], [15, 12]])
        for value in (base, posts):
            value["board_level2"].pop("glory_posts", None)
            value.pop("rules_version")
            value.pop("game_name")
        self.assertEqual(base, posts)

    def test_every_gate_sees_the_same_post_distances(self):
        value = engine.load_rules(os.path.join(ROOT, "rules_v10_l2posts.json"))
        b2 = engine.Board(value, "board_level2")
        cp = tuple(value["board_level2"]["checkpoint"])
        posts = [tuple(c) for c in value["board_level2"]["glory_posts"]]
        profiles = {gid: sorted(b2.distances(tuple(c))[p] for p in posts) for gid, c in b2.gates.items()}
        self.assertEqual(len({tuple(p) for p in profiles.values()}), 1, profiles)
        self.assertEqual({b2.distances(cp)[p] for p in posts}, {12})


class TestSixBlockExperiment(unittest.TestCase):
    """rules_v10_six_*.json: six-block succession maps (experiment)."""

    def test_files_match_the_tool_and_are_fair(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import v10_six_blocks as six
        for name in six.ARMS:
            with self.subTest(arm=name):
                value = engine.load_rules(os.path.join(ROOT, six.rules_file(name)))
                engine.validate_rules(value)
                self.assertEqual(value, six.arm_rules(name))
                b2 = engine.Board(value, "board_level2")
                self.assertEqual(len(b2.distances(b2.gates["P0"])), 97)
                cp = tuple(value["board_level2"]["checkpoint"])
                self.assertEqual({b2.distances(g)[cp] for g in b2.gates.values()}, {9})
                for key in ("support_sites", "glory_posts"):
                    cells = [tuple(c) for c in value["board_level2"][key]]
                    profiles = {sorted_tuple for sorted_tuple in
                                (tuple(sorted(b2.distances(g)[c] for c in cells))
                                 for g in b2.gates.values())}
                    self.assertEqual(len(profiles), 1, (name, key))


if __name__ == "__main__":
    unittest.main()
