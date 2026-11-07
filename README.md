# Diocletian's Palace — mechanics simulator V0.1

A headless, deterministic simulator for the four-player, two-level
*Diocletian's Palace: Six Treasures* game. Use it to test rule changes
with repeatable batches before any physical playtesting.

- `SPEC.md` — the implemented specification (V0.1 proposal)
- `rules_baseline.json` — canonical, editable rule set
- `DECISIONS.md` — recorded interpretations of every ambiguous rule
  (D1–D24)
- `FINDINGS.md` — V0.1 baseline experiment (1,000 games)
- `FINDINGS_V02.md` — combat and fairness experiments
- `FINDINGS_V03.md` — duel consequence experiments
- `FINDINGS_V04.md` — OpenAI Decisions player intelligence
- `FINDINGS_V041.md` — AI tournament and decision analysis
- `notes/v05-experiment-plan.md` — V0.5 experiment plan (three rule
  experiments under Decisions play; live runs pending authorization)

## Where the design stands

Measured on 1,000-game batches with the same seeds and policy
rotation (baseline → adopted package → candidate):

- **Adopted for V0.3** (`rules_v03_base.json`): attacker wins duel
  ties, one grace round, rotating first player. Aggressive seats 11%,
  comebacks 70%, challenger edge down to 30%, median 14 rounds.
- **Candidate from V0.3**: the duel lost turn
  (`rules_v03_lostturn.json`) — aggressive 14%, no timeouts, one
  round longer.
- **Rejected so far**: Glory cap 3 (more fights, no strategy shift),
  Glory theft (zero-sum economy crowns the pacifist: aggressive 0%,
  greedy 36%), retreat-node displacement (drops victims on the
  chamber doorstep; falsified by playtest `runs/narr8`).
- **Open questions**: the residual turn-order gap (28/21), `balanced`
  dominance (~30%), and displacement geometry (try the loser's own
  gate next).

## Install and test

Python 3.11 or newer. Standard library only.

```bash
python3 -m unittest discover -s tests    # 43 engine and policy tests
```

## Play one game turn by turn

```bash
python3 sim.py validate --rules rules_baseline.json
python3 sim.py new --rules rules_baseline.json --seed 42 --out runs/demo \
  --policies balanced,greedy,aggressive,random
python3 sim.py observe --run runs/demo --player P1
python3 sim.py act --run runs/demo --player P1 --turn-id 1 --action-id a0001 \
  --note 'open the nearest district'
python3 sim.py auto --run runs/demo        # finish with built-in policies
python3 sim.py replay --run runs/demo --verify
```

`observe` prints the public observation: the active player's die, all
pawns, public Glory, equipment, seals and hits, revealed districts, and
every legal action with a stable `action_id`. `observe` never changes
game state. Submitting an illegal or stale `action_id` prints
`legal_action_error` on stderr and exits nonzero without mutating
anything.

## Run experiments

```bash
# 1,000 games with the SPEC §13 policy rotation (four blocks of 250)
python3 sim.py batch --rules rules_baseline.json --games 1000 \
  --seed-base 1000 --schedule experiment --out results/v01_baseline

# or a fixed seat assignment for every game
python3 sim.py batch --rules rules_baseline.json --games 100 \
  --seed-base 500 --policies random,greedy,aggressive,balanced --out results/mix

python3 sim.py report --input results/v01_baseline
```

Each batch directory contains `games.csv` (one row per game),
`summary.json` (aggregate statistics with Wilson 95% intervals),
`experiment.json` (seeds, policies, engine version), and
`sample_games/` with full logs for the first five seeds plus every
anomalous game (draw or over 150 turns). Full logs for all games are
off (`logging.save_full_batch_logs` in the rules JSON).

## Compare a rule change

1. Copy `rules_baseline.json` to `rules_<name>.json` and change one
   conceptual knob.
2. `python3 sim.py validate --rules rules_<name>.json`
3. Re-run the batch with the same `--seed-base` and
   `--schedule experiment`.
4. Compare `summary.json` files; the seeds and seat schedules match,
   so differences come from the rule change.
5. `python3 compare.py results/v01_baseline results/<name>` prints a
   side-by-side markdown table.

Existing variants (reports in `FINDINGS.md`, `FINDINGS_V02.md`, and
`FINDINGS_V03.md`):

- V0.2 Combat and Fairness (`rules_v02_*.json`): attacker-wins-ties,
  Glory cap 3, three Emperor hits, rotating first player, grace 0/1,
  and the ties+rotation combo.
- V0.3 duel consequences (`rules_v03_*.json`), on top of the adopted
  V0.2 package: duel Glory theft, duel displacement to the retreat
  node, and the duel lost turn.
- V0.5 proposals (`rules_v05_*.json`), each one knob on the V0.3 base:
  Peristyle seal cost 2 Glory, Level 1 capped at 16 rounds.

Optional rule keys absent from the baseline:
`turns.rotate_first_player_each_round`, `combat.duel_glory_theft`,
`combat.duel_displacement`, `combat.duel_lost_turn`.

Never edit `rules_baseline.json` mid-experiment; each variant gets its
own file and results directory.

## AI-turn policies (V0.4, optional)

An observation-only OpenAI Decisions player, a deterministic
`tactical` benchmark bot, and mock/playback providers for offline
work. The `openai` package is optional; live calls require
`OPENAI_API_KEY` and an explicit budget:

```bash
pip install -r requirements-decisions.txt

# Offline mock game (no network, no key)
python3 sim.py ai-auto --rules rules_v03_base.json --seed 4400 \
  --players decisions,decisions,decisions,decisions \
  --provider mock --out runs/v04_mock_4400

# Mixed policies: one Decisions seat vs local bots
python3 sim.py ai-auto --rules rules_v03_base.json --seed 4402 \
  --players decisions,tactical,balanced,greedy \
  --provider live --live-decisions \
  --max-decisions-calls 100 --max-cost-usd 0.50 --out runs/v04_mix_4402

# Offline replay never contacts the API
python3 sim.py replay --run runs/v04_mix_4402 --verify
```

Provider decisions, probabilities, confidence, latency, tokens, and
estimated costs are logged to `decisions.jsonl` in the run directory.
Budget exhaustion stops the game cleanly as `incomplete.json`.
Details and measured results: `FINDINGS_V04.md`; configuration:
`decisions_config.json`.

## AI tournaments and offline analysis (V0.4.1)

Tournament configs live in `tournaments/`; all outputs go to
`results/v041/` (never overwriting earlier results).

```bash
# Estimate cost and call count before spending anything
python3 sim.py tournament --config tournaments/v041_tournament_a.json \
  --out results/v041 --dry-run

# Live (requires OPENAI_API_KEY, explicit opt-in, budget caps)
python3 sim.py tournament --config tournaments/v041_tournament_a.json \
  --out results/v041 --live-decisions --resume

# Offline analysis of any completed tournament
python3 analyze_v041.py analyze results/v041   # decision scorecard
python3 analyze_v041.py report  results/v041   # strength, cost, CIs
```

Resume re-runs only games without a `result.json`; per-game and
aggregate cost caps stop the run gracefully (the driver receives
whichever cap is tighter and checks it before every call); completed
games are never silently re-played or substituted. Measured outcomes
of the 64-game V0.4.1 tournament: `FINDINGS_V041.md` and the
qualitative game studies in `notes/v041/`. The repository keeps the
six games cited in the findings under `results/v041/games/`; the
complete 64-game log set ships as the release artifact
`v041-tournament-logs` (2.5 MB, offline re-analyzable with
`analyze_v041.py`).

## V0.5 experiments (in preparation)

Three rule experiments, each with a bot baseline and a live AI
tournament: the duel lost turn, Peristyle seal cost 2, and Level 1
capped at 16 rounds. Plan and predictions:
`notes/v05-experiment-plan.md`. Bot baselines are done
(`results/v05_peristyle2_bots`, `results/v05_l1max16_bots`; the
lost-turn baseline is `results/v03_lostturn`). Live tournaments are
configured but not run — they start only with an authorized budget:

```bash
python3 sim.py tournament --config tournaments/v05_exp1_lostturn_ai.json \
  --out results/v05_exp1 --dry-run      # estimate first
python3 sim.py tournament --config tournaments/v05_exp1_lostturn_ai.json \
  --out results/v05_exp1 --live-decisions
```

## Modules

- `sim.py` — CLI entry point
- `engine.py` — state machine, legal actions, resolution, events
- `board.py` — grid graph, deterministic shortest paths, site lookups
- `policies.py` — `random`, `greedy`, `aggressive`, `balanced` bots
- `tactical_policy.py` — frozen deterministic benchmark bot (V0.4)
- `candidate_actions.py` — public observation projection and
  candidate shortlists (V0.4)
- `decisions_policy.py` — mock/playback/live OpenAI Decisions
  providers (V0.4, optional `openai` package)
- `ai_driver.py` — single-writer AI game driver with budgets
- `report.py` — batch runner, CSV, summary statistics
- `compare.py` — side-by-side markdown table across batch summaries
- `tournament.py` — reproducible AI tournament runner (V0.4.1)
- `analyze_v041.py` — offline decision scorecards and tournament
  reports (V0.4.1)
- `decisions_config.json`, `requirements-decisions.txt` — V0.4 config
  and optional dependency pin
- `tests/` — engine invariants, resolution tests, policy unit tests,
  bounded exhaustive checks, V0.4 offline provider and driver tests
