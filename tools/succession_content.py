"""Shared player-facing rules for the browser and printable succession pack.

`rulebook_html` targets the current twin-board rules (V0.10.2); the
legacy single-board V0.8 prose survives in `rulebook_html_v08` for the
legacy printable pack only.
"""

from html import escape

FACTIONS = {"army": "Army", "officials": "Imperial officials", "elites": "City elites"}


def rulebook_html(rules):
    cfg = rules["succession"]
    cap = rules["glory"]["cap"]
    cost = cfg["support_cost"]
    required = cfg["required_support"]
    fee = int(cfg.get("contest_cost") or 0)
    window = cfg.get("claim_window_rounds", 2)
    grace = rules["level1"]["grace_full_rounds"]
    l1_max = rules["level1"]["max_rounds"]
    l2_max = rules["level2"]["max_rounds"]
    min_roll = rules["glory"]["guard_post_success_min_roll"]
    limit = ("There is no storage cap." if cap is None
             else f"You can hold at most <b>{cap} Prestige</b>. Extra rewards are lost.")
    l2 = rules.get("board_level2") or {}
    posts = len(l2.get("glory_posts", []))
    return f'''<h2>The game in one minute</h2>
<p>305 AD. Four rivals prepare a claim to the throne. Collect equipment on the palace map,
earn Prestige, then turn the board over: on the succession map, buy the backing of two
factions and proclaim at the Peristyle. A claim that survives <b>{window} full rounds</b> wins.</p>
<h2>Set the table</h2>
<p>Choose four humans or bots. Random gates use the game seed. You can also choose four distinct gates manually,
or rotate gates across four games. Names and colors belong to players, not gates. The displayed assignment is final when you start.</p>
<p>Both maps share one street plan. The palace map comes first; the succession map is the
same city with its Peristyle three steps east, {posts} guard posts of its own, and six
face-down faction cards. Every gate on the succession map is nine steps from its Peristyle.</p>
<h2>Your turn</h2>
<ol><li>Roll two six-sided dice for movement.</li><li>Move along the circles, up to the total. You may stop early and pass other pawns.</li>
<li>Do <b>one action</b> at your destination: take equipment, stand guard, duel, search a
faction card, gain support, claim the checkpoint, proclaim, maintain your claim, or reveal
a district with the galea.</li></ol>
<p>Tap a highlighted circle. Collection is automatic when no competing action exists. Otherwise a modal shows the choices.
A guard action or duel requires movement of at least one space. The other actions can be stationary.</p>
<h2>Equipment stays yours</h2>
<p>Six treasure entries hold six shuffled equipment types. Cards start face down; two begin face up.
Each player can collect each type once, and only while the palace phase lasts. Equipment is never lost.</p>
<table><tr><th>Item</th><th>Ability</th></tr>
<tr><td><b>Gladius</b> · sword</td><td>+1 to your attack in any duel you start</td></tr>
<tr><td><b>Scutum</b> · shield</td><td>+1 to your defense in any duel</td></tr>
<tr><td><b>Pilum</b> · javelin</td><td>+1 to your attack against the standing claimant</td></tr>
<tr><td><b>Pugio</b> · dagger</td><td>You win tied duels if only you hold it. Both or neither: the attacker wins. Always active.</td></tr>
<tr><td><b>Galea</b> · helmet</td><td>Once per game, as your action: reveal any one face-down treasure card</td></tr>
<tr><td><b>Lorica segmentata</b> · armor</td><td>Once per game: when your claim is beaten, keep your square</td></tr></table>
<p>In a duel each side adds at most <b>one</b> number bonus - the best one that applies, never a sum.
The pugio is not a number bonus: it is a passive tie-break that works next to your chosen bonus whenever
the final totals are equal. Gladius and pugio together are legal; gladius and pilum together still add only +1.</p>
<h2>Earn and spend Prestige</h2>
<p>{limit} Move to a guard post (either map) and roll one die: <b>{min_roll} or higher earns one Prestige</b>.
The winner of a duel earns one Prestige. The loser pays one back to the bank.</p>
<p>Resolve a duel in this order: both roll one die; each side adds its one best number bonus;
compare totals; only if the totals are equal, apply the pugio - the lone holder wins, otherwise
the attacker wins. Nobody loses equipment or support.</p>
<h2>Search the faction cards</h2>
<p>At the change to the succession map, six faction cards go face down on the ? spaces:
the Army, the Imperial officials, the City elites, and three empty streets. End your move on a
? and turn its card face up: that is a search. Everyone sees it; it stays face up.</p>
<p>Stand on a face-up faction card and <b>spend {cost} Prestige</b> as your action for its support.
An empty street gives nothing. Every faction can support every player once. You need
<b>{required} different supporters</b> to proclaim. Faction cards exist only in the succession phase.</p>
<h2>From the palace to the succession</h2>
<p>The first player who owns all six items may stand at the Peristyle and claim the checkpoint
as their action. Finish that round, then <b>{grace} additional full round</b>, and the succession begins.
If nobody claims by round {l1_max}, the succession begins anyway.</p>
<p>At the change the palace map leaves the table. Every pawn returns to its gate on the succession
map and keeps everything it owns: items, Prestige, and support already gained. Nothing is granted
for free.</p>
<h2>Proclaim and contest a claim</h2>
<ol><li>During the succession phase, stand at the Peristyle with {required} supporters and proclaim. Only one claim can stand at a time.</li>
<li>Your claim now stands inside a {window}-round window. Rivals cancel it only by winning a challenge duel.</li>
<li>On your turn you may maintain the claim and stay put. Leaving the Peristyle by your own move cancels it.</li>
<li>If no rival cancels the claim before {window} full rounds pass, <b>you are emperor</b>.</li></ol>
<p>To challenge, end your move within two street circles of the claimant and duel them.
Challenging a standing claim costs a mandatory <b>{fee} Prestige fee</b>, paid before you roll - even if you lose.
Without at least {fee} Prestige you cannot contest at all. A winning challenge cancels the claim;
the claimant returns to their gate unless the lorica segmentata is unused, which once per game
lets a beaten claimant keep the square (the claim still dies). If no claim survives by round
{l2_max} of the succession, the game ends in a draw.</p>
<h2>What you can see</h2>
<p>Positions, equipment, Prestige, supporters, revealed cards, and claims are public. Face-down
treasure and faction cards and future rolls are hidden. The same seed and setup reproduce the game.</p>
<h2>History behind the game</h2>
<p>Diocletian's Tetrarchy shared rule between two senior emperors and two junior emperors.
This game imagines rival claims after his retirement. Its three support groups and palace contest are game abstractions.</p>
<p>The gates have real names: Golden north, Silver east, Bronze south, and Iron west.
The cardo runs north–south and the decumanus east–west. The six-block game map is not an exact reconstruction.</p>
<p class="provenance">Imperial Rivals: 305 AD, rules V0.10.2. Simulations can test incentives and strategies;
only human playtests can establish whether these choices are clear and enjoyable.</p>'''


def rulebook_html_v08(rules):
    cfg = rules["succession"]
    cap = rules["glory"]["cap"]
    cost = cfg["support_cost"]
    required = cfg["required_support"]
    challenge_cost = cfg["challenge_cost"]
    bonus = cfg["challenge_bonus"]
    early = "both phases" if cfg["support_in_city"] else "the succession phase"
    limit = "There is no storage cap." if cap is None else f"You can hold at most <b>{cap} Prestige</b>. Extra rewards are lost."
    transition = "Return pawns to their assigned gates." if cfg["reset_positions"] else "Keep every pawn at its current position."
    fee = int(cfg.get("contest_cost") or 0)
    fee_note = "" if not fee else (
        f"<p>Challenging an active claimant costs <b>{fee} Prestige</b>, paid before you roll. "
        f"This fee is mandatory and separate from the optional +{bonus} boost. You pay it even if the challenge fails. "
        "An ordinary duel against a player without an active claim stays free. A winning challenge still earns the normal duel reward.</p>")
    rows = "".join(f"<tr><td><b>{label}</b></td><td>{place}</td></tr>" for label, place in [
        ("Army", "District F · barracks"), ("Imperial officials", "Peristyle · main crossing"),
        ("City elites", "District A · civic meeting place")])
    return f'''<h2>The game in one minute</h2>
<p>Four rivals prepare a claim to imperial power. Collect equipment, earn Prestige, and secure faction support.
During succession, reach the Peristyle with <b>{required} different supporters</b> and proclaim your claim.
If it survives a response turn from every rival, you win.</p>
<h2>Set the table</h2>
<p>Choose four humans or bots. Random gates use the game seed. You can also choose four distinct gates manually,
or rotate gates across four games. Names and colors belong to players, not gates. The displayed assignment is final when you start.</p>
<p>The six intact blocks hold six shuffled equipment types. Cards start face down. Each player can collect each type once.
The north and south gates end the cardo; the east and west gates end the decumanus. The cardo is off-center in this game map.</p>
<h2>Your turn</h2>
<ol><li>Roll two six-sided dice for movement.</li><li>Move along the circles, up to the total. You may stop early and pass other pawns.</li>
<li>Do <b>one action</b> at your destination. Taking equipment, gaining support, and fighting are separate actions.</li></ol>
<p>Tap a highlighted circle. Collection is automatic when no competing action exists. Otherwise a modal shows the choices.
A guard action or duel requires movement of at least one space. Equipment, support, a proclamation, and maintaining a claim can be stationary.</p>
<h2>Equipment stays yours</h2>
<p>Visit a treasure entry to collect its equipment. The first collection reveals the card to everyone.
You can still collect equipment during succession. Equipment is never lost or given to you for free at transition.</p>
<table><tr><th>Equipment</th><th>Added to your duel roll</th></tr><tr><td>0–2 items</td><td>+0</td></tr>
<tr><td>3–5 items</td><td>+1</td></tr><tr><td>All six</td><td>+2</td></tr></table>
<h2>Earn and spend Prestige</h2>
<p>{limit} Move to a guard post and roll one die: <b>4, 5, or 6 earns one Prestige</b>.
The winner of a duel earns one Prestige. The first complete collector who opens the checkpoint also earns one.</p>
<p>To duel, end your move within two street spaces of a rival. Each player rolls one die and adds the equipment bonus.
<b>The attacker wins ties.</b> Before rolling, the attacker may spend <b>{challenge_cost} Prestige for +{bonus}</b>.
The cost is paid even if the challenge fails. No one loses equipment or support.</p>
<h2>Secure faction support</h2>
<table><tr><th>Group</th><th>Meeting place</th></tr>{rows}</table>
<p>In {early}, visit a meeting place and <b>spend {cost} Prestige for its support</b>. There is no additional roll.
Every group can support every player, once per player. Support remains yours for the whole game.
You need {required} different supporters to proclaim a claim. Rivals do not need to endorse you.</p>
<h2>From preparation to succession</h2>
<p>The first player with all six equipment types can open the checkpoint. Finish that round and
<b>{rules['level1']['grace_full_rounds']} additional full round</b>. Then succession begins.
If no one opens it, succession starts after {rules['level1']['max_rounds']} city rounds.</p>
<p>{transition} Keep your equipment, Prestige, and support. <b>Missing equipment is not granted.</b>
You can finish collecting it through play.</p>
<h2>Proclaim and contest a claim</h2>
<ol><li>During succession, reach the Peristyle with {required} supporters. Use your action to proclaim your claim.</li>
<li>Every rival gets a response turn. They can challenge you, prepare their own position, or take another action.</li>
<li>A winning challenge cancels your claim and returns your pawn to your assigned gate. Your equipment and support remain.</li>
<li>If all three rivals finish a response with your claim intact, <b>you are acclaimed emperor</b>.</li></ol>
<p>Only one claim can be pending. A failed challenge leaves it active. Leaving the Peristyle cancels your own claim.
If your turn comes during the response window, you can maintain your claim and stay put.
If nobody wins within {rules['level2']['max_rounds']} succession rounds, the game is a draw.</p>{fee_note}
<h2>What you can see</h2>
<p>Positions, equipment, Prestige, supporters, and claim responses are public. Unrevealed equipment and future rolls remain hidden.
The same seed and setup reproduce the game. The game does not use real money.</p>
<h2>History behind the game</h2>
<p>Diocletian's Tetrarchy shared rule between two senior emperors and two junior emperors.
This game imagines rival claims after his retirement. Its three support groups and palace contest are game abstractions.</p>
<p>The gates have real names: Golden north, Silver east, Bronze south, and Iron west.
The cardo runs north–south and the decumanus east–west. The six-block game map is not an exact reconstruction.</p>
<p class="provenance">Succession prototype V0.8. The starting economy is experimental. Simulations can test incentives and strategies;
only human playtests can establish whether these choices are clear and enjoyable.</p>'''


def printable_pack(rules, board, cards):
    cap = rules["glory"]["cap"]
    trackers = "".join(f'''<article class="tracker"><h3>Player {i}</h3><p>Name: __________________ Gate: __________</p>
<p>Equipment: □ pugio · □ pilum · □ galea · □ scutum · □ gladius · □ armor</p>
<p>Prestige: ______ {'(maximum ' + str(cap) + ')' if cap is not None else '(no cap)'}</p>
<p>Support: □ Army · □ Imperial officials · □ City elites</p><p>Claim responses: □ rival 1 · □ rival 2 · □ rival 3</p></article>''' for i in range(1, 5))
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Diocletian’s Palace · Succession playtest</title>
<style>body{{font:14px/1.6 Georgia,serif;color:#263b34;background:#eee;margin:0}}.page{{max-width:950px;margin:20px auto;padding:28px;background:#fffdf6;break-after:page}}
h1,h2,h3{{font-weight:normal}}h2{{margin-top:24px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:8px;text-align:left}}
.board svg{{width:100%;height:auto}}.tracker{{border:1px solid #ccc;padding:15px;margin-bottom:15px;break-inside:avoid}}.eqgrid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.eqcard{{border:1px solid #ccc;padding:20px}}
@media print{{body{{background:white}}.page{{margin:0;max-width:none;padding:12mm}}@page{{size:A4;margin:10mm}}.board{{page:board}}@page board{{size:A4 landscape}}}}</style></head><body>
<section class="page"><h1>Diocletian’s Palace: the succession</h1><p>Prototype V0.8 · Four players · Two movement dice and one combat die per player.</p>
<p>Print the board in landscape. Use four distinct pawns, counters for Prestige, and the player trackers.
Give the six equipment cards public locations; each player marks their own collected copy on a tracker.</p>
<p>Start with random gate assignments. For four repeated games, rotate players through all four gates.</p></section>
<section class="page board"><h2>Six blocks · Six treasures</h2>{board}<p>N: Golden · E: Silver · S: Bronze · W: Iron.
Blue letters mark treasures. Stars mark guard posts. A/O/C badges mark the Army, officials, and city elites.</p></section>
<section class="page"><h2>Equipment cards</h2>{cards}</section><section class="page"><h2>Player trackers</h2>{trackers}</section>
<section class="page">{rulebook_html_v08(rules)}</section>
<section class="page"><h2>Teach in five minutes</h2><ol><li>Show the six equipment locations and the lasting equipment bonus.</li>
<li>Show where Prestige comes from and how one support action works.</li><li>Walk through a turn with two movement dice and one action.</li>
<li>Show the Peristyle and demonstrate a claim, a challenge, and the three responses.</li>
<li>Explain that rivals keep their equipment and support after a canceled claim.</li></ol>
<h2>Playtest feedback</h2><p>What did you think your best strategy was? ______________________________</p>
<p>Describe a turn with two appealing choices. __________________________________</p><p>Did preparation help later? __________________________________</p>
<p>Could you meaningfully stop a rival? __________________________________</p><p>Where did you wait or repeat an action? __________________________________</p>
<p>What rule needed an explanation? __________________________________</p><p>Would you play again, and what would you try differently? __________________________________</p>
<p>Record seed, player-to-gate assignments, policies, turns, and rules version with the feedback.</p></section></body></html>'''
