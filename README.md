# Imperial Rivals: 305 AD

*The Roman Succession. Claim the throne. Survive the challenge.*

A competitive four-player board game set in Diocletian's Palace, Split, in
305 AD. Collect equipment, earn Prestige, secure faction support, and defend
your claim to the throne through a final two-round window. Imperial Rivals is
the series name; 305 AD is the first edition.

This repository contains a deterministic Python simulator, a browser game,
a print-and-play kit, and the experiments that guide the design.

## Current versions

The simulator, print kit, and browser game use different rules:

| Component | Rules | Status |
| --- | --- | --- |
| Python simulator | [V0.10.2 big board](rules_v0102_bigboard.json) | Current design candidate |
| [Print kit](print/) | V0.10.2 big board | Generated PDFs; needs human playtesting |
| [Browser game](web/) | [V0.8 succession](rules_v08_succession.json) | Playable with humans and bots |
| Original simulator | [V0.1 baseline](rules_baseline.json) | Kept for historical experiments and replays |

**V0.10 uses two boards of the same size.** Players collect equipment on
the palace board, then turn the board over and return to their gates on the
succession map. It has the same six blocks and streets. Every gate there is
nine steps from the Peristyle, and four guard posts let players earn Prestige
there too. The three factions hide among six face-down cards, one beside each
block, with three blanks. Players search the
cards, buy support from two factions, and defend a claim at the Peristyle for
two rounds. Six equipment abilities affect play; at most one equipment
modifier applies per duel side.

The browser engine does not yet support the second board. Its V0.8 rules
and rulebook differ from the current print kit. See the
[V0.10 findings](FINDINGS_V10.md) and the
[V0.10 notes](notes/v10-level2-2026-11-14.md) for the evidence and open
questions.

## Play in the browser

The browser game uses plain HTML, CSS, and JavaScript. No build step is required.
From the repository root, start a local server:

```bash
python3 -m http.server 8000 --directory web
```

Open <http://localhost:8000>. Choose human or bot players and use
**How to play** for the V0.8 rulebook.

The board data and rulebook are generated from `rules_v08_succession.json`:

```bash
python3 tools/make_web_board.py
```

This command regenerates the V0.8 browser files. It does not upgrade the
browser to V0.9.4. Cloudflare hosting is configured in
[`wrangler.jsonc`](wrangler.jsonc).

## Print and play

The default edition is the [drawn kit](print/imperial-rivals-305ad-complete-print-kit-A4-ART.pdf).
It carries hand-drawn grayscale artwork (boards, cards, and tokens drawn
programmatically, see `art/`):

- [Palace board, drawn art: four A4 tiles](print/imperial-rivals-305ad-board-4xA4-ART.pdf)
- [Succession map, drawn art: four A4 tiles](print/imperial-rivals-305ad-succession-map-ART.pdf)
- [Cards and tokens, drawn art](print/imperial-rivals-305ad-cards-tokens-ART.pdf)

Both complete kits start with the rulebook, quick reference, teaching guide,
and player sheets. The print instructions come next, right before the pages to
cut: the palace board, the succession map, then the cards and tokens.

The [black-and-white kit](print/bw/imperial-rivals-305ad-complete-print-kit-A4-BW.pdf)
uses black ink only and is the source of the rules documents:

- [Palace board: four A4 tiles](print/bw/imperial-rivals-305ad-board-4xA4-BW.pdf)
- [Succession map: four A4 tiles](print/bw/imperial-rivals-305ad-succession-map-A4-BW.pdf)
- [Player sheets](print/bw/imperial-rivals-305ad-player-sheets-A4-BW.pdf)
- [Cards and tokens](print/bw/imperial-rivals-305ad-cards-tokens-A4-BW.pdf)
- [Rulebook](print/bw/imperial-rivals-305ad-rulebook-A4-BW.pdf)
- [Quick reference](print/bw/imperial-rivals-305ad-quick-reference-A4-BW.pdf)
- [Teaching guide](print/bw/imperial-rivals-305ad-teaching-guide-A4-BW.pdf)
- [Playtest form](print/bw/imperial-rivals-305ad-playtest-form-A4-BW.pdf) (separate file,
  not in the complete kits)
- [Print and assembly instructions](print/bw/imperial-rivals-305ad-print-instructions-A4-BW.pdf)

Each board assembles to 580 × 406 mm from four A4 tiles. The two boards
share their cut lines, so you can tape them back to back. Follow the print
instructions and check the 100 mm calibration ruler.

Both kits print the same geometry: the art consumes a layout exported
from the generator itself (`art/build/layout.json`), never a copy.

To regenerate the kit from `rules_v0102_bigboard.json`, install ReportLab:

```bash
python3 -m pip install reportlab
python3 tools/make_a4_print_kit.py          # black-and-white kit
python3 tools/make_a4_print_kit.py --art    # also the drawn kit
```

The drawn assets are seeded and reproducible. To re-render them after
changing the rules or the drawing code (`@napi-rs/canvas` needs Node 18+):

```bash
python3 art/export_layout.py
cd art && npm ci && node render.mjs && cd ..
python3 tools/make_a4_print_kit.py --art
```

The generator updates the PDFs and [`print/kit-manifest.json`](print/kit-manifest.json).
Use the [current playtest protocol](playtest/protocol-v09.md) to record a human session.

## Run the simulator

Use Python 3.11 or newer. The engine and built-in bots use only the standard library.
Run commands from the repository root.

### Validate, play, and replay a game

Use a new output directory for each game:

```bash
python3 sim.py validate --rules rules_v0102_bigboard.json
python3 sim.py new --rules rules_v0102_bigboard.json --seed 42 \
  --out runs/demo --policies balanced,greedy,aggressive,random
python3 sim.py auto --run runs/demo
python3 sim.py replay --run runs/demo --verify
```

The four policy names map to players `P0`, `P1`, `P2`, and `P3` in that order.
The run directory stores the game state and event log.

### Submit individual actions

After `new`, inspect the active player's observation before you use `auto`:

```bash
python3 sim.py observe --run runs/demo --player P0
```

Use `first_active_player` from the `new` output to select the player.
The observation includes public state and legal actions with stable action identifiers.
Submit the returned `turn_id` and an `action_id` from that observation:

```bash
python3 sim.py act --run runs/demo --player P0 --turn-id 1 \
  --action-id a0001 --note 'open the nearest district'
```

Replace the example values with those from your observation.
`observe` does not change state. An illegal or stale action returns
`legal_action_error` without changing state.

## Run rule experiments

For succession rules, use the evaluator with four strategy profiles:
`collector`, `early_support`, `prestige_farmer`, and `counterleader`.
A 96-game batch covers a full rotation of profiles and gate assignments.

```bash
python3 tools/succession_experiments.py \
  --rules rules_v0102_bigboard.json --games 96 --seed-base 10000 \
  --out results/bigboard-demo
```

Use a new, empty output directory. Read its `report.md` and `summary.json`
for strategy, gate, pacing, and claim measurements. The evaluator also
supports alternative-play audits and bounded live model games.

For the original rules and built-in policy schedule:

```bash
python3 sim.py batch --rules rules_baseline.json --games 1000 \
  --seed-base 1000 --schedule experiment --out results/baseline-demo
python3 sim.py report --input results/baseline-demo
```

These batches produce `games.csv`, `summary.json`, `experiment.json`,
and sample game logs. Compare two batch summaries with:

```bash
python3 compare.py results/baseline-demo results/variant-demo
```

To test a change:

1. Copy the rules file and change one conceptual rule.
2. Validate the copy with `sim.py validate`.
3. Run both versions with matching seeds, profiles, and gate schedules.
4. Compare the results and confirm the finding on fresh seeds.
5. Record the evidence and limitations before you recommend the change.

Keep each rules file and result directory separate. Read
[`programme.md`](programme.md) before using the bounded experiment runner
in [`tools/run_programme.py`](tools/run_programme.py). Simulation results
inform human playtests; they do not establish player enjoyment.

## Optional model players

The OpenAI Decisions provider adds model players. Mock and playback providers
work offline. Live calls require the optional dependency, `OPENAI_API_KEY`,
explicit opt-in, and budget limits.

```bash
python3 -m pip install -r requirements-decisions.txt
```

Try an offline mock game:

```bash
python3 sim.py ai-auto --rules rules_v08_succession.json --seed 4400 \
  --players decisions,decisions,decisions,decisions \
  --provider mock --out runs/mock-demo
```

Provider decisions, latency, token counts, and estimated costs are recorded
in `decisions.jsonl`. Budget exhaustion records an `incomplete.json` file.
Replay verification works offline.

For tournament setup and analysis:

```bash
python3 sim.py tournament --config tournaments/v041_tournament_a.json \
  --out results/tournament-demo --dry-run
python3 analyze_v041.py analyze results/v041
python3 analyze_v041.py report results/v041
```

The dry run estimates calls and cost. The analysis commands use the retained
V0.4.1 tournament logs. See [model player findings](FINDINGS_V04.md),
[tournament findings](FINDINGS_V041.md), and
[`decisions_config.json`](decisions_config.json) for details.
Follow the budget and authorization rules in `programme.md` before paid runs.

## Check changes

The full Python suite includes PDF checks that require ReportLab and pypdf:

```bash
python3 -m pip install reportlab pypdf
python3 -m unittest discover -s tests
```

For browser changes, run the Node.js checks:

```bash
node tools/test_web_engine.mjs
node tools/test_succession_engine.mjs
node tools/test_succession_parity.mjs
node tools/test_web_ui.mjs
```

The user interface check requires `jsdom`; it prints `SKIP` when that package
is unavailable. The browser checks cover the implemented browser rules,
not V0.9.4 twin-board parity.

## Project map

| Path | Purpose |
| --- | --- |
| [`sim.py`](sim.py) | Command-line interface for games, batches, tournaments, and replays |
| [`engine.py`](engine.py), [`succession.py`](succession.py) | Original and succession game engines |
| [`board.py`](board.py) | Board graph, paths, and site lookups |
| [`policies.py`](policies.py), [`tactical_policy.py`](tactical_policy.py) | Built-in bots and deterministic benchmark |
| [`candidate_actions.py`](candidate_actions.py), [`decisions_policy.py`](decisions_policy.py), [`ai_driver.py`](ai_driver.py) | Model observations, providers, and budgeted game driver |
| [`report.py`](report.py), [`compare.py`](compare.py) | Batch statistics and comparisons |
| [`tournament.py`](tournament.py), [`analyze_v041.py`](analyze_v041.py) | Model tournaments and offline analysis |
| [`tools/`](tools/) | Generators, evaluators, experiment runners, and browser checks |
| [`web/`](web/), [`print/`](print/) | Browser game and printable materials |
| [`tests/`](tests/) | Engine, policy, experiment, and print checks |
| [`results/`](results/), [`runs/`](runs/) | Experiment results and retained games |
| [`notes/`](notes/), [`docs/`](docs/) | Research, design plans, and implementation notes |

## Design history and evidence

The findings files preserve measurements for their versions. Their recommendations
can be superseded by later experiments.

| Stage | Evidence |
| --- | --- |
| V0.1: original rules | [Specification](SPEC.md), [baseline findings](FINDINGS.md) |
| V0.2–V0.3: combat and duel consequences | [Combat and fairness](FINDINGS_V02.md), [duel experiments](FINDINGS_V03.md) |
| V0.4–V0.5: model play and rule trials | [Model players](FINDINGS_V04.md), [tournaments](FINDINGS_V041.md), [rule trials](FINDINGS_V05.md) |
| V0.6–V0.7: physical board geometry | [Board validation](BOARD_VALIDATION_V061.md), [playability scorecard](PLAYABILITY_SCORECARD_V061.md), [findings](FINDINGS_V061.md), [board comparison](notes/board-comparison.md) |
| V0.8: imperial succession | [Redesign plan](docs/intervention-plan.md), [succession findings](FINDINGS_V08.md) |
| V0.9–V0.9.3: equipment, claim windows, and movement | [Trial findings](FINDINGS_V09.md), [simplification study](notes/v09-simplification-study.md), [geometry sweep](notes/v09-geometry-sweep-2026-11-13.md) |
| V0.9.4: separate succession map | [Twin-board findings](notes/v094-twinboard-2026-11-13.md), [human playtest protocol](playtest/protocol-v09.md) |
| V0.10: big succession map and faction cards | [Findings](FINDINGS_V10.md), [notes](notes/v10-level2-2026-11-14.md), [Haiku table game](runs/haiku-table-v010/REPORT.md) |

[`DECISIONS.md`](DECISIONS.md) records rule interpretations and design decisions.
Earlier rules files remain available for comparisons and historical replays.
See [`runs/README.md`](runs/README.md) for replay caveats in the oldest logs.
