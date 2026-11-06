# Diocletian's Palace — mechanics simulator V0.1

A headless, deterministic simulator for the four-player, two-level
*Diocletian's Palace: Six Treasures* game. Use it to test rule changes
with repeatable batches before any physical playtesting.

- `SPEC.md` — the implemented specification (V0.1 proposal)
- `rules_baseline.json` — canonical, editable rule set
- `DECISIONS.md` — recorded interpretations of every ambiguous rule
- `FINDINGS.md` — results of the 1,000-game baseline experiment

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

Existing variants (V0.2 Combat and Fairness set, reports in
`FINDINGS.md` and `FINDINGS_V02.md`): attacker-wins-ties, Glory cap 3,
three Emperor hits, rotating first player, grace 0/1, and the
ties+rotation combo (`rules_v02_*.json`). Optional rule keys absent
from the baseline: `turns.rotate_first_player_each_round`.

Never edit `rules_baseline.json` mid-experiment; each variant gets its
own file and results directory.

## Modules

- `sim.py` — CLI entry point
- `engine.py` — state machine, legal actions, resolution, events
- `board.py` — grid graph, deterministic shortest paths, site lookups
- `policies.py` — `random`, `greedy`, `aggressive`, `balanced` bots
- `report.py` — batch runner, CSV, summary statistics
- `tests/` — engine invariants, resolution tests, policy unit tests,
  bounded exhaustive checks
