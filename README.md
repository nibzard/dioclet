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
- `FINDINGS_V05.md` — rule experiments under Decisions play
- `notes/v05-experiment-plan.md` — V0.5 experiment plan with
  predictions and outcome lines
- `FINDINGS_V08.md` — succession fee experiments, proposal agents,
  and live Decisions validation

## Where the design stands

Measured on 1,000-game batches with the same seeds and policy
rotation (baseline → adopted package → candidate):

- **Adopted for V0.3** (`rules_v03_base.json`): attacker wins duel
  ties, one grace round, rotating first player. Aggressive seats 11%,
  comebacks 70%, challenger edge down to 30%, median 14 rounds.
- **Candidate from V0.3**: the duel lost turn
  (`rules_v03_lostturn.json`) — aggressive 14% under bots, but the
  V0.5 AI test showed it does not redirect aggression at leaders and
  raises auto-grants 32% (see `FINDINGS_V05.md`); do not adopt.
- **Adopted for V0.5** (`rules_v05_l1max16.json`): Level 1 capped at
  16 rounds as guardrail insurance — binds only the worst stalls
  (about 6% of AI games), every observed median untouched.
- **Rejected so far**: Glory cap 3 (more fights, no strategy shift),
  Glory theft (zero-sum economy crowns the pacifist: aggressive 0%,
  greedy 36%), retreat-node displacement (drops victims on the
  chamber doorstep; falsified by playtest `runs/narr8`), Peristyle
  seal cost 2 (locks Glory-poor seats out of the guaranteed buy;
  no new deliberation), duel lost turn (see the candidate note).
- **Open questions**: the residual turn-order gap (28/21), `balanced`
  dominance (~30%), and displacement geometry (try the loser's own
  gate next).

## Install and test

Python 3.11 or newer. Standard library only.

```bash
python3 -m unittest discover -s tests    # engine, policy, board, and harness tests
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
- V0.5 (`rules_v05_*.json`), each one knob on the V0.3 base:
  Peristyle seal cost 2 Glory (rejected), Level 1 capped at 16
  rounds (adopted as a guardrail).

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

## V0.6.1: real board validation (print-and-play ready)

The designer's physical board is encoded, 2d6
movement is measured in, and a print-and-play pack exists:
`playtest/playtest-pack.html` (board, cards, tokens, rulebook, quick
reference, teaching script, feedback form) plus
`playtest/protocol.md` for human sessions. Validation, fairness
probes, pacing, and the Level 1 cap analysis: `FINDINGS_V061.md`,
`BOARD_VALIDATION_V061.md`, `PLAYABILITY_SCORECARD_V061.md`. The
live AI confirmation is configured but awaits spending
authorization. V0.6.2 fixed the pack after review: unescaped print
CSS, 7 mm pawns with a landscape board page, four equipment tracker
sheets, an explicit move-first rule for guard posts and duels, and
real policy dispatch in `tools/mirror_batch.py`.

## V0.7: the six-block board

Designer correction (2026-11-07): the point of the layout is six
blocks with one card each. The V0.6 encoding had added a central
north-south street (D27) that split the middle column into four
strips, so the simulated board carried eight blocks and two cards
without a block of their own. `rules_v07_6blocks.json` removes that
street: 97 street spaces, six 5x5 blocks, entries B and E moved to
the north and south streets in front of the middle blocks, the
retreat hall one step east of the Emperor. Everything else carries
over unchanged. Measured against the V0.6 board: fewer city timeouts
(129 versus 162 per 1000 games), same collection and comeback rates,
and even gates under both the balanced-se mirror and first-challenger
probe (`DECISIONS.md` D33, `notes/board-comparison.md`).

## V0.7.3: six intact blocks and aligned gates

The active board is `rules_v073_sixblocks_cardo.json`. It keeps six
solid 5x5 blocks and 97 street spaces. The cardo follows the existing
western street, column 6. The decumanus follows row 6. The north and
south gates both end the cardo; the east and west gates end the
decumanus. The checkpoint marks their crossing.

V0.7.2 added column 9 through the two middle blocks. That creates
eight physical blocks, even when metadata calls them six buildings.
It is rejected for the active layout and retained for old replays.
The generators now check physical connected blocks, complete
footprints, distinct card ownership, and the four street endpoints.

The cardo is off-center to preserve six equal blocks without adding
a street. Gate-to-checkpoint distances are north 6, east 12, south 6,
and west 6. Random gate assignment can share the chance of each
position; it does not prove equal strength. This layout needs new
balance measurements.

The full gameplay redesign is specified in
[`docs/intervention-plan.md`](docs/intervention-plan.md). It covers
persistent equipment, faction support, Prestige, random gate
assignment, and a contested claim to imperial power.

## V0.8: imperial succession

The active prototype is `rules_v08_succession.json`
(`gameplay_mode: "succession-v1"`). It keeps the V0.7.3 six-block
board and replaces the palace boss fight with a contested claim:

- Players get names and colors; gates are assigned separately
  (seeded random, manual, or a four-game rotation).
- Equipment persists through the whole game. There are no free
  grants at transition, and collection stays legal in succession.
- Glory is renamed Prestige and has spending options.
- Seals are replaced by faction support: visit a meeting place and
  spend one Prestige. Support from two of three factions qualifies a
  claim.
- The endgame is a claim at the Peristyle that every rival answers.
  Challenging an active claimant costs 1 Prestige, paid before the
  roll and separate from the optional +2 boost. A winning challenge
  cancels the claim and returns the claimant to the assigned gate. A
  claim that survives all three responses wins. Fee 0 lost to a
  free-denial loop and fee 2 removed live counterplay; see
  `FINDINGS_V08.md`.

Legacy `seals` and `hits` state is never reinterpreted; the legacy
engine still replays old rules files. The succession engine lives in
`succession.py` (Python) and `web/succession-engine.js` (browser);
`web/succession-bots.js` supplies the public-information bot
policies. Offline strategy evaluation, gate permutation audits, and
alternative-play audits: `tools/succession_experiments.py`
(`evaluate_rules`). The bounded autoresearch runner over
`experiments/v08-programme.json` is `tools/run_programme.py`
(sequential tool-free Claude proposal agents; scripted smoke mode
needs no model call). Human playtest protocol:
`playtest/protocol-v08.md`. Experiment instructions and evidence
rules: `programme.md`.

## Play it in the browser

A playable web version lives in `web/`: plain HTML, CSS, and
JavaScript, no build step. Hot-seat humans and the bot policies play
the V0.8 succession rules on the six-block, 97-space board. The full
rulebook ships with the site behind the **How to play** button. The
board definition is generated from `rules_v08_succession.json`
(`python3 tools/make_web_board.py`), never hand-copied; pass
`--rules` for legacy artifacts. Tests: `node
tools/test_web_engine.mjs` (legacy engine), `node
tools/test_succession_engine.mjs` (succession behavior), `node
tools/test_succession_parity.mjs` (Python/JavaScript action parity),
and `node tools/test_web_ui.mjs` (jsdom UI test; prints SKIP without
jsdom installed). Deployed to Cloudflare via `npx wrangler deploy`
(see `wrangler.jsonc`).

## Print and play (V0.8.1 kit)

A black-and-white A4 print-and-play kit lives in `print/`. One command
regenerates every PDF from `rules_v08_succession.json`:

```bash
python3 tools/make_a4_print_kit.py
```

The kit contains the four-tile board (580 × 406 mm assembled,
butt-join with dashed cut lines), player sheets, cards and tokens, a
six-page family rulebook, a quick reference, a teaching guide, a
playtest form, and print instructions with a 100 mm calibration
ruler. `print/kit-manifest.json` records every drawn position. The
generator stops if the rules JSON drifts from the numbers printed in
the prose. Tests: `tests/test_print_kit_v081.py`.

## V0.5 experiments (run)

Three rule experiments, each with a bot baseline and a live AI
tournament: the duel lost turn, Peristyle seal cost 2, and Level 1
capped at 16 rounds. Measured outcomes: `FINDINGS_V05.md` (96 games,
$0.2214 of a $5.00 authorized cap, all games replay-verified).
Repository copies hold each tournament's aggregates
(`results/v05_exp*/`); the full 96-game log set ships as the release
artifact `v05-tournament-logs`.

## Modules

- `sim.py` — CLI entry point
- `engine.py` — state machine, legal actions, resolution, events
  (dispatches `gameplay_mode: "succession-v1"` to `succession.py`)
- `succession.py` — V0.8 succession mode: state, claims, support,
  invariants, and strategy probes
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
- `tools/succession_experiments.py` — V0.8 offline evaluation,
  gate-permutation and alternative-play audits, bounded live games
- `tools/run_programme.py` — bounded sequential proposal-agent runner
  over `experiments/v08-programme.json` (V0.8)
- `decisions_config.json`, `requirements-decisions.txt` — V0.4 config
  and optional dependency pin
- `tests/` — engine invariants, resolution tests, policy unit tests,
  bounded exhaustive checks, V0.4 offline provider and driver tests
