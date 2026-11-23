#!/usr/bin/env python3
# ABOUTME: Shared player-facing rules text for the web board and the
# ABOUTME: printable playtest pack, with every rule number from the rules JSON.
"""Shared player-facing rules for the browser and printable packs.

Both texts read every rule number from the rules JSON
(rules/imperial-rivals-v0.10.2.json); none are fixed copies.
"""

from html import escape

FACTIONS = {"army": "Army", "officials": "Imperial officials", "elites": "City elites"}

# Tracker lines use English primary names.
_TRACKER_ALIASES = {"pugio": "dagger", "pilum": "javelin", "galea": "helmet",
                    "scutum": "shield", "gladius": "sword",
                    "lorica_segmentata": "armor"}

_NUMBER_WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
                 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
                 10: "ten", 11: "eleven", 12: "twelve"}


def count_word(n):
    # Numbers up to twelve read as words in prose; larger ones stay digits.
    return _NUMBER_WORDS.get(n, str(n))


def rulebook_html(rules):
    cfg = rules["succession"]
    palace = rules["palace"]
    prestige = rules["prestige"]
    movement = rules["movement"]
    duels = rules["duels"]
    treasures = rules["treasures"]
    players = rules["game"]["players"]
    version = rules["game"]["rules_version"]
    cap = prestige["cap"]
    cost = cfg["support_cost"]
    required = cfg["factions_to_proclaim"]
    fee = cfg["contest_fee"]
    window = cfg["claim_window_rounds"]
    trans_min = cfg["transition_min_prestige"]
    grace = palace["rounds_after_checkpoint"]
    l1_max = palace["max_rounds"]
    l2_max = cfg["max_rounds"]
    min_roll = prestige["guard_post_min_roll"]
    gw = count_word(prestige["guard_post_reward"])
    dw = count_word(prestige["duel_win_reward"])
    dl = count_word(prestige["duel_loss_penalty"])
    dice, sides = movement["dice"], movement["die_sides"]
    tie, rng = duels["tie_winner"], duels["range"]
    items = treasures["items"]
    abilities = treasures["abilities"]
    face_up = treasures["start_face_up"]
    items_req = palace["checkpoint_items_required"]
    gv, sv, pv = (abilities["gladius"]["value"], abilities["scutum"]["value"],
                  abilities["pilum"]["value"])
    for name, kind in (("gladius", "attack_bonus"), ("scutum", "defense_bonus"),
                       ("pilum", "attack_vs_claimant"), ("pugio", "win_ties"),
                       ("galea", "reveal_district"),
                       ("lorica_segmentata", "prevent_displacement")):
        if abilities[name]["type"] != kind:
            raise SystemExit(f"the web rulebook files the {name} under its "
                             f"{abilities[name]['type']} ability; update the prose")
    smap, pmap = cfg["map"], palace["map"]
    east = smap["checkpoint"][0] - pmap["checkpoint"][0]
    steps = {abs(g[0] - smap["checkpoint"][0]) + abs(g[1] - smap["checkpoint"][1])
             for g in smap["gates"].values()}
    if east <= 0 or len(steps) != 1:
        raise SystemExit("the web rulebook places the succession Peristyle east "
                         "of the palace crossing, every gate the same number of "
                         "steps away; update the prose")
    gate_steps = steps.pop()
    posts = len(smap["guard_posts"])
    n_gates = len(pmap["gates"])
    n_entries = len(pmap["treasure_entries"])
    n_items = len(items)
    n_factions = len(cfg["faction_cards"]["factions"])
    empty = cfg["faction_cards"]["empty"]
    n_cards = n_factions + empty
    n_blocks = len(pmap["buildings"])
    limit = ("There is no storage cap." if cap is None
             else f"You can hold at most <b>{cap} Prestige</b>. Extra rewards are lost.")
    trans_note = (f" Any player entering with less than {trans_min} Prestige rises to {trans_min}."
                  if trans_min else "")
    round_word = "full round" if window == 1 else "full rounds"
    return f'''<h2>The game in one minute</h2>
<p>305 AD. {count_word(players).capitalize()} rivals prepare a claim to the throne. Collect equipment on the palace map,
earn Prestige, then turn the board over: on the succession map, buy the backing of {count_word(required)}
factions and proclaim at the Peristyle. A claim that survives <b>{window} {round_word}</b> wins.</p>
<h2>Set the table</h2>
<p>Choose {count_word(players)} humans or bots. Random gates use the game seed. You can also choose {count_word(n_gates)} distinct gates manually,
or rotate gates across {count_word(n_gates)} games. Names and colors belong to players, not gates. The displayed assignment is final when you start.</p>
<p>Both maps share one street plan. The palace map comes first; the succession map is the
same city with its Peristyle {count_word(east)} steps east, {posts} guard posts of its own, and {count_word(n_cards)}
face-down faction cards. Every gate on the succession map is {count_word(gate_steps)} steps from its Peristyle.</p>
<h2>Your turn</h2>
<ol><li>Roll {count_word(dice)} {count_word(sides)}-sided dice for movement.</li><li>Move along the circles, up to the total. You may stop early and pass other pawns.</li>
<li>Do <b>one action</b> at your destination: take equipment, stand guard, duel, search a
faction card, gain support, claim the checkpoint, proclaim, maintain your claim, or reveal
a hidden card with the helmet.</li></ol>
<p>Tap a highlighted circle. Collection is automatic when no competing action exists. Otherwise a modal shows the choices.
A guard action or duel requires movement of at least one space. The other actions can be stationary.</p>
<h2>Equipment stays yours</h2>
<p>{count_word(n_entries).capitalize()} treasure entries hold {count_word(n_items)} shuffled equipment types. Cards start face down; {count_word(face_up)} begin face up.
Each player can collect each type once, and only while the palace phase lasts. Equipment is never lost.</p>
<table><tr><th>Item</th><th>Ability</th></tr>
<tr><td><b>Sword</b> · gladius</td><td>+{gv} to your attack in any duel you start</td></tr>
<tr><td><b>Shield</b> · scutum</td><td>+{sv} to your defense in any duel</td></tr>
<tr><td><b>Javelin</b> · pilum</td><td>+{pv} to your attack against the standing claimant</td></tr>
<tr><td><b>Dagger</b> · pugio</td><td>You win tied duels if only you hold it. Both or neither: the {tie} wins. Always active.</td></tr>
<tr><td><b>Helmet</b> · galea</td><td>Once per game (either map), as your action: publicly reveal any one face-down treasure or faction card</td></tr>
<tr><td><b>Armor</b> · lorica segmentata</td><td>Once per game: when your claim is beaten, keep your square</td></tr></table>
<p>In a duel each side adds at most <b>one</b> number bonus - the best one that applies, never a sum.
The dagger is not a number bonus: it is a passive tie-break that works next to your chosen bonus whenever
the final totals are equal. Sword and dagger together are legal; sword and javelin together against the claimant use the best one (+{max(gv, pv)}).</p>
<h2>Earn and spend Prestige</h2>
<p>{limit} Move to a guard post (either map) and roll one die: <b>{min_roll} or higher earns {gw} Prestige</b>.
The winner of a duel earns {dw} Prestige from the bank. The loser pays {dl} back to the bank (ordinary duel losers stay put).</p>
<p>Resolve a duel in this order: both roll one die; each side adds its one best number bonus;
compare totals; only if the totals are equal, apply the dagger - the lone holder wins, otherwise
the {tie} wins. Nobody loses equipment or support.</p>
<h2>Search the faction cards</h2>
<p>At the change to the succession map, {count_word(n_cards)} faction cards go face down on the ? spaces:
the Army, the Imperial officials, the City elites, and {count_word(empty)} empty streets. End your move on a
? and turn its card face up: that is a search. Everyone sees it; it stays face up.</p>
<p>Stand on a face-up faction card and <b>spend {cost} Prestige</b> as your action for its support.
An empty street gives nothing. Every faction can support every player once. You need
<b>{required} different supporters</b> to proclaim. Faction cards exist only in the succession phase.</p>
<h2>From the palace to the succession</h2>
<p>The first player who owns all {count_word(items_req)} items may stand at the Peristyle and claim the checkpoint
as their action. Finish that round, then <b>{grace} additional full round</b>, and the succession begins.
If nobody claims by round {l1_max}, the succession begins anyway.</p>
<p>At the change the palace map leaves the table. Every pawn returns to its gate on the succession
map and keeps everything it owns: items, Prestige, and support already gained.{trans_note}</p>
<h2>Proclaim and contest a claim</h2>
<ol><li>During the succession phase, stand at the Peristyle with {required} supporters and proclaim. Only one claim can stand at a time.</li>
<li>Your claim now stands inside a {window}-round window. Rivals cancel it only by winning a challenge duel.</li>
<li>On your turn you may maintain the claim and stay put. Leaving the Peristyle by your own move cancels it.</li>
<li>If no rival cancels the claim before {window} {round_word} pass, <b>you are emperor</b>.</li></ol>
<p>To challenge, end your move within {count_word(rng)} street circles of the claimant and duel them.
Challenging a standing claim costs a mandatory <b>{fee} Prestige fee</b>, paid before you roll - even if you lose.
Without at least {fee} Prestige you cannot contest at all. A winning challenge cancels the claim;
the claimant returns to their gate unless the armor (lorica segmentata) is unused, which once per game
lets a beaten claimant keep the square (the claim still dies). If no claim survives by round
{l2_max} of the succession, the game ends in a draw.</p>
<h2>What you can see</h2>
<p>Positions, equipment, Prestige, supporters, revealed cards, and claims are public. Face-down
treasure and faction cards and future rolls are hidden. The same seed and setup reproduce the game.</p>
<h2>History behind the game</h2>
<p>Diocletian's Tetrarchy shared rule between two senior emperors and two junior emperors.
This game imagines rival claims after his retirement. Its {count_word(n_factions)} support groups and palace contest are game abstractions.</p>
<p>The gates have real names: Golden north, Silver east, Bronze south, and Iron west.
The cardo runs north–south and the decumanus east–west. The {count_word(n_blocks)}-block game map is not an exact reconstruction.</p>
<p class="provenance">Imperial Rivals: 305 AD, rules V{version}. Simulations can test incentives and strategies;
only human playtests can establish whether these choices are clear and enjoyable.</p>'''


def printable_pack(rules, board, cards):
    game = rules["game"]
    palace = rules["palace"]
    prestige = rules["prestige"]
    cfg = rules["succession"]
    movement = rules["movement"]
    cap = prestige["cap"]
    players = game["players"]
    version = game["rules_version"]
    dice = movement["dice"]
    items = rules["treasures"]["items"]
    n_items = len(items)
    n_gates = len(palace["map"]["gates"])
    n_blocks = len(palace["map"]["buildings"])
    eq_ticks = " · ".join("□ " + _TRACKER_ALIASES.get(n, n) for n in items)
    support_ticks = " · ".join("□ " + name for name in FACTIONS.values())
    rival_ticks = " · ".join(f"□ rival {j}" for j in range(1, players))
    trackers = "".join(f'''<article class="tracker"><h3>Player {i}</h3><p>Name: __________________ Gate: __________</p>
<p>Equipment: {eq_ticks}</p>
<p>Prestige: ______ {'(maximum ' + str(cap) + ')' if cap is not None else '(no cap)'}</p>
<p>Support: {support_ticks}</p><p>Claim responses: {rival_ticks}</p></article>''' for i in range(1, players + 1))
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Diocletian’s Palace · Succession playtest</title>
<style>body{{font:14px/1.6 Georgia,serif;color:#263b34;background:#eee;margin:0}}.page{{max-width:950px;margin:20px auto;padding:28px;background:#fffdf6;break-after:page}}
h1,h2,h3{{font-weight:normal}}h2{{margin-top:24px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:8px;text-align:left}}
.board svg{{width:100%;height:auto}}.tracker{{border:1px solid #ccc;padding:15px;margin-bottom:15px;break-inside:avoid}}.eqgrid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.eqcard{{border:1px solid #ccc;padding:20px}}
@media print{{body{{background:white}}.page{{margin:0;max-width:none;padding:12mm}}@page{{size:A4;margin:10mm}}.board{{page:board}}@page board{{size:A4 landscape}}}}</style></head><body>
<section class="page"><h1>Diocletian’s Palace: the succession</h1><p>Prototype V{version} · {count_word(players).capitalize()} players · {count_word(dice).capitalize()} movement dice and one combat die per player.</p>
<p>Print the board in landscape. Use four distinct pawns, counters for Prestige, and the player trackers.
Give the {count_word(n_items)} equipment cards public locations; each player marks their own collected copy on a tracker.</p>
<p>Start with random gate assignments. For {count_word(players)} repeated games, rotate players through all {count_word(n_gates)} gates.</p></section>
<section class="page board"><h2>{count_word(n_blocks).capitalize()} blocks · {count_word(n_items).capitalize()} treasures</h2>{board}<p>N: Golden · E: Silver · S: Bronze · W: Iron.
Blue letters mark treasures. Stars mark guard posts. A/O/C badges mark the Army, officials, and city elites.</p></section>
<section class="page"><h2>Equipment cards</h2>{cards}</section><section class="page"><h2>Player trackers</h2>{trackers}</section>
<section class="page">{rulebook_html(rules)}</section>
<section class="page"><h2>Teach in five minutes</h2><ol><li>Show the {count_word(n_items)} equipment locations and the lasting equipment bonus.</li>
<li>Show where Prestige comes from and how one support action works.</li><li>Walk through a turn with {count_word(dice)} movement dice and one action.</li>
<li>Show the Peristyle and demonstrate a claim, a challenge, and the three responses.</li>
<li>Explain that rivals keep their equipment and support after a canceled claim.</li></ol>
<h2>Playtest feedback</h2><p>What did you think your best strategy was? ______________________________</p>
<p>Describe a turn with two appealing choices. __________________________________</p><p>Did preparation help later? __________________________________</p>
<p>Could you meaningfully stop a rival? __________________________________</p><p>Where did you wait or repeat an action? __________________________________</p>
<p>What rule needed an explanation? __________________________________</p><p>Would you play again, and what would you try differently? __________________________________</p>
<p>Record seed, player-to-gate assignments, policies, turns, and rules version with the feedback.</p></section></body></html>'''
