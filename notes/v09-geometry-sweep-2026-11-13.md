# V0.9 geometry sweep

Research date: 2026-11-13.

Sources: the 2026-11-12 human session (`playtest/human-session-001.md`,
sections "Level 2 was redesigned at the table" and "Observed problems"),
the V0.6 placement finding and the V0.8 east-gate skew in
`FINDINGS_V0*.md`, and the sweep outputs in `results/v09-geometry/`.

## The playtest's questions

- "Nobody goes through the middle; everyone orbits in a circle."
- Meeting-place distances were unequal (one seat 3 steps, others 4 to 6).
- A claimant near their own gate was practically unreachable.

The engine's layout contract (`board.py`,
`validate_six_block_layout`) pins the gates to the ends of the cardo
and decumanus and the checkpoint to their crossing. On the standard
street grid the crossing can sit at x=6 (current) or x=12 only. An
equidistant crossing is impossible (the cardo gates always sit 6
steps from it while the side gates need 9); the closest map needs a
centered cardo, which needs re-blocking
the whole map.

## Arms

| Arm | Change |
|---|---|
| inc | 0.9.1-trim as promoted |
| cardo12 | cardo at x=12: gates and crossing shift east |
| centered | new six-block map, cardo x=9: crossing distances 6/9/6/9, the smallest spread the street contract allows; two gap streets (x=4 north, x=14 south) cut the wide blocks |
| posts | four guard posts onto the two interior columns |
| midpair | district B to (12,3), district E to (6,9): two treasures on interior streets |
| midpair_posts | both changes together (`rules_v092_succession.json`, "0.9.2-crossflow") |

Metrics: the frozen climb gates plus three new ones - per-gate win
rates with Wilson intervals, a street-class traffic share (rim versus
the two interior columns and the interior row), and per-district
exploration balance. Screens: 96 matched seeds (940000+).
Confirmation and the centered diagnostic: 384 fresh seeds (950000+).

## Verified findings

Every number below survived an adversarial review pass: three
independent verifiers re-derived the statistics, reproduced the
confirmation run bit-exact, and replayed 576 fresh games per arm on
unburned seeds (960000+, 970000+).

1. **The east-gate skew survived the window court.** At 384 games the
   incumbent's east gate wins 15.6% (Wilson 12.3-19.6%) against
   26.6-28.9% for the other three; the deficit is significant
   (chi-square 18.6, p about 3e-4) and appears under all four policy
   profiles, so it is not a schedule artifact. The 96-game screen had
   hidden it. The far gate is the deficit gate in every arm measured:
   the cardo12 mirror puts its far gate lowest, and the centered map's
   6-step gate pair outwins its 9-step pair.
2. **Interior placement doubles middle traffic with no health cost.**
   midpair_posts: interior share 0.29 to 0.62, draws 2 of 384, median
   23 rounds, claims 5.41 per game, every predeclared gate green. The
   gain is not a farmer artifact: every profile's own interior fraction
   rises (for example collector 29.7% to 54.3%), and deleting all
   farmer steps still leaves interior share 0.578. The farmer
   post-to-post shuttle exists but mirrors the incumbent's rim
   post ping-pong - the same behavior relocated, not a new loop.
   East recovers to 19.8%: a point estimate of about half the gap
   closed, but the paired difference is not significant at n=384
   (McNemar p about 0.11-0.14; the interval spans zero to full
   closure).
3. **Guard posts alone are not fair.** Moving all four posts onto the
   interior columns collapsed the east gate to 11.5% at screen: the
   post set is symmetric but the faction sites are not (officials sit
   west of the crossing). Posts move only together with treasures.
4. **The centered-cardo map buys seat fairness at the first claimer's
   expense.** Its gates are the tightest measured (23.4-28.4%, a
   five-point spread; true equidistance is impossible because gates
   must end the cardo and decumanus) but the first claimant wins only
   19.5% (384 games), below the predeclared 0.20 floor - the screen
   fail was real, not noise. Parking it follows the blind-support
   precedent: full data, no promotion. Any future promotion of a
   centered map requires a fresh screen cycle on fresh seeds, plus a
   deliberate decision on whether a weaker first claim is acceptable.
5. **Swapping the cardo mirrors the tilt, nothing more.** cardo12
   passes every gate but moves middle traffic by one point and swaps
   which seats win. Not useful; not promoted.

Statistical caveats carried from the review: the farmer profile's
floor is thin (17.2% pooled over 1056 games, 95% interval 15.0-19.5%),
and claims per game sits near 5.4 in this arm against 4.7-4.9 for the
incumbent - watch both in the human session.

## Static distance audit

No games: BFS from each gate to every site (checkpoint, faction
cells, posts, district entries); spread is max minus min distance.

| Map | Checkpoint spread | Mean site spread | Post spreads |
|---|---|---|---|
| 0.9.1 incumbent | 6 | 14.0 | 18, 18, 18, 18 |
| 0.9.2 crossflow | 6 | 11.6 | 14, 8, 14, 8 |
| centered cardo | 3 | 13.0 | 18, 10, 10, 18 |

Crossflow carries the best mean site spread; district B's spread
drops from 12 to 6 and the east gate's trip to B falls from 15 to 9.
The centered map wins only at the crossing and the officials cell -
which is exactly where its first-claimant cost lives. Its wide blocks
keep rim content lopsided (districts all spread 15).

## Open questions

- Does the interior traffic survive human play, or do humans read the
  (12,3) and (6,9) treasures as rim content anyway? The second human
  session should watch this directly.
- Is a first-claimant win rate near 0.20 a feature (comebacks) or a
  trap (the claim is a sacrifice)? The gate band 0.20-0.60 comes from
  V0.8-era reasoning and has never been tested with humans.
- The playtest's three-step challenge radius was never simulated;
  crossflow keeps the off-center crossing, so "claim near your gate"
  stays partly unsolved. A radius arm on the crossflow map is the
  natural follow-up screen.
- No per-seat distance metric exists for support sites during play;
  the static audit covers setup positions only.
- Kingmaking and the broke-player lockout remain bot-invisible.
- Gate fairness under print: the kit regenerates from the rules file,
  but the human session should check the new map reads well on paper.
