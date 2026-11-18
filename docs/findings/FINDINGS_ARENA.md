# FINDINGS_ARENA.md — Arena series runner and play-quality measurement

Phase 4 of [`docs/model-context-plan.md`](../model-context-plan.md):
the series runner (`arena --series`), the metrics in `summary.json`,
and the tactical fixture check (`arena --fixtures`). This file records
the methodology, the metric definitions, and the results of each
measurement series. Every later phase adds its series under
"Measurements against the baseline".

## Methodology

### Series design

One series plays `seeds x 4` games under one budget. The shipped
baseline is [`arena/matches/series-four-way.json`](../../arena/matches/series-four-way.json):

| Element | Value | Why |
|---|---|---|
| Players | `clef/clef-flash`, `pplx/pplx-decider-v1.3`, `clef/clef`, `pplx/pplx-decider-flash-v1.3` | Two providers with usable rate limits, two models each. The gateway free tier (5 requests per minute) collapsed the first attempt, so no gateway seat |
| Seeds | 42-44 (3 seeds) | Each seed gives 4 games, one per seat. Cut from 5 seeds to keep the `clef` model under the budget |
| Budget | 2000 calls, $0.75 | ~110 turns x 12 games at the plan's estimate |
| `rotate_seats` | true | Seat position is part of the measurement |
| `shuffle_candidates` | true | Position bias is part of the measurement |

### Seat rotation (Latin square)

Game `g` of a seed seats player `i` at seat `P((i + g) mod 4)`. Every
player visits every seat exactly once per seed, so seat effects
(duel range, turn order) average out of the win-rate comparison. The
same seed plays all four games; the rotation is the only experimental
variable between them.

### Candidate shuffle

When `shuffle_candidates` is true, each remote seat sees its candidate
shortlist in a shuffled order. The shuffle is deterministic:
`sha256("series-shuffle:<seed>:<game>:<turn_id>:<seat>")[:8]` seeds a
`random.Random`, so a rerun reproduces the same orders. The legal
actions keep engine order; only the shortlist is permuted. The order
is recoverable from two places:

1. `series-game.json`, the sidecar next to each `match.jsonl`: one row
   per remote turn with the shown `candidate_order` and the `selected`
   action ID.
2. Each `decision` line's `attempts[].exchange.request`, which contains
   the exact request body with the shuffled shortlist.

### Budget

All games share one budget object. A cap reached mid-game marks that
game incomplete, and the runner marks every remaining game skipped. The
pre-run estimate prints the expected games, calls, and cost, and asks
for confirmation on a terminal; `--yes` approves a non-interactive run.

### Estimate and measured turns

The estimator assumes 110 turns per game (the plan anchor) and 6000
input tokens per call. A measured local-bot game at the shipped rules
(2026-11-16, `matches/bots.json`, seed 42) ran 152 turns, so the real
call count can exceed the estimate and the call cap may stop the
series a few games early. The estimate is an assumption, not a limit;
`summary.json` records the true totals.

## Metric definitions

`summary.json` sits in the series run directory. One player entry per
`provider/model` label:

| Metric | Definition |
|---|---|
| `games`, `wins` | Games the player sat in; games it won (outcome `win`, winner = its seat) |
| `win_rate_wilson_95` | Wilson score interval for the win rate, 95% (z = 1.96), rounded to 4 decimals. Use the interval, not the point estimate, when players sit few games |
| `wins_by_seat` | Wins per seat `P0`-`P3`; a seat-skewed table points at a seat advantage the rotation did not cancel |
| `incomplete_games` | Games the player sat in that ended early (budget, provider failure, Ctrl-C) |
| `missed_interventions` | See below |
| `calls`, `input_tokens`, `cost_usd` | Remote calls and usage from the `result` line of each game |
| `latency_ms.median`, `latency_ms.p95` | Over the player's decisions; linear-interpolation percentiles |
| `position1` | `selected` / `turns`: how often the player chose the candidate shown first in the shuffled shortlist (position bias check) |

### Missed intervention

A turn counts as one missed intervention for a seat when all of these
hold:

1. The observation has a `pending_claim` owned by another seat.
2. The legal actions contain a duel against that claimant.
3. The seat selected a different action.
4. The game ended with `end_reason` `survived_window`, the claimant as
   the winner, on the claim that was pending at this turn (a claim the
   seat could have cancelled).

Condition 4 keeps the count honest: a duel was possible, the claim won,
and it was the same claim. Superseded claims (cancelled, then
re-proclaimed by the same player) do not count against earlier turns.
The count is a play-quality signal against the tactical fixture
"cancel a claim that wins this round".

## Tactical fixtures

`arena --fixtures` asks each remote provider that has keys, once per
frozen position, to select an action; `--fixtures-bots` adds the local
bots. The three frozen positions in
[`arena/tests/fixtures/tactical/`](../../arena/tests/fixtures/tactical/):

| Fixture | Situation | Correct action |
|---|---|---|
| `cancel-winning-claim` | A rival claim is pending and this round is its last (round minus claim round = claim window); the seat can duel the claimant | Any duel against the claimant |
| `proclaim-legal` | Phase 2, no claim pending, proclaim available | Proclaim |
| `gain-support-affordable` | Phase 2, a gain-support action is affordable | Any gain-support action |

The fixtures hold public observation data only (a test walks the JSON
and rejects engine hidden state). Each fixture stores the observation,
the candidate shortlist, and the correct action IDs. The runner also
rebuilds the shortlist from the observation and reports drift, so a
rules change that moves the shortlist shows up before the scores do.
Regenerate the fixtures with
`uv run python arena/tests/fixtures/tactical/make_fixtures.py` after an
engine change; it plays seeded bot games and freezes the first
position that meets each situation.

## Baseline

Run 2026-11-18, commit `e076bd2`, series `20261118T115223Z-86e515e7-series`.
12 games (seeds 42-44 x 4 seats), 0 incomplete, 0 skipped, 1616 of
2000 calls, $0.5330 total, 1128 s. Every game ended `survived_window`;
turns ran 124-156 (mean 134), above the 110-turn estimate, and the
input tokens per call ran about 4200 (clef) to 4900 (pplx), below the
6000-token estimate.

| Player | Wins | Wilson 95% | Wins by seat | Missed | Cost | p95 ms | Pos-1 rate |
|---|---|---|---|---|---|---|---|
| `pplx/pplx-decider-v1.3` | 10/12 (0.83) | [0.552, 0.953] | P0:2 P1:3 P2:3 P3:2 | 1 | $0.0395 | 803 | 0.064 |
| `clef/clef` | 2/12 (0.17) | [0.047, 0.448] | P0:1 P1:1 | 1 | $0.4094 | 986 | 0.099 |
| `clef/clef-flash` | 0/12 (0.00) | [0.000, 0.243] | - | 5 | $0.0643 | 2865 | 0.074 |
| `pplx/pplx-decider-flash-v1.3` | 0/12 (0.00) | [0.000, 0.243] | - | 6 | $0.0199 | 427 | 0.059 |

Read of the numbers:

- `pplx-decider-v1.3` beats `clef` with no interval overlap (0.448 <
  0.552) and wins from every seat, so the lead is not a seat artifact.
- Price does not buy wins: `clef` cost $0.41 (77% of the series, at
  $0.24/M input) for 2 wins; `pplx-decider-v1.3` cost $0.04 for 10.
- Both flash models lost every game and account for 11 of the 13
  missed interventions. The missed-intervention gap (1 vs 5-6) tracks
  the win gap, which supports the metric: the losers let winning
  claims survive.
- Position-1 rates sit at 6-10% for every model, close together, so
  the shuffled shortlist order sways no model in a visible way.
- No `--fixtures` score was collected at the baseline; the fixture
  set ran only against local bots (random 2/3, tactical 3/3).
