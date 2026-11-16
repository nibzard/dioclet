# FINDINGS_ARENA.md — Arena series runner and play-quality measurement

Phase 4 of [`docs/model-context-plan.md`](../model-context-plan.md):
the series runner (`arena --series`), the metrics in `summary.json`,
and the tactical fixture check (`arena --fixtures`). This file records
the methodology and the metric definitions. The coordinator runs the
baseline and fills in the results section at the end.

## Methodology

### Series design

One series plays `seeds x 4` games under one budget. The shipped
baseline is [`arena/matches/series-four-way.json`](../../arena/matches/series-four-way.json):

| Element | Value | Why |
|---|---|---|
| Players | `clef/clef-flash`, `pplx/pplx-decider-v1.3`, `gateway/nace-ai/drex-v2.0`, `gateway/baseten/elephant-1` | Two cheap dedicated decision models and two gateway models on the free tier |
| Seeds | 42-46 (5 seeds) | Each seed gives 4 games, one per seat |
| Budget | 2200 calls, $1.00 | ~110 turns x 20 games, per the plan |
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

## Baseline (to be run)

Not run yet. The coordinator runs:

```bash
cd arena
uv run --extra decisions arena --yes --series matches/series-four-way.json
```

and copies the printed scoreboard and `summary.json` here. Fill in:

- Per-player win rates with the Wilson intervals, seat split, and cost.
- Missed interventions per player, next to the `cancel-winning-claim`
  fixture score.
- Position-1 rates, to judge how much the candidate order sways each
  model.
- Any games the call cap skipped, with the measured turns per game.
