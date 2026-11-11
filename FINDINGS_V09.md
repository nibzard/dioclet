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
