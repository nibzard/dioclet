#!/usr/bin/env python3
"""One seat at a shared table: lets an outside player (a person or an
agent) play one colour in a persistent game created by `sim.py new`.

    python3 tools/table_seat.py wait --run DIR --player P0
    python3 tools/table_seat.py view --run DIR --player P0
    python3 tools/table_seat.py act  --run DIR --player P0 --action a0003 --note "why"

`wait` blocks until it is the player's turn (then prints the view) or
the game ends. `view` prints a compact, public-only picture of the
game: an ASCII map, every player's state, the recent public events,
and a shortlist of candidate actions with plain descriptions. `act`
submits one action for the current turn; the turn id is filled in.

Everything shown comes from engine.observe() for that player, plus the
public event feed, so a seat never sees hidden district contents.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import candidate_actions  # noqa: E402
import engine  # noqa: E402

FACTION_MARK = {"army": "a", "officials": "o", "elites": "e"}


def ascii_map(obs):
    """North at the top. Players are digits 0-3, drawn over the map."""
    b = obs["board"]
    w, h = b["width"], b["height"]
    grid = [["." for _ in range(w)] for _ in range(h)]
    for x, y in b["blocked"]:
        grid[y][x] = "#"
    for x, y in b.get("glory_posts", []):
        grid[y][x] = "*"
    for name, (x, y) in b.get("districts", {}).items():
        grid[y][x] = name
    for name, (x, y) in b.get("factions", {}).items():
        grid[y][x] = FACTION_MARK.get(name, "f")
    for x, y in b["gates"].values():
        grid[y][x] = "G"
    cx, cy = b["checkpoint"]
    grid[cy][cx] = "X"
    for pid, p in obs["players"].items():
        x, y = p["position"]
        grid[y][x] = pid[1]
    rows = []
    for y in range(h - 1, -1, -1):
        rows.append(f"{y:2d} " + "".join(grid[y]))
    rows.append("   " + "".join(str(x % 10) for x in range(w)))
    return "\n".join(rows)


def public_events(state, obs, since_turn):
    revealed = set((obs.get("revealed_districts") or {}).keys())
    lines = []
    for rec in state["events"]:
        if rec["turn_id"] <= since_turn:
            continue
        acts = rec["action"]["kind"]
        parts = []
        for e in rec["events"]:
            t = e.get("type")
            if t == "district_revealed" and e.get("district") not in revealed:
                continue
            if t == "duel":
                parts.append(f"duel {e['attacker']} {e['attacker_score']} vs "
                             f"{e['defender']} {e['defender_score']} -> {e['winner']} wins")
            elif t == "equipment_collected":
                parts.append(f"{e['player']} took {e['item']} from {e['district']}")
            elif t in ("prestige_earned", "prestige_spent"):
                why = e.get("cause") or e.get("purpose")
                sign = "+" if t == "prestige_earned" else "-"
                parts.append(f"{e['player']} {sign}{e['amount']} Prestige ({why})")
            elif t == "guard_post":
                parts.append(f"{e['player']} guard post roll {e['roll']} "
                             f"{'success' if e['success'] else 'fail'}")
            elif t == "support_gained":
                parts.append(f"{e['player']} gained {e['faction']} support")
            else:
                parts.append(", ".join(f"{k}={v}" for k, v in e.items()))
        dice = rec.get("movement_dice")
        lines.append(f"t{rec['turn_id']} {rec['player']} rolled {dice} "
                     f"{acts}->{rec.get('position_after')}"
                     + (": " + "; ".join(parts) if parts else ""))
    return lines[-12:]


def view(run, player, out=sys.stdout):
    state = engine.load_run(run)
    if engine.is_finished(state):
        r = engine.result(state)
        print("GAME OVER:", json.dumps({k: r[k] for k in ("outcome", "winner", "end_reason")}),
              file=out)
        print("LAST EVENTS:", file=out)
        everything = {"revealed_districts": {d: None for d in "ABCDEF"}}
        for line in public_events(state, everything, state["turn_id"] - 8):
            print("  " + line, file=out)
        return
    obs = engine.observe(state, player)
    rules = state["rules"]
    me = obs["players"][player]
    print(f"== {player} | turn {obs['turn_id']} | phase {obs['phase']} "
          f"({'palace map' if obs['phase'] == 1 else 'succession map'}) | "
          f"round {obs['round']} | status {obs['status']} | "
          f"active {obs['active_player']} | your roll {obs.get('movement_dice')} "
          f"(total {obs.get('movement_die')})", file=out)
    print("\nMAP (# building, . street, G gate, X Peristyle, * guard post, "
          "A-F treasure entries, a/o/e faction sites, 0-3 players):", file=out)
    print(ascii_map(obs), file=out)
    print("\nPLAYERS:", file=out)
    for pid, p in sorted(obs["players"].items()):
        tag = " (you)" if pid == player else ""
        print(f"  {pid}{tag}: pos {p['position']} gate {p['gate']} prestige {p['prestige']} "
              f"items {p['equipment_count']}/6 {p['equipment']} support {p['support']}",
              file=out)
    print(f"\nrevealed districts: {obs.get('revealed_districts')}", file=out)
    print(f"pending claim: {obs.get('pending_claim')}", file=out)
    prog = obs.get("progress") or {}
    print(f"first challenger: {prog.get('first_challenger')} | full sets: "
          f"{prog.get('players_with_full_equipment')}", file=out)
    since = max(0, obs["turn_id"] - 12)
    print("\nRECENT EVENTS:", file=out)
    for line in public_events(state, obs, since):
        print("  " + line, file=out)
    if obs["active_player"] != player:
        print(f"\nNot your turn ({obs['active_player']} is active).", file=out)
        return
    built = candidate_actions.build_candidates(obs, rules)
    cands = built[0] if isinstance(built, tuple) else built
    print(f"\nYOUR CANDIDATE ACTIONS ({len(cands)} of {len(obs['legal_actions'])} legal):",
          file=out)
    for c in cands:
        print(f"  {c['action_id']}: {c['description']}", file=out)
    print("\nAct with: python3 tools/table_seat.py act --run RUN --player "
          f"{player} --action <id> --note \"<one-line reason>\"", file=out)


def cmd_wait(args):
    deadline = time.time() + args.timeout
    while True:
        state = engine.load_run(args.run)
        if state["status"] != "in_progress" or state["active_player"] == args.player:
            view(args.run, args.player)
            return
        if time.time() > deadline:
            print(f"still waiting: {state['active_player']} is active at turn "
                  f"{state['turn_id']}. Run wait again.")
            return
        time.sleep(1.0)


def cmd_act(args):
    state = engine.load_run(args.run)
    if state["status"] != "in_progress":
        print("game is over")
        return
    if state["active_player"] != args.player:
        print(f"not your turn: {state['active_player']} is active")
        sys.exit(2)
    try:
        record = engine.apply_action(state, args.player, state["turn_id"],
                                     args.action, args.note)
    except engine.EngineError as exc:
        print(f"rejected: {exc.code}: {exc}")
        sys.exit(2)
    engine.write_run(args.run, state)
    print(f"applied {args.action}: now at {record['position_after']}, "
          f"prestige {record.get('prestige_after')}, items {record['equipment_count_after']}")
    for e in record["events"]:
        print("  event:", json.dumps(e))
    if engine.is_finished(state):
        r = engine.result(state)
        print("GAME OVER:", json.dumps({k: r[k] for k in ("outcome", "winner", "end_reason")}))
    else:
        print(f"next: {state['active_player']}. Now run wait.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("wait", "view", "act"):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        p.add_argument("--player", required=True, choices=["P0", "P1", "P2", "P3"])
        if name == "wait":
            p.add_argument("--timeout", type=float, default=540)
        if name == "act":
            p.add_argument("--action", required=True)
            p.add_argument("--note", default="")
    args = ap.parse_args()
    if args.cmd == "wait":
        cmd_wait(args)
    elif args.cmd == "view":
        view(args.run, args.player)
    else:
        cmd_act(args)


if __name__ == "__main__":
    main()
