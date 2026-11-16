# Plan: correct and fair context for model players

Status: in implementation since 2026-11-16. The three open decisions
are made (see the decision section); each phase lands as one commit
with all checks passing.

## Goal

Every model player in Arena must receive correct, consistent, and
identical information. After that, Arena must measure whether more context
makes the models play better, one change at a time.

The game mechanics do not change. The golden traces
(`tests/test_golden_traces.py`) must stay identical through every phase.

## Verified problems (2026-11-16, commit 479959c)

1. **Two different win conditions.** The rules use a claim window of 2
   rounds (`rules/imperial-rivals-v0.10.2.json`,
   `succession.claim_window_rounds`). `rule_summary` describes the window
   correctly (`candidate_actions.py:76`). But these texts describe the old
   V0.8 rule, where a claim wins after one response from each rival:
   - the projection `objective`: "survive one completed response turn from
     each rival" (`candidate_actions.py:115`)
   - the proclaim description: "win if it survives one response from every
     rival" (`candidate_actions.py:247`)
   - the Arena instructions: "If you are the final rival to respond,
     unrelated action can hand the claimant victory"
     (`arena/arena/providers/systemone.py:33`,
     `arena/arena/providers/openai_decisions.py:33`)
2. **The "exact" duel odds are wrong.** `engine.observe` sets
   `equipment_bonus: 0` for every player (`engine.py:650`). The candidate
   features calculate `duel_win_probability_exact` from that value and the
   base tie rule (`candidate_actions.py:210-221`). The engine resolves a
   duel with the best attack bonus (gladius, or pilum against the
   claimant), the best defense bonus (scutum), and the pugio tie-break
   (`engine.py:826-872`). Thus every duel shows 58.3%. The duel
   description (`candidate_actions.py:252-256`) shows the same wrong value.
3. **The providers do not receive the same information.** The OpenAI and
   gateway adapters add `candidate_features` to the evidence
   (`openai_decisions.py:51-58`). The System One adapters (Jev, Clef,
   Perplexity) send only the projection and the descriptions
   (`systemone.py:52-66`). A comparison between providers is not fair.
4. **Arena cannot measure play quality.** It plays one game with one seed
   and fixed seats. Seat order and dice have a large effect, so one game
   is not evidence.

## Decisions made by Niko, 2026-11-16

1. **Claim window: option A.** The engine follows the print. A claim
   proclaimed in round R now wins at the end of round
   R + `claim_window_rounds` (two full rounds after the proclaim when
   the window is 2). The engine predicate changes from
   `round - pending.round >= window` to `> window`; the web engine
   changes identically; the golden traces are re-recorded; SPEC.md and
   DECISIONS.md record it (D56). Balance results measured before D56
   used the shorter window.
2. **Baseline series:** 5 seeds x 4 seats = 20 games (about $0.40 at
   the 2026-11-16 rates), recorded in `docs/findings/FINDINGS_ARENA.md`.
3. **Phase 8:** only if Phases 5-7 show a gain.

## Root rule (Niko, 2026-11-16): the rules JSON is the source of truth

The rules JSON and its schema are the root of everything. Every rule
text - model projections, provider instructions, and the printed
documents - is generated from the active rules file. No sentence in
any generated document may state a rule value that the generator does
not read from the rules file. The print kit generators
(`tools/make_a4_print_kit.py`, `tools/succession_content.py`) derive
their numbers from the rules JSON so new PDFs follow rule edits.

Background to decision 1: before D56 the engine crowned a surviving
claim at the end of round R+1 (`round - pending.round >= window`), one
round earlier than the print's "two full rounds" (the live game
`arena/runs/20261116T165636Z-arena-42-4c19ad02` shows the old timing:
P3 proclaimed on turn 122, round 7, and won after turn 128, the end of
round 8). The player mat even shipped the old timing as text. Option A
makes the rulebook wording true and fixes the mat. Phase 6 computes
the deadline from the engine logic, never from a copied value.

## Principles

- **Generate all rule text from the active rules.** No sentence in a
  projection, a description, or an instruction may state a rule value that
  the code does not read from the rules file. Each rule text has a test for
  window = 0 and window = 2.
- **Three kinds of numbers, labeled.** `exact` (a deterministic fact or an
  exact probability for this action only), `estimate` (a heuristic), and
  `unknown`. Do not label a value `exact` unless a test proves it against
  the engine.
- **One evidence object for all providers.** Adapters change only the
  envelope (request format). They do not add, remove, or reword content.
- **Public information only.** The hidden-information sentinel tests
  (`arena/tests/test_hidden_info.py`, `tests/test_succession_decisions.py`)
  must cover each new field.
- **No change to mechanics.** The golden traces stay identical. The bots
  do not read the new fields.
- **Measure each change separately.** Phases 5–8 each have a measurement
  step. Do not combine two context changes in one measurement.

## Phases

Each phase ends with all checks passing and one commit.

### Phase 1: Rule text from the rules

- Add one function in `candidate_actions.py` that writes the claim rule
  from `succession.claim_window_rounds`. Use it in `rule_summary`, the
  projection `objective`, and the proclaim description.
- Move the Arena instructions (now duplicated in `systemone.py` and
  `openai_decisions.py`) into one module, `arena/arena/prompt.py`. Build
  the instruction from the active rules. Use this text as a start:

  > Choose the supplied action that maximizes your eventual chance of
  > winning under the active rules. Compare immediate outcomes, resource
  > costs, progress toward a claim, and rivals' opportunities to win or to
  > cancel your claim. Use the explicit deadline when a claim is pending.
  > Contest odds describe that contest only.

  Remove the "final rival to respond" sentence when the window is not 0.
- Tests: with window = 2, no text contains "response from every rival" or
  "final rival"; with window = 0, the text describes the response rule.
  One test collects every string that goes to a provider and checks it.
- Bump `SUCCESSION_SCHEMA_VERSION` (`candidate_actions.py:15`).

### Phase 2: Correct duel odds

- Write `duel_odds(attacker, defender, rules, pending_claim)` in
  `candidate_actions.py`. It must use the same logic as the engine: the
  best attack modifier (gladius; pilum only against the pending claimant),
  the best defense modifier (scutum), never a sum, the pugio tie-break
  (only a lone holder wins the tie), then `duels.tie_winner`. Return the
  win probability and the parts: attack bonus, defense bonus, pugio
  holders, tie rule.
- Use it for `duel_win_probability_exact` and the duel description.
- Remove `equipment_bonus` from `engine.observe` (`engine.py:650`) and
  from the projection (`candidate_actions.py:109`). Its value is always 0.
  Remove the `equipment_bonus` terms from the bot heuristic at
  `engine.py:1186-1187`; the result does not change, because the value is
  0. Remove the field from the web engine too, if it exists there.
- Tests:
  - For every combination of items for both sides (with and without a
    pending claim against the defender), compare `duel_odds` with the
    engine. Force all 36 dice pairs into the engine duel and count the
    wins. The values must be exactly equal.
  - The golden traces stay identical.
  - Web parity passes.

### Phase 3: One evidence object for all providers

- Add `arena/arena/evidence.py`: `build_evidence(view)` returns one dict:
  the rule summary, the projection, and the candidates with
  `action_id`, `kind`, `description`, and `features`.
- The OpenAI adapter sends it as `input_json`. The System One adapters
  send it as `state`. Both use the same choice list (`action_id` and
  description) and the instruction from Phase 1.
- Tests: for the same turn, the evidence in the OpenAI request and in each
  System One request is deep-equal. A test fails if an adapter adds a key.
- Bump the Arena log schema to `arena-match-v3`. Update
  `arena/README.md`.

### Phase 4: Series runner and measurement

Arena needs this before any context change can be measured.

- A series file, for example `matches/series-four-way.json`: the rules,
  the four players (provider and model), the number of seeds, the budget
  for the whole series, `rotate_seats: true`, and
  `shuffle_candidates: true`.
- `uv run arena --series <file>` plays each seed four times, with the
  players rotated across the seats (each player plays each seat once). It
  writes `runs/<series id>/` with one directory per game and a
  `summary.json`.
- Shuffle the candidate order with a deterministic seed per game, turn,
  and seat. Record the order in the log. Report how often each model
  selects position 1.
- The report, per player: wins, win rate with a 95% interval, wins per
  seat, incomplete games, missed interventions, calls, input tokens, cost,
  and latency (median and p95).
- **Missed intervention:** a rival claim is pending, the seat has a legal
  duel against the claimant, the seat selects a different action, and the
  claim then wins. Count it from `match.jsonl`.
- **Tactical fixtures:** `arena/tests/fixtures/tactical/*.json`. Each file
  has one public position, the legal actions, and the set of correct
  actions. Start with: cancel a claim that wins at the end of this round;
  proclaim when it is legal; gain support that you can afford. `uv run
  arena --fixtures` asks each provider once for each fixture and reports
  the score.
- Tests run offline with local bots and test doubles.
- Before the first paid series, show Niko the estimated calls and cost.
  At the 2026-11-16 rates, one four-way game is approximately $0.02.

**Baseline:** after Phases 1–3, run one series (Niko sets the size and
budget). Record the result in `docs/findings/FINDINGS_ARENA.md`.

### Phase 5: Explicit outcomes for each candidate

- Add `outcomes` to the features of duel, guard post, support, proclaim,
  explore, and search candidates. Each outcome has a `condition`, an exact
  `probability` where it applies, and its effects: Prestige after the
  action (cost, reward, cap loss, shame penalty), claim cancelled or not,
  claimant sent to the gate or kept on the square (lorica), item gained,
  card revealed, and abilities used.
- The illustrative form:

  ```json
  {"action_id": "a0012", "kind": "duel", "target": "P2",
   "costs": {"prestige": 1},
   "outcomes": [
     {"condition": "win", "probability": 0.583333,
      "effects": {"prestige_after": 1, "claim_cancelled": true}},
     {"condition": "lose", "probability": 0.416667,
      "effects": {"prestige_after": 0, "claim_cancelled": false}}]}
  ```

- Tests: for each kind, apply the action to a copy of a real state with
  forced dice, and compare the result with each predicted outcome.
- Measure: one series against the baseline.

### Phase 6: The claim deadline and the turn order

- Add a `claim` block to the projection when a claim is pending: the
  claimant, the turn after which the claim wins, the remaining turns in
  order (with the rotation of the first player), the number of chances
  that each rival has to cancel the claim, and whether this seat can
  cancel it on this turn.
- Calculate the deadline with the same logic as the engine (see the
  decision above). Do not copy the rule into a second place.
- Tests: play forward with actions that do not cancel the claim, and
  compare the predicted last turn with the turn on which the engine ends
  the game. Test claims made on each of the four turn positions in a
  round.
- Measure: one series against Phase 5.

### Phase 7: Named targets

- Add a `goals` list to the projection. Each goal has a name, a target
  cell, the exact street distance, the prerequisites, and whether the seat
  meets them. Examples: "Army support: 3 steps, card face up, costs 1
  Prestige, you can pay"; "Peristyle: 5 steps, needs 2 factions, you have
  1"; "card space C: 4 steps, face down".
- The chance to reach a target on the next turn is exact (two dice, sum at
  least the distance). Label more turns as an estimate.
- For face-down cards, give only what the public reveals and the setup
  rules prove (for example, "2 of the 4 face-down cards are factions").
- Measure: one series against Phase 6.

### Phase 8: Short event history (only if Phases 5–7 help)

- Add the public events since the previous turn of this seat, and this
  seat's previous action and its result. Limit the size (for example, 12
  events).
- Measure: one series against Phase 7.

## Not in this plan

- Changes to how the shortlist selects candidates (more varied routes).
  Do this later, with its own measurement.
- Full conversation history, or a strategy journal written by the model.
- Any change to the mechanics, except the claim window decision above,
  which Niko makes separately.

## Checks after each phase

```bash
python3 -m pytest -q                       # includes the golden traces
node tools/test_succession_parity.mjs
node tools/test_web_engine.mjs
node tools/test_web_ui.mjs
cd arena && uv run pytest -q && uv run arena --match matches/bots.json
```

Paid live tests and series run only when Niko approves a budget.

## Questions for Niko

All three questions are answered in "Decisions made by Niko,
2026-11-16" above: option A, a 20-game baseline, and Phase 8 only on
measured gains.
