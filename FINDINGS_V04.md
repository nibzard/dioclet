# FINDINGS_V04.md — OpenAI Decisions player intelligence

Engine revision under test: `feature/v04-openai-decisions` from
`51c30fc`. Rules file for all V0.4 experiments: `rules_v03_base.json`
(hash in each run's `rules.snapshot.json`). Provider model
`gpt-6-luna` via `client.decisions.create` (openai SDK 3.46.0; 2.21.0
does not expose `client.decisions` — recorded as a doc-vs-installed
variance, resolved by upgrading; `requirements-decisions.txt` pins
`openai>=3.46,<4`).

This report separates validated engineering results, actual live
observations (three pilot games and three contract calls), and
experiments that were **not** run.

## Engineering results (offline, validated)

- **Historical behavior unchanged.** All 52 pre-existing tests pass;
  44 new offline tests bring the suite to 96. A fresh 1,000-game
  batch on `rules_v03_base.json` with the published §13 schedule
  produced a **byte-identical `games.csv` and `summary.json`** to
  `results/v03_base` — the V0.4 code did not perturb the engine.
- **Information boundary holds.** A hidden sentinel planted in engine
  state never appears in any provider request or decision log
  (tested). Equipment *names* are a public catalog; only the
  district-to-item mapping is hidden, and only revealed pairs are
  projected.
- **Engine authority holds.** Every applied action comes from the
  engine's `legal_actions`; candidates never invent or rename IDs;
  refusals, wrong answer types, and out-of-set choices raise before
  `apply_action` (stub-tested, never observed live).
- **Budgets and failure handling.** Call, cost, token, and wall-clock
  caps are enforced *before* each request; exhaustion marks the game
  `incomplete` (never a draw, never a silent fallback) with partial
  logs preserved and resumable. One legal action ⇒ no API call.
- **Candidate shortlists.** Across 110 generated observations
  (two scripted games plus crafted states), shortlists stayed within
  2–24 options, always kept winning attacks, seals, explores,
  checkpoint, and every distinct duel target, always kept a
  non-greedy move alternative, and audited every exclusion. Exact
  single-roll odds (duel, seal, Emperor) are d6×d6 enumerations
  labeled `*_exact`; no invented long-horizon probabilities.

## Tactical benchmark (offline, 1,000 games, no API)

`results/v04_tactical_rotate/` — the §13-style rotation with
`tactical` (version `tactical-v04.1`, frozen) as the reference policy
on `rules_v03_base.json`:

| Policy | Seat-games | Win rate |
|---|---:|---:|
| tactical | 2,750 | **31.6%** |
| greedy | 500 | 17.4% |
| aggressive | 500 | 7.8% |
| random | 250 | 2.0% |

Median 14 rounds, 0 draws, 5.71 duels/game (56% attacker wins),
first-challenger win rate 32.9%. Tactical edges out `balanced`
(29.9% on the same base in `results/v03_base`), confirming it is a
competent-but-not-oracle benchmark: it fixes the `aggressive` trap
(winning Emperor attacks outrank duels) and manages the Glory
economy. It did not dominate: 3 of 8 seats in the permutation block
still lost to ordinary bots in aggregate.

## Live API contract checks (3 real calls)

`results/v04_live/contract_checks.json`. Three fixture observations,
one Decisions call each:

| Fixture | Candidates | Chosen kind | Confidence | Latency | Tokens | Est. cost |
|---|---:|---|---:|---:|---:|---:|
| opening turn | 16 | explore | 0.25 | 2,345 ms | 1,126 | $0.000113 |
| mid level 1 | 13 | move | 0.26 | 2,198 ms | 929 | $0.000093 |
| level 2 endgame | 14 | attack_emperor | 0.91 | 262 ms | 1,168 | $0.000117 |

Schema matched the documented response exactly: typed `choice`
answer, `probabilities` as an array of `{value, probability}`,
finite confidence, `usage.input_tokens_details` with
cached/cache-write breakdown. The endgame fixture shows the model
identifying the winning attack with high confidence — and the two
early-position confidences (0.25) are honest: confidence is model
choice uncertainty, **not** win probability.

## Live pilot games (3 games, budget-capped)

All under `--max-decisions-calls 100 --max-cost-usd 0.50` per game.
All finished, all pass offline `replay --verify`, zero refusals,
zero invalid answers, zero fallbacks. Logs: `runs/v04_*`,
`decisions.jsonl` per run.

| Game | Players | Winner | Turns | Calls | Tokens | Est. cost |
|---|---|---|---:|---:|---:|---:|
| 4401 | decisions ×4 | P0 | 77 | 77 | 86,374 | $0.00864 |
| 4402 | decisions, tactical, balanced, greedy | P1 (tactical) | 59 | 15 | ~15k | $0.00166 |
| 4403 | decisions ×2, tactical ×2 | P2 (tactical) | 49 | 24 | ~24k | $0.00274 |

Total live spend (contract checks + pilots): **≈ $0.0135**.

Observed in game 4401 (four Decisions players): 24 explores, 33
moves, 9 seal attempts, 6 Emperor attacks, 4 duels, 1 checkpoint
claim across 77 turns; confidence mean 0.27 (max 0.94); latency p50
171 ms, p95 294 ms (first calls in a fresh process were slower, ~2 s,
suggesting connection setup rather than inference); no probability
validation flags on any of 77 answers. Every seat pursued equipment
in level 1, bought seals, and attacked the Emperor — no erratic or
random play, and no illegal or nonsensical selections.

**These are pilots, not performance estimates.** Three games cannot
rank policies; the two mixed-game wins by `tactical` seats are
anecdotes with n = 1 per configuration.

## Not run (explicitly)

- **Phase C evaluation (32–64 live games)** — not started; requires
  an explicitly approved call/cost budget per the brief. Estimated
  cost if run at observed rates: a 64-game evaluation ≈ 64 × 20
  decisions × ~$0.00011 ≈ **$0.14** and ~25–35 minutes wall clock.
- **Sampling selection mode** — implemented and stub-tested, never
  exercised live (`selection_mode=top` throughout).
- **Prompt caching optimization** — not attempted; per-turn state
  projections differ, so the shared prefix is short and the 1,024
  token cache threshold would rarely help at this input size.
- **`rules_v03_lostturn.json` live follow-up** — untouched; mechanics
  unchanged in V0.4 by design.

## Limitations

- Cost figures are *estimates* from the versioned pricing table
  ($0.10 per 1M uncached input tokens, output unbilled), not a
  billing statement; regional multipliers may apply.
- Live latency and token counts come from three short games on one
  account, one region, one afternoon.
- The mock provider exercises the pipeline, not the model; mock
  games are never counted as model results anywhere in this report.
- `tactical` is frozen at `tactical-v04.1`; any retuning after
  comparisons requires a new recorded version.

## Recommendation

**OpenAI Decisions is practical as an AI-turn policy for this
game.** The typed-choice contract fit cleanly: legality is enforced
by construction, the model saw only public state, answer validation
never rejected a live response, and per-turn cost (~$0.0001, ~0.2 s
median after warm-up) is negligible at pilot scale — even a 64-game
evaluation rounds to about fifteen cents. The open question is not
cost or safety but **strength**: whether `gpt-6-luna` beats
`tactical` (31.6%) over a real sample. Next steps, in order:

1. Approved Phase C: 32 mirror + 32 mixed games with seat rotation,
   Wilson intervals, and the recorded-observation bank for prompt
   comparisons (`selection_mode=top`).
2. A dominated-move audit: replay recorded decisions and count turns
   where a winning attack existed but was not chosen.
3. Only then consider per-seat memory or sampled selection, each as
   its own experiment.
