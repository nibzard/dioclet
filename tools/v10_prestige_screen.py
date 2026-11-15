"""V0.10 Prestige screen: five one-knob arms on matched seeds (768 games).

Usage: python3 tools/v10_prestige_screen.py 768 1050000 [arm,arm,...]
Arms: base, shame0 (duel_loser_cost 0), free_contest (contest_cost 0),
posts (four succession-map guard posts), posts_shame0, window3
(claim_window_rounds 3), posts_window3. Writes
results/v10-prestige/screen-<seed>-<arms>.json. The confirmation run is
tools/v10_prestige_experiment.py. Bot profiles only.
"""
import json, os, random, sys, concurrent.futures, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools")]
import engine, policies
from v09_hillclimb import schedule
from v10_level2_experiment import summarize

POSTS = [[0, 3], [18, 9], [3, 0], [15, 12]]
def arm_rules(name):
    r = engine.load_rules(os.path.join(ROOT, "experiments/rules/rules_v010_bigboard.json"))
    if "shame0" in name: r["succession"]["duel_loser_cost"] = 0
    if "free" in name: r["succession"]["contest_cost"] = 0
    if "posts" in name: r["board_level2"]["glory_posts"] = POSTS
    if "window3" in name: r["succession"]["claim_window_rounds"] = 3
    return r
ARMS = sys.argv[3].split(",") if len(sys.argv) > 3 else ["base", "shame0", "free_contest", "posts", "posts_shame0"]

def play(args):
    name, index, seed_base = args
    rules = arm_rules(name)
    order, assignment = schedule(index)
    rules["succession"]["gate_assignment"] = "manual"; rules["succession"]["gate_order"] = list(order)
    seed = seed_base + index
    st = engine.new_game(rules, seed, f"g{seed}", assignment)
    rng = random.Random(f"probe:{seed}")
    fee = rules["succession"].get("contest_cost", 0)
    claims = []          # (rivals able to contest, cancelled?)
    broke_turns = phase2_turns = 0
    last_claim = None
    for _ in range(4 * (rules["level1"]["max_rounds"] + rules["level2"]["max_rounds"] + 3)):
        if engine.is_finished(st): break
        pid = st["active_player"]
        if st["phase"] == 2:
            phase2_turns += 1
            broke_turns += st["players"][pid]["prestige"] == 0
        obs = engine.observe(st, pid)
        a, why = policies.act(assignment[pid], obs, rng)
        engine.apply_action(st, pid, obs["turn_id"], a, why)
        pc = st.get("pending_claim")
        if st["phase"] == 2 and pc and pc.get("claim_id") != last_claim:
            last_claim = pc.get("claim_id")
            able = sum(1 for q, p in st["players"].items() if q != pc["player"] and p["prestige"] >= max(fee, 1))
            claims.append(able)
    engine.check_invariants(st)
    res = engine.result(st)
    gate_of = {p: v["gate_id"] for p, v in res["players"].items()}
    sr = {p: [] for p in gate_of}; searches = 0
    for rec in st["events"]:
        if rec.get("phase") != 2: continue
        for e in rec["events"]:
            if e.get("type") == "support_gained": sr[e["player"]].append(rec["round"])
            elif e.get("type") == "support_site_revealed": searches += 1
    return {
        "winner_gate": gate_of.get(res["winner"]) if res["winner"] else None,
        "end_reason": res["end_reason"], "rounds_level1": res["rounds_level1"],
        "rounds_level2": res["rounds_level2"], "total_rounds": res["total_rounds"],
        "claims": sum(p["claims_made"] for p in res["players"].values()),
        "first_challenger": res["first_challenger"], "first_challenger_won": res["first_challenger_won"],
        "winner_profile": res["policies"].get(res["winner"]) if res["winner"] else None,
        "support_rounds_by_gate": {gate_of[p]: r for p, r in sr.items()}, "searches": searches,
        "claim_able": claims, "broke": broke_turns, "p2turns": phase2_turns,
    }

if __name__ == "__main__":
    n, base = int(sys.argv[1]), int(sys.argv[2])
    out = {}
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for name in ARMS:
            games = list(pool.map(play, [(name, i, base) for i in range(n)], chunksize=8))
            s = summarize(name, games)
            able = [a for g in games for a in g["claim_able"]]
            s["claims_seen"] = len(able)
            s["claims_no_rival_can_contest"] = round(sum(a == 0 for a in able) / len(able), 3)
            s["mean_rivals_able"] = round(statistics.mean(able), 2)
            s["phase2_turns_broke"] = round(sum(g["broke"] for g in games) / sum(g["p2turns"] for g in games), 3)
            out[name] = s
            g = s["gate_win_rates"]; l = s["level2_rounds"]
            print(f"{name:13} draw {s['draw_rate']:.3f} L2 {l['p10']}/{l['median']}/{l['p90']} tot {s['median_rounds']} "
                  f"gates {'/'.join(f'{g[x][0]:.3f}' for x in ('P0','P1','P2','P3'))} p {s['gate_uniformity_p']} "
                  f"claims {s['claims_per_game']} 1st {s['first_claimant_win_rate']} "
                  f"noContest {s['claims_no_rival_can_contest']} ableMean {s['mean_rivals_able']} broke {s['phase2_turns_broke']} "
                  f"farmer {s['winning_profiles'].get('prestige_farmer')}", flush=True)
    os.makedirs(os.path.join(ROOT, "results", "v10-prestige"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "results", "v10-prestige", f"screen-{base}-{len(ARMS)}.json"), "w"), indent=1)
