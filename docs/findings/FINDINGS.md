# FINDINGS.md — baseline experiment V0.1

All numbers come from the files in `results/v01_baseline/`
(`summary.json`, `games.csv`, `sample_games/`), produced by:

```bash
python3 sim.py batch --rules rules_baseline.json --games 1000 \
  --seed-base 1000 --schedule experiment --out results/v01_baseline
```

The schedule follows SPEC §13: 250 games all-balanced, 250 with one
rotating `aggressive`, 250 with one rotating `greedy`, 250 cycling
`random,greedy,aggressive,balanced` through all 24 seat permutations.
Seeds 1000–1999. Engine 0.1.0, rules hash
`c41593ef305600347ff48397f9e005f3b59ba16399b66af183ea47ea35054cb8`.
Two identical 8-game batches produced byte-identical `games.csv` and
`summary.json`. Smoke bundle: 10 games with full logs in
`results/smoke10/full_games/`; replays verified for smoke games
g000003 and g000010 and baseline games g001000–g001002.

## 0. Engine bug found and fixed during the study

The five narrative playtests (§6) exposed a real engine bug: a failed
Emperor attack set the retreat position and then overwrote it with the
action destination, so the SPEC §7 retreat to `[2,3]` never happened
and misses cost no tempo. Three independent playtest agents found it
by reading the logs; the original unit test passed because it returned
early on wins and never exercised a miss. Fixed (movement now resolves
before the outcome, so the retreat sticks), covered by a stronger test
and a new `check_invariants` rule, and every batch in this document
was re-run on the fixed engine.

## 1. Does the game reach a winner, and after how long?

Always. 1,000 of 1,000 games ended with an Emperor kill. No phase-1
timeouts, no phase-2 draws.

| Metric | Mean | Median | p90 | p95 | Max |
|---|---:|---:|---:|---:|---:|
| Full-game rounds | 15.47 | 15 | 18 | 18 | 24 |
| Full-game turns | 60.18 | 59 | 69 | 72 | 95 |
| Level 1 rounds | 9.11 | 9 | 9 | 10 | 11 |
| Level 2 rounds | 6.36 | 6 | 8 | 9 | 15 |

Games are **decisive but shorter than the 20–35 round target**
(SPEC §13). Level 1 is stable at 9–10 rounds; Level 2 resolves in
about 6 rounds because the two-seal entry plus two Emperor hits at a
44.8% hit rate finishes fast. (Durations in this report come from the
final engine, which no longer counts one phantom round after a
last-seat win; see FINDINGS_V02.md experiment 4.)

## 2. Collected versus auto-granted equipment

The six-item quest is real for bots that want it:

- Players collected **5.57 of 6** items on average before the
  transition.
- **86.3%** of the 4,000 player-games needed **zero** auto-granted
  items; 7.5% needed three or more. Average auto-granted: 0.43.
- 95.1% of players actively explored at least three districts.
- 96 of 4,000 player-games (2.4%) collected nothing — the `random`
  seats that wandered.

Hypothesis 1 ("auto-grant may erase the collection challenge") is
**not confirmed for goal-directed play**: the auto-grant mostly
rescues random seats. The narrative games (§6) show a softer picture
with human-like variety: one winner explored only 2 of 6 districts and
lost nothing, and a duel-only persona entered Level 2 with a full free
kit, so the catch-up rule can make Level 1 feel weightless for players
who do not engage with it.

## 3. Fighting: frequency and usefulness

- **5.80 duels per game**; 63%+ of games had at least two. Target met.
- The initiator usually loses: **attacker won 38.2%**, defender 61.8%
  of 5,797 duels. With equal equipment the tie rule hands the defender
  6 of 36 outcomes.
- Dueling does not pay: `aggressive` won **6.0%** of its 500
  seat-games (95% CI about 4–9%), versus **31.4%** for `balanced`
  (862/2,750, CI 29.6–33.1), 19.2% for `greedy`, 4.0% for `random`.
- Glory comes from guard posts (5,173 attempts, 50.9% success), not
  fights. Duels occupy 9.6% of turns; 90.4% of turns have no player
  interaction.

Aggression is a trap under the baseline: the defender-biased tie rule
plus lost tempo beats the 1-Glory duel reward. The narrative tables
add nuance the counters miss (§6): duels with an equipment edge felt
good, ties decided whole rivalries on coin flips, and Level 2 duels
felt pointless because nothing can slow an Emperor runner.

## 4. Strategy balance, gates, and turn order

Per-seat win rates (a fair policy scores 25%):

| Policy | Seat-games | Wins | Rate | 95% CI |
|---|---:|---:|---:|---|
| balanced | 2,750 | 864 | 31.4% | 29.7–33.2 |
| greedy | 500 | 96 | 19.2% | 16.0–22.9 |
| aggressive | 500 | 30 | 6.0% | 4.2–8.4 |
| random | 250 | 10 | 4.0% | 2.2–7.2 |

- Choices matter (hypothesis 4): `balanced` beats `random` about
  eight to one.
- Gates are near fair (hypothesis 5): P0 27.5%, P1 26.1%, P2 22.9%,
  P3 23.5%; all confidence intervals overlap. Note the south gate P2
  starts on the Emperor chamber cell, which the tactician persona in
  game 3 exploited immediately.
- **Turn order is the real inequality**: seat position 1 won 30.3%
  (CI 27.5–33.2) versus 18.7% for position 4 (CI 16.4–21.2); the
  intervals do not overlap. The first challenger also comes
  disproportionately from early seats (position 1: 515 of 1,000
  triggers; position 4: 62).
- The first challenger wins **38.6%** (CI 35.6–41.7) — a real but not
  decisive edge; 61.4% of wins are comebacks. Not a pure sprint.

## 5. Glory, seals, and the Emperor

- Glory earned averages 1.9 per player; 0.46 per player is wasted at
  the cap of 2; 0.81 is spent.
- Peristyle is the Glory sink: **2,500+ bought seals** versus about
  700 Glory spent on Emperor attacks. One Glory for a guaranteed seal
  reads as underpriced (narrative game 5 said the same).
- Acquire rates: cellars 66.4% (roll 3+), peristyle 61.7% including
  purchases, guard barracks 57.8% (contest). Attempts average 3.12 per
  player for two seals — no grind.
- Emperor: 6,966 attempts, 3,118 hits (44.8%), 1,000 kills. With the
  retreat rule now actually enforced, a miss costs one turn of
  tempo; no endgame drag appeared (zero phase-2 timeouts).

## 6. Narrative playtests (five LLM-driven games)

Five games ran with role-playing agents through the same CLI loop,
one action per turn, observations only (`runs/narr1..5`; reports in
`notes/narrative-game-1..5.md`; each replay-verified). They played
before the §0 retreat fix, so their "retreat never fired" impressions
trace to that bug; each report carries a caveat banner. Themes:
cautious merchants, four duelists, four contrasting personas, a
catch-up focus game, an endgame focus game. Winners: scholar,
duelist-bear, tactician, explorer-racer, gambler — five different
seeds, four different gates, three comeback wins.

What the counters could not capture, agreed across tables:

1. **The Glory cap of 2 deadens Level 1.** Capped players lose their
   guard-post action and bank duel wins as `glory_wasted_at_cap`
   (seven wasted rewards in one game; a 4-0 duelist earned nothing).
   The grace rounds after the checkpoint claim are the dullest
   stretch: capped, fully equipped players just move.
2. **Equal-tier duels feel rigged.** Ties to the defender decided
   whole rivalries (3 of 11 duels in one game); attackers with an
   equipment edge enjoyed fights, even-odds attackers regretted them.
3. **Level 2 has no interaction.** A duel cannot remove hits, seals,
   or delay a leader; three tables independently wanted a way to
   interfere with an Emperor runner.
4. **The paid Emperor attack reads as a purchase.** +2 for 1 Glory
   (about 92% per one table's count) made the endgame a shopping
   race; paid attacks losing on ties stung hardest.
5. **Auto-equip flattening cuts both ways.** It rescued a reckless
   player's 2-item kit and kept games close, but a player who
   explored nothing entered Level 2 identical to one who explored
   everything — deflating for the racer.
6. **Dice spite created the best stories** (double 1-versus-6 guard
   losses), and the two-hit Emperor finishes stayed genuinely tense
   even while players criticized the economy around them.

## 7. Answering the design questions

1. **Level 1 too quick?** No — 9–11 rounds, bots collect 5.57 items.
   But grace rounds are dead air for capped players.
2. **Does aggression pay?** No — see §3; the narrative tables add
   that ties feel unfair rather than strategic.
3. **Pure sprint?** No — 61% comebacks. Turn order, not the
   checkpoint, is the fairness risk.
4. **Dice dominant?** No — policy choice explains the win spread.
5. **Gates fair?** Within noise (±3 points on 1,000 games).
6. **Endgame drag?** No — the opposite: games run 5–19 rounds under
   the 20–35 target.
7. **Comebacks?** Common and viable; the catch-up rule mostly helps
   non-engaged players, which is both its job and its PR problem.

## 8. Top three single-knob experiments next

1. **`rules_v02_grace0.json` — `grace_full_rounds: 0`.** Already run
   on the same 1,000 seeds and schedule
   (`results/v02_grace0/summary.json`): Level 1 median 9 → 7 rounds;
   first-challenger win rate 38.6% → 34.3%; comeback share 61.4% →
   65.7%; last-seat win rate 18.7% → 20.7%; auto-granted 0.43 → 0.70
   per player; median full game 15 → 14 rounds; still 1,000/1,000
   decisive. Grace removal compresses collection and slightly
   flattens the seat skew; grace 1 was subsequently tested and is the
   recommended compromise (see FINDINGS_V02.md).
2. **`rules_v02_emperor3hits.json` — `emperor_hits_to_win: 3`.** The
   cleanest lever toward the 20–35 round target. Watch phase-2
   timeouts (currently zero) and whether paid attacks dominate.
   The narrative tables suggest pairing it with a cheaper Glory
   attack bonus review, but change one knob at a time.
3. **`rules_v02_duelrange1.json` — `duel_range: 1`.** Tests whether
   encounters become deliberate choices instead of drive-by coin
   flips, and whether `aggressive` recovers beyond 6%. The tables
   suggest the deeper problem is the tie rule and the Glory cap, so
   `combat.tie_goes_to_defender: false` and `glory.cap: 3` are the
   next-duel knobs after range.

Run each with the same seeds and schedule for comparability:

```bash
python3 sim.py batch --rules rules_v02_emperor3hits.json --games 1000 \
  --seed-base 1000 --schedule experiment --out results/v02_emperor3hits
```

## 9. Limitations

- Bots are simple heuristics; the retreat fix barely moved bot stats
  (one extra step per miss), so §1–§5 numbers would barely change
  under other small fixes too — treat sub-2-point differences as
  noise.
- 1,000 games resolve about ±3 points on a 25% rate; gate claims
  under 5 points are not separable here.
- The qualitative games used scripted-persona LLM agents, not humans
  (`notes/`), and ran pre-fix (see §0); treat their endgame-tempo
  impressions as indicative, not measured.
