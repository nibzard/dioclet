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

## Modules

- `sim.py` — CLI entry point
- `engine.py` — state machine, legal actions, resolution, events
- `board.py` — grid graph, deterministic shortest paths, site lookups
- `policies.py` — `random`, `greedy`, `aggressive`, `balanced` bots
- `report.py` — batch runner, CSV, summary statistics
- `tests/` — engine invariants, resolution tests, policy unit tests,
  bounded exhaustive checks
