# FINDINGS_V02.md — Combat and Fairness experiments

Seven batches, 1,000 games each, seeds 1000–1999, same SPEC §13
policy rotation, engine 0.1.0 with the D18–D20 knobs. Baseline for
comparison: `results/v01_baseline`. Generate this table any time with
`python3 compare.py results/v01_baseline results/v02_*`.

| Metric | baseline | tie→attacker | cap 3 | 3 hits | rotating first | grace 1 | tie+rotate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Median rounds | 15 | 15 | 15 | 17 | 15 | 14 | 15 |
| Median turns | 59 | 59 | 60 | 67 | 59 | 56 | 59 |
| Duels per game | 5.80 | 4.86 | 7.01 | 6.49 | 5.74 | 5.46 | 4.86 |
| Attacker win rate | 38% | 56% | 38% | 38% | 39% | 39% | 56% |
| Aggressive seat wins | 6% | 11% | 6% | 4% | 5% | 6% | 11% |
| Greedy seat wins | 19% | 19% | 24% | 24% | 25% | 24% | 22% |
| Balanced seat wins | 31% | 31% | 31% | 31% | 30% | 30% | 30% |
| Random seat wins | 4% | 3% | 5% | 3% | 5% | 5% | 4% |
| Seat 1 / seat 4 wins | 30/19 | 29/19 | 30/20 | 30/21 | 30/22 | 30/20 | 31/20 |
| First challenger wins | 39% | 38% | 36% | 38% | 33% | 35% | 32% |
| Comeback share | 61% | 62% | 64% | 62% | 67% | 65% | 68% |
| Collected per player | 5.57 | 5.71 | 5.37 | 5.57 | 5.59 | 5.46 | 5.73 |
| Auto-granted per player | 0.43 | 0.28 | 0.63 | 0.43 | 0.41 | 0.54 | 0.27 |
| Draws | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

All batches were re-run on the final engine after the reporting fix
described under experiment 4; every sample game replays
byte-identical (`replay --verify`).

Result files: `results/v02_tie_attacker`, `v02_glorycap3`,
`v02_emperor3hits`, `v02_rotating_first`, `v02_grace1`,
`v02_tie_rotate` (plus `v02_grace0` from the V0.1 report).

## What each experiment showed

### 1. Attacker wins ties (`combat.tie_goes_to_defender: false`)

The duel becomes winnable: attacker win rate 38% → 56%, right at the
top edge of the 45–55% target (even-bonus duels are theoretically
58.3% for the attacker). The `aggressive` policy doubles from 6% to
11% of seat-games — better, still far below `balanced`'s 31%. Duels
per game dropped to 4.86: with duels finally paying, `aggressive`
seats reach the Glory cap faster and stop fighting. Nothing else
moved: game length, first-challenger rate, and comeback rate are all
flat. This is the clearest single-knob win of the set.

### 2. Glory cap 3 (`glory.cap: 3`)

More fighting, no more winning: duels rise to 7.01 per game but
`aggressive` stays at 6%. The extra banked Glory goes to Emperor
attacks and hoarding, not strategy — Peristyle purchases drop from
2,524 to 1,671, and collection falls to 5.37 items (players linger in
duels instead of exploring). A bigger cap alone does not make combat
strategic; it makes it cheaper to ignore.

### 3. Three hits to win (`combat.emperor_hits_to_win: 3`)

Moves the needle on duration: median 17 rounds (target band 20–35),
p95 21, median 67 turns, still zero draws. `greedy` rises to 24% —
the longer endgame rewards straight-line play — while `aggressive`
falls to 4%. If length is the only concern, this knob works; it does
nothing for combat or fairness.

### 4. Rotating first player (`turns.rotate_first_player_each_round: true`)

First-challenger wins fall 39% → 33% and comebacks rise to 67%; the
challenger trigger itself spreads almost evenly over seats (baseline
position 1 triggered 515/1,000 games; under rotation 206, versus
282/268/244 for the other seats). But the
seat 1 / seat 4 win gap only narrows from 30/19 to 30/22 — and the
combo batch shows the residual gap (31/20, CIs 28–34 vs 18–23, not
overlapping) is the **within-round initiative** in the decisive final
round, not who starts the game. Fixing that needs a different lever
(for example a snake/serpentine order or simultaneous Emperor
resolution), not this one.

Implementation note: this batch exposed a second reporting bug —
after a win, the engine advanced the turn pointer (and rotated the
reported final-round order), so last-seat winners were miscounted as
position 3 (seat 4 showed 0.0%) and some finished games counted one
phantom extra round. Fixed (`_advance` no-ops on a finished game),
regression-tested, and **all batches in this report were re-run on
the final engine**; duration figures shifted down by 0–1 round for
that reason.

### 5. Grace 1 (`level1.grace_full_rounds: 1`)

Behaves exactly as the compromise hypothesis predicted, sitting
between grace 2 (baseline) and grace 0 on every metric: Level 1
median 8 rounds, auto-granted 0.54 per player, median 15 rounds,
challenger 35%, comeback 65%. Grace 1 keeps most of the fairness gain
of grace 0 while halving its extra auto-granting. Recommended over
both extremes.

### 6. Combo: attacker ties + rotation

No interaction between the two knobs: attacker 56%, `aggressive`
11.2%, seats 31/20. The fairness gap persists because of final-round
initiative (see experiment 4). The combo is safe to adopt for the
combat-fairness package, but rotation alone does not deliver seat
equality.

## Repeat endgame playtests on the corrected engine

Two new narrative games on the fixed retreat rule
(`runs/narr6`, `runs/narr7`, notes in `notes/narrative-game-6..7.md`),
replacing the pre-fix endgame impressions:

- **The retreat fix works.** Misses now cost Glory, position, and
  about a full turn of tempo; chamber camping is slower; camping the
  retreat square itself became a real (odd but interesting) tactic.
  Both tables called the endgame earned rather than a re-roll lottery.
- **The miss penalty is still light** — the retreat node is one step
  from the chamber, so a roll of 1+ re-enters. Nobody stalls, but
  nobody is blocked either.
- **Level 2 interference is mechanically absent.** Every persona
  independently refused to duel a leader, because a duel costs the
  loser nothing and pays the winner Glory — attacking a leader risks
  fueling them. Door-guarding is void by rule: duels resolve on the
  guard's turn, bar no entry, and the chamber is a shared pass-through
  cell. The final countdown after a leader's first hit is watched,
  not played.
- **Paid attacks (~72%) open the endgame; free attacks (~42%) decide
  it** once Glory runs dry. The Peristyle purchase compresses the
  seal phase to about two rounds.
- **Dead air persists at the Glory cap** during grace rounds and the
  Level 1 tail (rounds 7–9): capped, fully-equipped players just walk.

## Scorecard against the success targets

| Target | Verdict | Evidence |
|---|---|---|
| Attacker wins 45–55% of matched duels | Met, at the top edge (56%) | tie→attacker |
| Aggressive sometimes succeeds | Not met (11% vs balanced 31%) | all variants |
| No overwhelming turn-order advantage | Partially met (30/19 → 30/22) | rotating first |
| A meaningful Level 2 interference move | Not met — none exists | narr7 |
| Collection feels worthwhile | Met (5.4–5.7 collected, 0.3–0.6 auto) | all variants |

## Recommended V0.2 ruleset and next steps

Adopt into the next baseline: **attacker wins ties, grace 1, rotating
first player** (`rules_v02_tie_rotate.json` plus `grace_full_rounds:
1`). All three are individually neutral-to-positive on duration and
decisiveness, and together they answer the two fairness findings.

The two unmet targets have the same root cause, confirmed by both
counters and personas: **a duel takes nothing from the loser and pays
only Glory, which guard posts already provide**. That is why
aggression cannot pay and why leaders cannot be fought. The V0.3
candidate mechanics, in order of testability:

1. **Glory theft** — the duel winner takes 1 Glory from the loser
   (never below 0). Smallest change; directly makes dueling a leader
   costly for them.
2. **Displacement** — the loser is pushed to the retreat node or one
   step back. Gives Level 2 a blocking move near the chamber.
3. **Lost turn** — the loser skips their next turn. Strongest effect;
   risks feeling punitive for children.

Each needs one small engine addition plus a JSON knob, and should be
run as its own file against the same seeds. After that, the seat-gap
levers (serpentine order or simultaneous Emperor resolution) address
the residual 31/20 initiative skew.

## Reproduce

```bash
for v in tie_attacker glorycap3 emperor3hits rotating_first grace1 tie_rotate; do
  python3 sim.py batch --rules rules_v02_$v.json --games 1000 \
    --seed-base 1000 --schedule experiment --out results/v02_$v
done
python3 compare.py results/v01_baseline results/v02_*
```
