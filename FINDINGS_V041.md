# FINDINGS_V041.md — AI tournament and decision analysis

Base commit `c58a76d` (V0.4 merged), branch `feature/v041-ai-tournament`.
Rules `rules_v03_base.json` (hash `405f6d18dee5f068…`), model
`gpt-6-luna`, prompt `v04-1`, projection `v04-proj-1`, tactical
`tactical-v04.1` (all frozen). Full logs: `results/v041/` (per-game
`decisions.jsonl`, `events.jsonl`, `result.json`; aggregates
`decision_analysis.json`, `tournament_report.json`,
`tournament_v041_*.json`). Qualitative studies: `notes/v041/`.

**Scale and integrity.** 64 live games (32 mirror + 32 mixed), 2,845
Decisions calls, 3.19M input tokens, **estimated $0.319** under the
authorized $1.00 aggregate cap. Zero refusals, zero invalid answers,
zero retries, zero incomplete games. All 64 games replay-verify
offline. Latency p50 161 ms, p95 255 ms, max 1.9 s.

Sections marked **[O] observation**, **[E] evidence**, **[I]
interpretation**, **[H] hypothesis** — kept apart per the brief.

## Tournament results

Matchup-specific outcomes (32 games each seat rotates; per-policy
seat-games in parentheses):

| Matchup | Games | Wins |
|---|---:|---|
| 4× decisions (mirror) | 32 | decisions 32 |
| decisions+tactical+balanced+greedy (rotation) | 16 | tactical 6, decisions 5, greedy 4, balanced 1 |
| 2× decisions + 2× tactical (pairs) | 16 | tactical 9, decisions 7 |

Mixed-game seat shares: **tactical 15/48 = 31.3% (CI 19.9–45.3),
decisions 12/48 = 25.0% (CI 14.5–38.5)** — overlapping intervals, no
established difference at this sample size. Mirror-game spread (all
decisions): gates P0 33% / P1 17% / P2 31% / P3 19%; turn positions
pos1 36% / pos2 22% / pos3 17% / pos4 25% — every pairwise CI
overlaps at n = 32. Durations: median 16.5 rounds, mean 17.0, max 26
(bot games on the same rules: median 14).

## The nine questions

### 1. Is Decisions demonstrably stronger than Tactical?

**[O]** No. **[E]** 12/48 vs 15/48 mixed seat-wins; tactical won the
pairs matchup 9–7. Confidence intervals overlap by ~17 points.
**[I]** Decisions plays at roughly tactical's strength: both exploit
the same two edges (favorable duels, Glory-timed Emperor swings).
**[H]** A 3–4× larger sample might separate them; the observed gap
(tactical +6 points) is what a mildly stronger player would show, and
also what noise would show.

### 2. Does AI play reveal strategies the scripted bots overlooked?

**[O]** Yes, two. **[E]** (a) *Glory-engine opening*: in
`tb209` (notes/v041) the winner explored only 3 districts, won 4
duels and 2 guard posts, and let the auto-grant complete the kit —
treating Level 1 as Glory farming, not collecting. Decisions seats
collected 5.39 items/seat vs tactical 5.90 and bots 6.00 — and still
won games. (b) *Seal-market timing*: decisions has the best
seal-acquisition efficiency of any policy (0.73 seals per attempt vs
tactical 0.61, balanced 0.60, greedy 0.56), buying the guaranteed
Peristyle seal early and rolling the cheaper Cellars.
**[I]** The auto-equip rule quietly legitimizes a whole strategy
class (skip collection, bank Glory) that no scripted bot uses.

### 3. Is aggressive play genuinely weak, or badly implemented?

**[O]** Badly implemented — partially. **[E]** Decisions fought
*more* than any policy (1.45 duels/seat vs tactical 0.98) and won
**62% as attacker** (the old `aggressive` bot: 38%). In `ta07` all 14
duels took the highest exact win chance on the menu (never a 42%
underdog fight; the 72% edge both times it existed), and among equal
targets it preferentially hit the Emperor leader. **[I]** With target
selection, dueling is a working Glory engine. **[E] But:* in that
same game the pile-on could not slow the leader (a duel pays only the
winner; the loser keeps everything), cap blocking wasted 4 of 14 duel
wins, and the two most belligerent seats made zero Emperor attempts —
"combat competence without conversion." **[I]** Duel *value*, not
duel *odds*, is the weak mechanic.

### 4. Which mechanic generates the most interesting decisions?

**[O]** The Glory economy. **[E]** Every close game in
`notes/v041/` turned on Glory timing: `ta14` (all four seats at 1
Emperor hit; winner saved a Glory mid-game and spent it on a 72%
attack); `ta07` (leader lost by exactly the missing +2 twice); `tb202`
(Glory-starved seats never got the guaranteed Peristyle buy and made
0–1 Emperor attempts). Model confidence is measurably higher on these
turns: 0.44 mean in Level 2 vs 0.19 in Level 1 (n = 913 / 1,932,
tournament-wide).
**[I]** One currency, three sinks (Peristyle seal, Emperor +2,
banking), real tension.

### 5. Which mechanics are ignored or exploited?

**[O] Ignored:** guard posts by decisions seats — across all 176
decisions seat-games there was **one** guard-post attempt (0.006 per
seat). `tb202`'s losing seats earned no Level 1 Glory, were locked
out of the guaranteed Peristyle buy, and made 0–1 Emperor attempts;
`ta05`'s candidate lists offered guard posts 70 times and never chose
one. **[I]** The model systematically undervalues the board's only
reliable Glory source; this is its clearest recurring weakness, and
it cost games. **[O] Exploited:** the auto-grant (see Q2).
**[O] Mechanically pointless:** leader interference — `ta14` declined
interference duels every turn ("hits are irreversible, targets hold
0 Glory"); nothing in `rules_v03_base` lets a duel slow a leader.

### 6. Is the automatic equipment catch-up still appropriate?

**[O]** It now does double duty. **[E]** With bots, 86% of seats
needed zero granted items (V0.1 data); with decisions seats, 0.61
items/seat are granted — competent players deliberately under-collect
to farm Glory/duels. **[I]** The rule no longer merely rescues laggards;
it subsidizes a degenerate-but-fun opening. **[H]** If V0.5 makes
Glory harder to bank, re-measure; if collection should matter, the
checkpoint could require N-of-6 items (needs a small new knob).

### 7. Is the Emperor battle sufficiently interactive?

**[O]** No — unchanged from V0.3's verdict, now with AI-era evidence.
**[E]** `ta14`: five straight Emperor hits, miss-retreat never fired,
interference available and declined every turn; `ta07`: a 7-attack
pile-on could not cost the leader a single tempo. **[I]** The
`duel_lost_turn` variant remains the most promising untested fix
*under competent play* (the V0.3 bot test showed aggressive 6%→14%).

### 8. Is turn-order advantage still significant?

**[O]** Suggestive, not established. **[E]** Mirror games: pos1 36%
vs pos3 17%, but CI 22–52 vs 8–32 overlap (n=32). `ta14`'s verdict
line: "initiative first — round order let P0 close before P3, the
other one-hit player, ever acted." **[I]** The structural concern
stands (V0.2 found a 31/20 final-round initiative gap over 1,000 bot
games); 32 AI games cannot confirm or clear it.

### 9. Which three rule experiments should V0.5 prioritize?

All three are runnable today with existing knobs (files included on
this branch, baseline untouched):

1. **`rules_v03_lostturn.json` Decisions tournament** (existing
   file). Tests whether duel consequences finally make interference
   and aggression pay *under strong play* — the V0.3 result (bots
   only) is the confound this removes. Predict: decisions duel rate
   stays ~1.4/seat but shifts to leaders; watch tactical vs decisions
   gap and low-value-duel share.
2. **`rules_v05_peristyle2.json` — `peristyle_glory_cost: 2`.** The
   Peristyle buy is currently underpriced (best seal efficiency,
   chosen in every close game). Cost 2 makes "guaranteed seal" cost
   an entire Emperor boost — the economy's central tension gets
   sharper. Predict: seal efficiency drops toward 0.6; Glory-engine
   openings weaken; guard-post usage (the model's blind spot) becomes
   mandatory.
3. **`rules_v05_l1max16.json` — `level1.max_rounds: 16`.** `ta05`
   exposed a stall: all four seats at 5/6 items circling the last
   unrevealed district for 10 rounds (29 of 35 turns were moves;
   Level 1 confidence 0.19, so the top pick itself was noise).
   Capping Level 1 at 16 rounds bounds the stall by timeout while
   keeping the median (8–9 rounds) untouched. Predict: p95 game
   length falls ~4 rounds; auto-grant share rises slightly.

Design candidates needing new (optional) knobs in V0.5, in priority
order: checkpoint at N-of-6 equipment; serpentine turn order or
simultaneous Emperor resolution for the initiative gap.

## Decision-quality scorecard (2,845 live decisions)

| Metric | Value | Verdict |
|---|---:|---|
| Winning-attack utilization | **92/92 = 100%** | never once forgone |
| Low-value duel share (p<50% or Glory-capped) | 13.3% | mostly cap-waste, not bad odds |
| Unproductive moves (goal-distance heuristic) | 0.8% | clean routing |
| `explore_no_gain` turns | 0 | never explored a known duplicate |
| Seats losing with unspent Glory | 34/176 (19%) | hoarding is its main leak |
| Glory wasted at cap | 0.30/seat | low but nonzero |
| Mandatory-action shortlist exclusions | **0** flags | shortlist never hid a win |
| Median legal → candidate actions | 51 → 16 | only near-duplicates dropped |

**[E]** Shortlist audit: 63,864 exclusions across 2,165 mirror turns,
all of them duplicate duel endpoints (44.6K), grouped moves (17.3K),
or grouped guard posts (1.9K) — every attack, seal, explore, and
checkpoint action was always offered. **[I]** No outcome can be
blamed on hidden filtering.

**Model confidence is choice uncertainty, not win probability** (per
the API contract and this study's data): mean 0.272 over 2,845
decisions (p10 0.09, p90 0.54), higher in Level 2 (0.41) than Level 1
(0.19), highest on winning-attack turns (0.84+). Low confidence
never produced an illegal or erratic pick in 2,845 tries.

## What was not run

- No statistical claim of policy superiority (sample is exploratory
  by design; nothing outside CIs is asserted).
- No `selection_mode=sample` games, no prompt variations, no
  per-seat memory (all explicitly out of scope).
- No new engine mechanics; the two `rules_v05_*.json` files are
  proposals, not adopted rules.

## Cost model going forward

At measured rates (~$0.000112/call, ~66 decisions per 4-player game),
a 64-game tournament costs **≈ $0.32 and ~40 minutes**; a 200-game
study ≈ $1. Budgeted AI evaluation is now cheap enough to be routine.
