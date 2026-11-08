# Agent handover: finish V0.8 and the experiment programme

Date: 2026-11-08.
Workspace: `/home/agent/dioclet`.
Live site: https://dioclet-board.nikola-balic.workers.dev

Use this document as the continuation prompt when the user assigns you this work. The original goal is paused for this handover. Saving this document does not resume it.

## Your task

Finish the V0.8 imperial-succession prototype, validate it, run bounded strategy experiments, and publish the tested prototype. Build the missing runner for sequential unattended Claude agents.

The user's objective is great game mechanics: consequential choices, viable competing strategies, alternative plays, and reasons humans would want another game. Finishing games and maximizing one bot's win rate are insufficient.

The user explicitly authorizes the existing OpenAI Decisions harness for realistic play exercises. They also request sequential noninteractive Claude agents for a hill-climbing or autoresearch-style cycle. Keep offline simulations, live model play, and human feedback distinct.

Read these first:

1. `docs/intervention-plan.md` — full design and implementation plan.
2. `programme.md` — draft instructions for the experiment agents.
3. `experiments/v08-programme.json` — cycle limits, permitted rule changes, and promotion checks.
4. `notes/treasure-incentives.md` and `notes/faction-support.md` — reasoning and historical sources.
5. The current diff and the new engine, evaluator, and browser files listed below.

Follow the applicable `AGENTS.md` instructions. Use `python3`. Never delete Codex or Claude session data. Record qualifying tool/setup problems with `papercut add` without blocking the task.

## Repository and deployment state

The working tree contains many uncommitted changes from this conversation. Preserve them. Do not reset, clean, overwrite, or revert files because they differ from Git HEAD.

Git HEAD was `21af4dc` when implementation began. Earlier commits include the rejected eight-block map. Inspect the current state instead of assuming HEAD is the intended design.

The unrelated untracked directories `results/v05_exp1/games/`, `results/v05_exp2/games/`, and `results/v05_exp3/games/` existed before this work. Leave them alone.

The live site runs V0.7.3 with the six-block board and phase-specific palace markers. The last deployment in this session was `32b509c4-1797-4dca-9438-26a62b556f60`.

V0.8 exists locally and is not deployed. No live Decisions requests or `claude -p` experiment cycles have run. No implementation commits have been made.

A local Python preview server may still be running on port 4193. Check it before starting another server. Do not stop unrelated processes.

## Fixed board requirements

Keep `rules_v073_sixblocks_cardo.json` as the corrected legacy board and the geometry source for V0.8.

- Grid: 19 columns by 13 rows.
- Exactly six connected solid blocks, each 5×5.
- Exactly 150 blocked cells and 97 street cells.
- Streets: perimeter, columns 6 and 12, and row 6.
- Cardo: column 6, north–south.
- Decumanus: row 6, east–west.
- Secondary vertical street: column 12.
- Gates: P0 `(6,0)`, P1 `(18,6)`, P2 `(6,12)`, P3 `(0,6)`.
- Checkpoint and Peristyle: `(6,6)`.
- District entries A/B/C: `(3,0)`, `(9,0)`, `(15,0)`.
- District entries D/E/F: `(3,12)`, `(9,12)`, `(15,12)`.
- Every building explicitly names its district.

`board.validate_six_block_layout()` checks physical connected blocks, footprints, entries, street orientation, and gate endpoints. Both generators call it. V0.7.2 fails this contract because its added column 9 creates eight physical blocks. Do not disguise that problem with six building labels.

The cardo is intentionally off-center to preserve the six equal blocks. Gate-to-crossing distances are 6/12/6/6. Random gate assignment shares access to positions across games; it does not establish equal gate strength.

## Implemented engine work

Python files:

- `succession.py` — new mode, state, legal actions, resolution, observations, results, invariants, and strategy probes.
- `engine.py` — dispatch for `gameplay_mode: "succession-v1"`; legacy behavior remains separate.
- `policies.py` — succession policy dispatch.
- `tests/test_succession.py` — 25 dedicated tests at handover.

Browser and Node files:

- `web/succession-engine.js` — overrides `DIOCLET_ENGINE` only when `DIOCLET_BOARD.mode` is `succession-v1`.
- `web/succession-bots.js` — overrides bot dispatch for that mode.
- `tools/test_succession_engine.mjs` — behavioral tests and complete bot games.
- `tools/test_succession_parity.mjs` — complete Python/JavaScript action-sequence comparisons.

The new rules file is `rules_v08_succession.json`. Its starting values include:

- Prestige cap three.
- Persistent equipment; no free grants; collection in both phases.
- Support from two of three factions.
- Support cost one; support available during both phases.
- Army at district F, officials at the Peristyle, city elites at district A.
- Position preservation at phase transition.
- Seeded random gate assignments, plus manual assignment and rotation.
- One optional Prestige payment for +2 on an attacking duel roll.
- A pending claim survives one completed response from each rival to win.
- A successful challenge cancels a claim and returns its owner to their assigned gate.
- Equipment and support survive canceled claims.
- Explicit optional `succession.contest_cost` for opposing an active claimant.

IMPORTANT: the active V0.8 JSON still starts with `contest_cost: 0`. That is the initial comparison baseline, not the recommended final choice. The first tests found serious repeated denial. See the evidence below before selecting a release candidate.

New player state uses `prestige` and `support`. Do not reinterpret legacy `seals` and `hits` silently. Python results supply explicit legacy CSV compatibility columns as well as the actual succession metrics.

Python pending claims use `player`, `claim_id`, and `responded`. JavaScript also supplies UI aliases `claimant` and `id`. Gate identity is distinct from player identity. JavaScript player fields include `gateId`, `index`, `prestige`, `support`, and `equipment`.

Both new engines use independent xorshift32 streams for gates, order, equipment, movement, and combat. Full-game parity already checks actual legal actions and resulting state, not just winners.

## Implemented interface and teaching work

`web/app.js`, `web/index.html`, and `web/style.css` are partly integrated with V0.8:

- Players have names such as Player 1, not a fixed gate direction.
- Random/manual/rotation controls show a gate preview before starting.
- Cards show Prestige and named faction support.
- Faction badges replace the old palace trials in succession mode.
- Claim status and action descriptions support the new actions.
- A treasure click collects automatically only when no competing action exists.
- Actual choices appear in an accessible modal.
- Pawn positions synchronize after off-turn displacement.
- Square corners and even borders remain. Do not restore rounded cards or colored accents on one border edge.

The browser loads the new engine and bots after the legacy scripts. An earlier UI bug passed `gateOrder` for every setup mode, which disabled randomization. This was fixed: `gateOrder` is supplied only for manual assignment. Verify it again in the final UI tests.

A browser smoke check successfully opened the V0.8 setup, displayed seeded random gate previews, and started a game without console errors. This is not a complete V0.8 interface verification.

`tools/succession_content.py` provides shared browser and print rules. `tools/make_web_board.py` now defaults to V0.8 and generates both `board-data.js` and `rules.js`. It emits the economy/combat configuration needed by the JavaScript engine. `tools/make_print_pack.py` defaults to V0.8 and supports `--rules` for legacy artifacts.

The new printable pack is generated. Legacy print tests explicitly select the V0.7.3 rules to preserve their original checks.

## Important unfinished integration work

1. `tools/test_web_ui.mjs` still contains the older UI test flow and script-loading list. It does not load the new succession scripts. Update or separate the harness before treating it as a V0.8 check. Cover the new state and victory conditions.
2. Finish browser and print regression checks. Validate random/manual/rotation assignments, support choices, persistent equipment, claims, response turns, cancellation, replay, and bot-only completion.
3. The shared player rules need to describe a mandatory contest fee if the selected candidate uses one. They currently explain the optional roll boost but do not yet fully explain that additional fee.
4. Review remaining legacy references and hardcoded assumptions in current UI, teaching text, reports, and prompts. Keep historical artifacts intact.
5. Finish a V0.8 human playtest protocol and update README, decision notes, and plan status to reflect actual implementation and findings.
6. The full suite must run after all final integration edits. Do not report earlier partial-suite results as a final pass.

The existing browser engine test loads the legacy engine. Use the dedicated succession test and parity test for the new mode.

## Experiment harness work

Implemented files:

- `candidate_actions.py` — public succession projection, diverse candidates, and mandatory claim/support/response options.
- `decisions_policy.py` — correct succession objective and public candidate evidence for the existing provider.
- `ai_driver.py` — shared budget support and succession tactical dispatch.
- `tools/succession_experiments.py` — offline strategy evaluation, gate permutations, alternative-play audits, and bounded live games.
- `tests/test_succession_decisions.py` — new harness checks.

Stable evaluator API:

```python
from tools.succession_experiments import evaluate_rules

summary = evaluate_rules(
    rules_path,
    out,
    games=96,
    seed_base=20000,
    split="screen",
    profiles=("collector", "early_support", "prestige_farmer", "counterleader"),
    audit_positions=2,
    rollouts=4,
    audit_turns=200,
    economy_grid=False,
    provider="mock",
)
```

The mock provider here is explicitly labeled offline bots. Do not describe it as live model play.

The evaluator writes `summary.json`, `report.md`, `alternatives.jsonl`, and variant directories. Each variant contains rules, games, public choices, and complete run logs. It rejects nonempty output directories.

Read `summary["variants"]["base"]` for totals. Fields include `draw_fraction`, `wins_by_strategy`, `wins_by_gate`, uncertainty intervals, `median_rounds`, `choice_rich_turns`, `avoidable_treasure_walks`, and `resource_and_claim_totals`.

Counterplay fields include `counterclaim_attempts`, `challenged_claims`, and `challenged_claim_fraction`. These track attempted challenges, not just successful cancellations.

Alternative-play audits resample hidden worlds compatible with public evidence and compare actions using paired future streams and varied opponent policies. The model never sees simulator secrets. The estimates are small, policy-dependent rollouts; do not present them as exact action values.

## Initial evidence

The JavaScript agent compared the same fixed seeds and policy mixture:

| Mandatory contest cost | Wins | Draws | Claims | Cancellations | Total turns | Collection actions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 18 | 22 | 1,076 | 1,045 | 5,792 | 889 |
| 1 | 40 | 0 | 194 | 154 | 3,624 | 887 |

This is evidence that the free-challenge prototype has a denial loop. Cost one is a promising candidate. It is not proof of balanced gates or human enjoyment.

The mandatory fee applies to every duel against an active claimant, including the unboosted variant. It cannot be bypassed through an ordinary free duel. An optional boost costs extra. Costs are paid before rolling; a winner still receives the normal duel reward. That reward is separate from the fee.

A four-game Python evaluator smoke run also found three draws and 130 canceled claims. It is only a diagnostic. Its temporary output was `/tmp/dioclet-evaluator-smoke`; verify whether it still exists.

Verified before the pause:

- 25 dedicated Python succession tests passed.
- The full Python suite passed earlier, before the last added tests and remaining integration changes.
- Dedicated JavaScript behavioral checks and 80 games passed.
- Python and JavaScript matched through 12 complete scenarios and 781 turns, including fees, caps, rotation, actions, and RNG states.

## Build the missing sequential runner

`tools/run_programme.py` DOES NOT EXIST YET. `programme.md` documents the intended command, not a working runner.

Implement the runner around these constraints:

- Read `experiments/v08-programme.json`.
- Default to three sequential fresh Claude proposal agents.
- Provide the programme, incumbent rules, previous results, public turn examples, and a strict proposal schema in each prompt.
- Ask for one rule path/value, a causal hypothesis, a prediction, and evidence that would refute it.
- Use tool-free proposal agents: Claude proposes data; the trusted runner edits a copied candidate and runs tests.
- Permit only the finite rule paths and values in the configuration.
- Freeze engine, evaluator, policy, test, and board hashes for the entire comparison run. Stop if they change.
- Write immutable cycle artifacts. Never mutate the active rules or deploy from inside a cycle.
- Run paired screening suites and fresh holdout suites. Rotate gate and policy assignments independently.
- Apply the configured promotion checks. Keep the incumbent if a candidate fails, conflicts with counterplay, or lacks enough evidence.
- Record every rejection and stop reason. Never fabricate model output or silently replace a failed model call with a scripted proposal.
- Support a clearly labeled scripted smoke mode that uses no model calls.
- Bound subprocess duration and cost. Stop on timeout, invalid output, authentication failure, exhausted budget, or invalid rules.

The fixed checks are guardrails for mechanical health, not a fun score. Inspect strategic tradeoffs and alternative plays before choosing a release candidate.

Claude is installed at `/home/agent/.local/bin/claude`. `claude --help` confirms `-p`, `--tools`, `--output-format json`, `--json-schema`, and `--max-budget-usd`.

The `yolo` alias is in `~/.bash_aliases` and expands to `claude --dangerously-skip-permissions`. It is not loaded in noninteractive Bash. The tool-free proposal runner does not require it.

Suggested invocation once the runner exists:

```bash
python3 tools/run_programme.py --cycles 3 --games 96 \
  --out results/v08-programme-001
```

Use new output directories for retries. Do not overwrite a partial run to hide an error.

## Live Decisions exercise

Official documentation was checked on 2026-11-08:
https://developers.openai.com/api/docs/guides/decisions

Keep `gpt-6-luna` and the existing `client.decisions.create` provider. The endpoint returns typed choices and probabilities, not freeform explanations. Do not invent a model rationale.

Session operational limits for the first exercise:

- Total estimated Decisions cost: $0.75 across all games and cycles.
- Total requests: 1,200.
- Use one persistent budget ledger across restarts.
- Claude proposal agents: at most $0.50 each and 180 seconds each; at most three cycles.

These are conservative session limits chosen for the first exercise. Do not increase them without a new user instruction. No live calls have consumed this exercise budget yet.

The new ledger reserves costs before sending, charges failures/refusals, disables retries, and records successful input usage. Review the accounting before running. The agent noted that cache-write or regional pricing can differ from the simple uncached input rate. Decide how to keep the ledger conservative; do not call it an account billing guarantee.

A bounded live command has this form:

```bash
python3 tools/succession_experiments.py \
  --rules PATH_TO_VALIDATED_CANDIDATE.json \
  --out results/v08-live-001 \
  --provider live --live-decisions --live-seats 4 \
  --games 4 --seed-base 130000 \
  --max-cost-usd 0.75 --max-decisions-calls 1200 \
  --budget-ledger results/v08-live-budget.json
```

Verify current arguments first. Preserve incomplete games as incomplete. Never turn API failure or budget exhaustion into a reported draw or completed bot game. Do not print credentials. The optional OpenAI SDK may require the repository's existing environment; inspect it without exposing secrets.

## Suggested continuation order

1. Inspect the diff, finish the remaining UI/print/harness integration, and run correctness checks.
2. Implement and smoke-test the bounded programme runner without model spending.
3. Run paired screening and fresh holdout tests, starting with contest cost zero versus one.
4. Run up to three actual Claude proposal cycles and the bounded live Decisions exercise.
5. Review strategy diversity, counterplay, resource incentives, gate results, and alternative turns. Select and record a provisional candidate.
6. Regenerate matching browser and print artifacts, verify the final UI, and deploy the selected V0.8 prototype.
7. Document findings, rejected variants, actual spending, unfinished human questions, and the next human playtest.

## Useful checks and commands

```bash
python3 -m unittest discover -s tests
node tools/test_succession_engine.mjs
node tools/test_succession_parity.mjs
node tools/test_web_engine.mjs
python3 tools/make_web_board.py
python3 tools/make_print_pack.py
node --check web/app.js
git diff --check
```

`jsdom` was installed outside the repository at `/tmp/dioclet-ui-check`. The UI test resolves it from the working directory:

```bash
cd /tmp/dioclet-ui-check
node /home/agent/dioclet/tools/test_web_ui.mjs
```

A missing `jsdom` prints SKIP and exits successfully. SKIP is not a passed UI test.

For a browser preview, use an available port and the existing agent-browser skill. Chromium needs `--args '--no-sandbox'` in this container. Close owned browser sessions and servers after verification.

Deployment uses the existing authenticated Worker configuration:

```bash
wrangler deploy
```

Finish the concrete implementation, tests, evidence, and reviewable result before any required release approval. The earlier conversation already authorizes implementing and publishing this prototype; do not invent another approval gate for routine fixes.

Do not commit unless the user asks or an applicable workflow requires it. If you do commit, follow the repository's commit instructions and git-note skill requirements.

## Final handoff to the user

Lead with what works and what is live. Link the actual programme report and selected rules. State how many games and live requests ran, which variants were retained or rejected, and the measured limits.

Be explicit that simulation screens mechanics and strategies. Human playtests must still establish whether the game is clear, tense, and worth replaying.
