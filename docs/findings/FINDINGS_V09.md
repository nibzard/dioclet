# V0.9 trial findings: treasure identity

Date: 2026-11-11. All numbers are offline bot play from
`results/v09-design-001` (the first ability set, C1) and
`results/v09-design-002` (the simplified set, C2, recommended).
Each trial is three arms, 480 games, matched seeds 300000-300479,
the V0.8 seat schedule: 24 gate permutations, four probe profiles
rotating. Plan: `notes/v09-experiment-plan.md`. Spend: none
(offline). Tests: 232 pass (210 existing unchanged plus 22 new in
`tests/test_v09_variants.py`). The C1 rules snapshot is preserved
at `results/v09-design-001/c1-abilities-rules.json`; the working
tree carries C2 in `rules_v09_abilities.json`.

The trial answers the design question the user set on 2026-11-11:
do distinct treasure identities plus partial revelation change
routing, combat, and gate fairness? It is a design experiment
outside the programme.md search space (programme.md:56), not a
release candidate.

## Headline

| Measure | A baseline | B reveal 2 | C abilities |
|---|---|---|---|
| Wins / draws of 480 | 468 / 12 | 464 / 16 | 361 / **119** |
| Median rounds | 26 | 25 | 31 |
| Claims per game | 9.5 | 9.3 | **17.2** |
| Cancelled claims per game | 8.5 | 8.3 | **16.3** |
| Duels per game | 22.8 | 22.3 | **31.2** |
| Gate spread (win-conditional) | 18.4 pts | 19.4 pts | **9.1 pts** |
| First-claimant win share | 44% | 41% | 36% |

- **B is safe and inert.** Every outcome measure sits inside noise
  of baseline. Revelation changed routing: 35% of first explores
  target a start-revealed district (0% possible in A by
  construction).
- **C is not shippable as specified.** Draws explode from 2.5% to
  24.8%, all phase-2 timeouts, driven by a claim-recycling loop (see
  below). The user's own warning, "a permanent +1 on a six-sided
  die is significant," is the mechanism.
- **C halves the gate spread.** East's conditional win rate rises
  from 13.0% to 19.7% while north and south fall. Suggestive at
  this sample size (per-gate cells near 90 games), but consistent.

## Variant B: partial revelation alone

- Win, draw, gate, strategy, and claim numbers all match baseline
  within Wilson noise. First-claimant win share 40.5% versus 44.1%
  is a 3.6-point move with a plus or minus 4.4 interval.
- Routing measurably uses the information: across the 1,920
  seat-games, 35.4% of first explores target a start-revealed
  district. The count of distinct first-explore districts per game
  is unchanged (median 2 in both arms), so bots converge on the
  nearest revealed district rather than splitting by identity.
- Under the frozen preference table (DECISIONS.md D41), profile
  identities did not separate routes enough to move this count.
  Bot play therefore prices B as pure information: real, used, and
  outcome-neutral at this power. A human-play answer needs live
  games; bots do not speculate about opponents' hidden districts.

## Variant C: the claim-recycling loop

Draw games in C average 32.0 proclamations and 31.4 cancellations
(winning games: 12.4 and 11.4). The loop:

1. Pugio pays 1 extra Prestige for a first duel win (1,437 awards
   across the arm). Support and contest fees become easier to fund.
2. More players reach two supports and proclaim (claims 9.5 to 17.2
   per game).
3. Attack-side abilities stack: gladius +1 always, pilum +1 against
   the claimant (8,348 uses), optional challenge +2, against scutum
   +1 alone. Challenges against claimants almost always land.
4. The claim is cancelled, the slot reopens, repeat, until round 24
   of phase 2 times out. Lorica does not slow the loop: it saves the
   beaten claimant's position, but the claim still cancels (D40).
   Draw games average 3.3 lorica saves versus 2.4 in wins.

Ability usage per 480 games: attack bonus active in 469 games
(10,649 duels), defense in 467 (8,473), pilum in 440 (8,348),
pugio in 478 (1,437 awards), lorica in 419 (1,246 saves), galea in
195 (198 inspections; about 0.4 per game, the only scarce ability).

Strategy effects: early_support falls from 26.7% to 16.5% and
counterleader from 24.6% to 20.4%; collector still leads at 27.9%.
Draws absorb a quarter of all games, so per-profile rates compress
overall.

## Equipment versus victory

By game end players hold most items in every arm (losers 0.76-0.80
hold rates), because all six types are collectable by every seat.
What changes is the winner-loser gap:

- A: winners hold an average item at 0.91, losers at 0.77.
- C: 0.89 versus 0.78. Set completion matters less; abilities, not
  counts, decide fights.

Scutum is the most winner-correlated item in C (winners 0.88,
losers 0.63), consistent with defense being the scarce side of the
new duel math.

## Gates

Win-conditional win rates (share of wins taken by each gate among
decided games):

| Gate | A | B | C |
|---|---|---|---|
| P0 north | 28.4% | 28.7% | 25.2% |
| P1 east | 13.0% | 12.5% | **19.7%** |
| P2 south | 31.4% | 31.9% | 28.8% |
| P3 west | 27.1% | 26.9% | 26.3% |

B leaves the V0.8 skew untouched. C compresses it: east nearly
doubles its share. The mechanism is plausibly the duel swarm around
the Peristyle: when the game is decided by challenge chains rather
than the collection race, the 12-step east approach matters less.
Confirm on a larger sample before treating this as settled.

## What to test next

~~C's failure is specific and fixable, and each fix is one knob.~~
Done the same day: the simplified set C2 below implements fixes 1
and the pugio removal; see results. The three-equipment checkpoint
rule stays untested as planned; it changes collection incentives
and should be measured after the duel loop is fixed, not
confounded with it.

## The simplified set (C2, recommended)

The same day, the design direction changed: keep card identity, cut
rule count. C2 (`rules_v09_abilities.json`, engine
`succession-0.9.1-experiment`, results `v09-design-002`) replaces
the C1 subsystems with six one-line cards plus two global rules:

- gladius: +1 attack roll. scutum: +1 defense roll. pilum: +1
  attack roll against the claimant. lorica: unchanged.
- pugio: **you win tied duels** (a tiebreaker, not Prestige).
- galea: **once per game, turn one hidden district face-up for
  everyone** (public; the private-knowledge subsystem is gone).
- Global: **at most one equipment bonus applies per duel side** —
  the best one, never the sum. Validation enforces that ability
  files zero the count tiers, so the two systems cannot stack.

Results (480 matched games per arm, `v09-design-002`):

| Measure | A baseline | C1 stacking | C2 simple |
|---|---|---|---|
| Draws of 480 | 12 | 119 | 25 |
| Median rounds | 26 | 31 | 26 |
| Claims per game | 9.5 | 17.2 | 10.2 |
| Cancelled claims per game | 8.5 | 16.3 | 9.2 |
| Duels per game | 22.8 | 31.2 | 23.8 |
| Gate spread (win-conditional) | 18.4 pts | 9.1 pts | 14.3 pts |

- **The claim-recycling loop is gone.** Claims, cancellations, and
  duels sit within one game of baseline. The remaining draw excess
  (25 versus 12, about 2.7 points, z about 2.1) is small; draw
  games still show late claim fights (29.6 claims versus 9.1 in
  wins) but they stay rare.
- **Abilities stay live.** The attack bonus applies in 472 of 480
  games (7,408 duels), defense in 466, pilum in 444 (5,203 uses),
  lorica saves in 395 (1,093 saves), pugio flips 521 ties across
  263 games, galea reveals in 195 games (198 uses; still the least
  used card, and the only one a player must choose to spend).
- **The collector edge shrinks.** Collector wins 34.0% in A, 25.4%
  in C2; prestige_farmer rises from 12.3% to 16.0%. Without the
  six-item +2 tier, completing the set is no longer the dominant
  plan — which is the design intent of card identity.
- **Scutum is the strongest card** (holder win share 0.286 versus
  base 0.237; gladius, pilum, pugio, galea at 0.255-0.265,
  lorica 0.265). Defense stays the scarce side even without
  stacking.
- **Gates move slightly toward balance** (spread 18.4 to 14.3
  points; east 13.0% to 15.4% win-conditional). Milder than C1's
  compression, which appears to have been an artifact of the
  claim chaos rather than a stable property.
- **Baseline integrity check**: arm A replays identically to the
  first trial (0 of 480 winners differ), after fixing a duel-math
  regression that briefly dropped the count-tier bonus for rules
  without abilities. A regression test now pins the tier bonus
  (`test_baseline_keeps_its_count_tier_bonus_in_duels`).

C2 is the recommended candidate for human playtesting: same rule
count as V0.8.1 plus two start reveals, six card lines, and one
stacking cap.

## Trial D: the three-equipment checkpoint

The planned follow-up (`rules_v09_checkpoint3.json`,
`results/v09-design-003`): C2 plus
`level1.claim_required_equipment: 3` and
`glory.set_completion_reward: 1` (one Prestige, once, for the
full set). Policies read both knobs (D43): collectors rush to the
requirement, other profiles complete the set only when the reward
exists. Baseline and C2 replay identically to run 002 (0 of 480
winners differ), so the arms are comparable.

| Measure | A baseline | C2 | D checkpoint 3 |
|---|---|---|---|
| Draws of 480 | 12 | 25 | 49 |
| Median total rounds | 26 | 26 | **18** |
| Median phase-1 rounds | 18 | 18 | **10** |
| First-claimant win share | 44.1% | 36.7% | **30.6%** |
| Items held per player at end | 4.7 | 4.7 | **2.3** |
| Set completions (all players) | 0 | 0 | 64 |
| Collector win share | 34.0% | 25.4% | 30.4% |
| Gate spread (win-conditional) | 18.4 pts | 14.3 pts | 16.9 pts |

- **The rush works and shortens the game**: phase 1 ends at a
  median of 10 rounds. Median total rounds fall from 26 to 18.
- **Early claiming is a weak move**: the first claimant converts
  only 30.6% of the time versus 44.1% at baseline — the claim
  opens while Prestige economies are thin and everyone is
  close enough to contest.
- **Card identity gets expressed less, not more**: players end
  with 2.3 items on average. The set-completion reward fires in
  only 64 of 480 games; collecting six before the phase-1 clock
  ends is not realistic, so the trade-off resolves to rush under
  bot play.
- Draws double versus C2 (10.2% versus 5.2%); gates stay near the
  baseline skew.

**Conclusion**: keep the checkpoint at six items for now. If a
lower threshold is wanted, pair it with a longer grace period (so
rivals can answer an early claim) and re-measure — the runner
makes that one rules-file edit away.

## Limitations

- Four fixed probe policies with a frozen preference table (D41);
  no adaptive or human play. B's null may not survive human play,
  where hidden information has value bots cannot price.
- 480 games per arm resolves the draw explosion and claim doubling
  decisively; per-gate cells (about 90 decided games) resolve only
  large swings.
- Browser (web/) JavaScript parity was not updated; it gates a
  release, not a trial.
- C1 and C2 ran on the same seeds but their bots diverge after the
  first ability-affected choice, so C1-versus-C2 comparisons are
  statistical, not paired.
- `rules_v08_succession.json` and `rules_baseline.json` are
  untouched. The trial lives in `rules_v09_reveal2.json`,
  `rules_v09_abilities.json` (C2), `succession.py`, and
  `tools/v09_design_experiment.py`.

## The endgame: hill-climb, live probes, and the V0.9 candidate

Date: 2026-11-12. Sources: `results/v09-climb/` (hill-climb, screens
700000+, confirmation 800000+), `results/v09-live-{f4,f3,f1}/`
(OpenAI Decisions, gpt-6-luna, shared cap $1.50 / 2400 calls,
actually spent about $0.87, ledger `results/v09-live-budget.json`).

### From playtest to engine

The human session's level-2 redesign entered the engine as five
default-off knobs (DECISIONS.md D44): claim survival window,
challenge radius, blind support sites, duel loser shame cost,
proclaim cost, plus the officials-off-Peristyle bug fix. E0
(window 2, radius 3, blind support) drew 16.7% under bots; the
climb then screened one knob at a time on 96 matched seeds with
programme.md gates plus predeclared claim-health gates.

### What the climb found

- **Window length is the master switch.** One round: 0% draws but
  trivial crowns. Two rounds with shame: the balanced point. Three
  rounds: 40-62% draws - the playtest's "three is a lot" confirmed
  quantitatively.
- **The challenge radius knob is inert** at or above duel_range
  (duel legality already requires adjacency); the humans' real
  problem was arrival time, which the window itself addresses.
- **Loser shame is the stabilizer.** It converts the window-2
  recycling loop (16.7% draws) into 1.8% by draining re-contest
  budgets.
- **Greedy ascent chose wrong**: it promoted window-1 and dropped
  blind support, but the contest audit showed that combination
  crowns 48% of games with zero cancellations - the fee-2 failure
  shape. Coordinate-wise scores missed the combination.

### Live probes (3 games per arm, 4 model seats)

| Arm | Bots: draws / free crowns | Live: finished / claims contested |
|---|---|---|
| F4 window2+shame+public support | 0% / 13.5% | 2 of 3 / 2 of 4 |
| F3 window2+shame+blind support | 1.8% / 37.5% | 0 of 3 (all timeout, no claims) |
| F1 window1+public support | 0% / 48% | 3 of 3 / 2 of 5 |

F4's live median (25 rounds) matches its bot median (24). F3's
blind support, the playtest's favorite idea, is unreachable for
model players: they cannot find two hidden faction sites inside
24 palace rounds. Blind support stays available as a knob
(`rules_v09f_court.json`) for groups who want a long hunt, but it
cannot be the default.

### The candidate: `rules_v09_succession.json` (0.9.0-court)

Everything learned, in one file:

- C2's six one-line equipment abilities, one modifier per duel
  side; count tiers zeroed; two districts revealed at start.
- Claim window of two rounds: rivals must cancel a claim inside
  the window or it crowns; responses no longer crown.
- Duel loser pays 1 Prestige to the bank (shame).
- Officials moved off the Peristyle (the exploited bug).
- Public support cells, city support allowed, contest fee 1.

Measured on 384 fresh seeds: 1.8% draws (V0.8.1: 3.4%), median 25
rounds, 3.7 claims and 2.7 cancellations per game (fewer,
contested claims instead of V0.8.1's 9.2-made/8.2-cancelled
recycling), first-claimant win 43.5%, and the tightest strategy
spread of any version (16.9% to 31.8% across the four profiles).
Under model play it finishes at bot speed with contested claims.

Open for the release pass: browser JavaScript parity, the print
kit, and a second human session on this candidate. The board
geometry sweeps the playtest asked for (nobody crosses the
middle) remain unrun - the runner now supports them.

## Simplification pass (S-series, 2026-11-13)

A rules-design literature sweep (`notes/rules-elegance-research-2026-11-13.md`,
`notes/v09-simplification-study.md`) gave a test method: every
rule must change a real decision or leave; prefer cuts that
remove text, not choices. Screens ran on 96 matched seeds
(900000+) with the frozen gates.

| Screen | Change | Verdict |
|---|---|---|
| S1 | six abilities collapsed to 3 attack / 3 defense, summed | rejected: strategy spread widens (collector 0.39, farmer 0.10) |
| S2 | drop the optional duel boost | **void**: the patch hit a dead `combat.challenge_bonus` key - a no-op arm, caught during the 0.9.2 kit rewrite |
| S3 | drop the contest fee | rejected: 60% draws, 24 claims per game - the denial loop returns |
| S4 | drop the first-challenger bonus | adopted: healthy, one salad source removed |
| S124 | S1+S2+S4 | rejected: compounds S1's spread damage |
| S2 real | `succession.challenge_bonus` 2 to 0 | adopted: 384-game confirmation green (1 draw, median 23, claims 4.81, east .158 to .182), `results/v09-boost/` |

S24 (S2+S4) is `rules_v091_succession.json` ("0.9.1-trim"),
confirmed on 384 fresh seeds (920000+): 1 draw, median 24 rounds,
4.62 claims and 3.62 cancellations per game, 17% free crowns, and
a slightly tighter strategy spread than 0.9.0 (collector 25.5%,
early support 32.6%, farmer 13.8%, counterleader 27.9%). Because
S2 was a no-op, that file's real content is the first-challenger
cut alone; the duel boost stayed live in 0.9.0 through 0.9.2.
The real boost removal was screened and confirmed after the
discovery and ships as `rules_v093_succession.json` ("0.9.3"):
the first version whose Prestige economy truly has two sources
(duel wins, guard posts) and two sinks (support, contest fee)
plus the bounded shame cost. Validation now rejects unknown
combat keys so a mis-aimed patch cannot pass silently.

## Geometry sweep (G-series, 2026-11-13)

The playtest's board questions, run as a placement sweep
(`notes/v09-geometry-sweep-2026-11-13.md`, runner
`tools/v09_geometry_sweep.py`). No rule text changed anywhere in
the series - every arm is cell placement only.

| Arm | Interior share | East gate | First claimant | Verdict |
|---|---|---|---|---|
| 0.9.1 incumbent | 0.29 | 15.6% | 36.3% | - |
| cardo12 | 0.30 | 32.3% (mirror) | 22.9% | passes, buys nothing |
| centered cardo | 0.43 | 24.0% | 19.5% | fails 0.20 floor |
| interior posts alone | 0.53 | 11.5% | 30.2% | fails: east collapses |
| midpair | 0.36 | 20.1% | 32.0% | passes |
| midpair_posts | 0.62 | 19.8% | 23.4% | passes, promoted |

Confirmed on 384 fresh seeds (950000+): `rules_v092_succession.json`
("0.9.2-crossflow") keeps every health gate green - 2 draws, median
23 rounds, 5.41 claims per game, profiles at 17-36% - while doubling
interior-street traffic (0.29 to 0.62) and lifting the east gate to
19.8% (point estimate; the paired gain is not significant at n=384).
A hostile-review pass reproduced the confirmation bit-exact, replayed
576 fresh games per arm, and confirmed the traffic gain is not a
farmer artifact. A static distance audit puts crossflow's mean
gate-to-site spread at 11.6 steps against 14.0 incumbent and 13.0 for
the centered map. The centered-cardo map is parked with full data:
the tightest gate balance measured (five-point spread) but a
first-claimant win rate below the predeclared floor.

The playtest's challenge-radius rule was then screened on the
crossflow map (96 matched seeds, 980000+, `results/v09-geometry/
radius_screen.json`): radius 1, the only value that binds (duel
legality already covers the claimant's two-cell ring), passes every
gate but moves nothing - east gate .18 to .19, interior share flat,
first claimant .27 to .32, all inside noise. The rule earns no
decision and stays out; the two-round window already carries the
unreachable-claimant load. The playtest's painted three-step radius
is vacuous in engine terms.

A four-game live probe with four model seats
(`results/v09-live-092/`, $0.17) matches the bot shape: 4 of 4
finished, zero draws, 5 of 8 claims contested, 4 cancelled, median
29 rounds, nothing wasted at the cap, first collector 1 of 4. The
crossflow map does not deadlock model play.

## Twin-board redesign (2026-11-13)

The user's review and the playtest's table redesign, implemented:
a separate succession map (`board_level2`, 13x9, four blocks,
gates 4/6/4/6 steps from the crossing) replaces the palace board in
phase 2, every seat returns to its gate on the new map, and the
three meeting places sit one per street arm (elites (6,3),
officials (3,4), army (9,4)) - every gate's nearest site 3 to 5
steps out, none at a gate, none on the Peristyle. Support exists
only on the succession map; the palace phase is pure collection.
Engine: phase-aware board selection, twin-map validation, and
phase-2 displacement to the new gates (`notes/v094-twinboard-2026-11-13.md`).

Confirmed on 384 fresh seeds (1010000+) against the 0.9.3 single
board: `rules_v094_twinboard.json` ("0.9.4-twinboard") holds every
health gate - 2 draws, median 23 rounds (15 collecting, 8
contesting), 4.45 claims per game, first claimant .32 - and gate
rates of .266/.250/.242/.237. A hostile-review pass reproduced
every number bit-exact and sharpened the statistics: the single
board rejects gate uniformity (chi-square p = .041; east alone
p = .0094) while the twin board is statistically indistinguishable
from uniform (p = .87). The east-gate improvement itself is a
point estimate (paired McNemar p = .061 at n = 384), so read it as
"the skew is gone from the measurement", not as a proven effect.
The reset also moves, not erases, phase-1 tilt: the first claimant
now varies by seat (p = .022) where 0.9.3's did not, but that
tilt no longer propagates to final wins. The cost is a weaker
farmer profile (.17 to .12; the duel-win payment is the only
phase-2 income) and a stronger collector (.28 to .35); both stay
inside the predeclared bands. `board_level2.glory_posts` remains a
validated knob if the human session finds the endgame starving.
Open release blocker: the browser JavaScript engine does not
implement `board_level2` yet (the parity suite passes on
pre-twin functionality only).
