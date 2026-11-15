# FINDINGS_V05.md — rule experiments under Decisions play

Branch `feature/v05-experiments`, commit `716bc6e` plus results. Model
`gpt-6-luna`, prompt `v04-1`, projection `v04-proj-1`, tactical
`tactical-v04.1` (all frozen). Plan and predictions:
`notes/v05-experiment-plan.md`. Budget: **$0.2214 spent of the $5.00
authorized on 2026-11-07**.

**Scale and integrity.** Three live tournaments, 32 games each
(16 rotation + 16 pairs), 96 games total; 1,966 Decisions calls,
2.21M input tokens. Zero refusals, zero invalid answers, zero
incomplete games, zero timeouts (all 96 ended by Emperor win). All
96 games replay-verify offline. Scorecards stay clean in every set:
winning-attack utilization 100% (23/23, 19/19, 34/34), zero
shortlist flags, zero `explore_no_gain`, one unproductive move each.

Sections marked **[O]** observation, **[E]** evidence, **[I]**
interpretation, **[H]** hypothesis. Base for every comparison: the
32 mixed V0.4.1 games (`results/v041/games/tb*`, same rotation+pairs
structure, seeds 5201+/5301+; the new sets use 6101+ and later, so
seed variance is inside every comparison).

## Seat-game win shares (per policy)

| Set | decisions | tactical | balanced | greedy |
|---|---|---|---|---|
| base (v041 tb) | 12/48 = 25.0% | 15/48 = 31.2% | 1/16 = 6.2% | 4/16 = 25.0% |
| exp1 lost turn | 11/48 = 22.9% | 13/48 = 27.1% | 6/16 = 37.5% | 2/16 = 12.5% |
| exp2 Peristyle 2 | 11/48 = 22.9% | 13/48 = 27.1% | 7/16 = 43.8% | 1/16 = 6.2% |
| exp3 L1 cap 16 | 9/48 = 18.8% | 16/48 = 33.3% | 4/16 = 25.0% | 3/16 = 18.8% |

Wilson 95% intervals all overlap across rows at n = 48 and n = 16.
No knob crowned the AI players.

## Experiment 1 — duel lost turn: fires, but aims nowhere

`rules_v03_lostturn.json` (bot baseline `results/v03_lostturn`).

**[O]** The consequence is real and cheap. **[E]** 3.16 turns skipped
per game (bots: 3.91); median 14 rounds; max 18 versus base 21; zero
timeouts. Duel victims: 76 skips landed on eventual losers, 25 on
winners.

**[O]** Aggression did not redirect at leaders. **[E]** Duels rose
3.00 to 3.56 per game and decisions duels 0.92 to 1.25 per seat, but
the share aimed at a seat holding an Emperor hit stayed flat (24/96 =
25.0% to 30/114 = 26.3%).

**[O]** A side effect surfaced. **[E]** Auto-granted equipment rose
from 1.88 to 2.47 per game (+32%): skipped turns delay collection, so
the catch-up rule pays out more. **[I]** The lost turn taxes tempo,
and the auto-grant quietly refunds part of the tax.

**[O]** Verdict against the plan's success criteria: the pace and
draw criteria pass; the central one — interference duels at the
Emperor rise — fails. A duel still pays only its winner, so a
skipped leader loses one turn while the duelist spent one turn to
cause it. **[I]** Duel *value*, not duel *cost*, remains the broken
half (same verdict as V0.4.1 Q3).

**Recommendation: do not adopt.** The next combat experiment must
change what a duel pays the winner against a leader (for example, a
bounty on Emperor hits held), not what it costs the loser. Also
unresolved: a lost turn is the harshest consequence for children
(V0.3 caution); only a human playtest can clear it.

## Experiment 2 — Peristyle seal costs 2: a wall, not a tension

`rules_v05_peristyle2.json` (bot baseline `results/v05_peristyle2_bots`).

**[O]** Purchases fell, not deliberated. **[E]** Peristyle buys per
32 games: 56 to 39 (−30%). Games with at least one buy: 29/32 to
23/32. Among seats that do buy, timing did not change: the median
first buy still lands in the first Level 2 round — a buyer at the
checkpoint spends immediately at any price. Peristyle attempts by
decisions seats: 22 to 14; success when attempted stayed perfect
(21/22, 14/14 — attempts only happen with 2 Glory in hand).

**[O]** The model's guard-post blindness survived the price hike.
**[E]** Decisions seats attempted one guard post in 48 seat-games
(one paid). The prediction "guard-post usage becomes mandatory"
failed. **[I]** Cost 2 does not create a seal-strike-save decision;
it locks Glory-poor seats out of the guaranteed buy — the `tb202`
failure mode, now by design.

**[O]** The bot duel surge was an artifact. **[E]** Bots dueled 23%
more under cost 2 (4.57 to 5.61 per game) because `_pick_duel`
refuses fights at the Glory cap and buyers drain to 0. Decisions
seats dueled the same as base (0.92 to 0.98 per seat). **[I]** The
bot baseline measured frozen code, not strategy.

**[O]** One small gain: losers holding unspent Glory fell from 64/96
to 57/96. **[I]** Pricier sinks nudge hoarders to spend. Wide
interval; suggestive only.

**Recommendation: reject cost 2; keep cost 1.** The economy question
it targeted (guard posts undervalued, seals cheap) needs a different
lever — for example, making the Peristyle roll-based like the
Cellars, or paying a Glory bounty for guard-post successes.

## Experiment 3 — Level 1 capped at 16: inert insurance, adopt it

`rules_v05_l1max16.json` (bot baseline `results/v05_l1max16_bots`).

**[O]** The cap never engaged. **[E]** Across the 32 games, Level 1
never exceeded 10 rounds (median 8). The bot baseline is
byte-identical to `results/v03_base`. Every metric sits inside seed
noise; differences from base cannot be attributed to the rule.

**[O]** The tail it bounds is real but rare. **[E]** In all 64 V0.4.1
games, Level 1 ran median 9, p90 13, max 22 rounds; four games (6%)
reached 16 or more — including the `ta05` stall (22) and `ta14` (19).
**[I]** The knob touches about one game in sixteen, exactly the
worst stalls, and nothing else. It removes the "four seats circling
a hidden district" failure while keeping every observed median.

**Recommendation: adopt as a guardrail.** Measured cost is zero; the
benefit only shows in the rare stall. This is the only one of the
three knobs with a positive expected value.

## Cross-experiment observations

- **[O]** Tactical's pairs edge persists everywhere: 10–6, 9–7, 11–5
  this cycle; pooled with V0.4.1, tactical seats won 39 of 128
  pairs seat-games (30.5%, CI 22.8–39.4) versus decisions 25 of 128
  (19.5%, CI 13.3–27.6). **[I]** Still overlapping; the lean is now
  four-for-four across rule sets. **[H]** Tactical's fixed
  Glory-spending discipline beats the model's hoarding leak; a
  Decisions prompt that spends at the cap might close it.
- **[O]** The `balanced` bot topped the seat table in exp1 (37.5%)
  and exp2 (43.8%) after 6.2% at base. **[H]** Friction knobs
  (skips, pricier seals) may favor a steady mid-tier script over
  both AI players; 16 seat-games per set is too few to establish it.
- **[O]** Confidence means barely moved (0.273, 0.277, 0.289 versus
  0.272 base). No rule change made Level 1 less of a noise turn.

## What was not run

- No human-play data; the lost-turn "feel" question stays open.
- No mirror (4× decisions) games this cycle; seat-order analysis
  rests on the rotation and pairs schedules only.
- 32 games per set: exploratory by design, as in V0.4.1.

## Cost accounting

| Experiment | Calls | Input tokens | Cost |
|---|---:|---:|---:|
| 1 lost turn | 612 | 688,112 | $0.0688 |
| 2 Peristyle 2 | 664 | 747,848 | $0.0748 |
| 3 L1 cap 16 | 690 | 777,867 | $0.0778 |
| **Total** | **1,966** | **2,213,727** | **$0.2214** |

Authorized: $5.00 (2026-11-07). Unused: $4.78.

## Reproduce

```bash
for e in 1_lostturn_ai 2_peristyle2_ai 3_l1max16_ai; do
  python3 sim.py tournament --config tournaments/v05_exp$e.json \
    --out results/v05_exp${e%%_*} --live-decisions --resume
done
python3 analyze_v041.py analyze results/v05_exp1   # scorecard
python3 analyze_v041.py report  results/v05_exp1   # strength, CIs
```
