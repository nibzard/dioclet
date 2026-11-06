# Diocletian's Palace — Game Mechanics Simulator Specification

**Status:** Implementation-ready V0.1 proposal  
**Audience:** Claude Code / coding agents  
**Language:** Python 3.11+, standard library only  
**Primary goal:** Use repeatable simulation to find out whether the two-level, four-player game is fun, fair, interactive, and likely to finish in a reasonable time.  
**This is a *prototype rule set*, not a claim that these are final game rules.**

## 1. What to build

Build a small, headless, turn-based game engine with:

1. **An editable JSON rule set** (see `rules_baseline.json`) controlling the important mechanics without code changes.
2. **A deterministic state machine** with a seeded random number generator.
3. **A CLI for one agent-controlled turn at a time**, exposing only information that a real player would know.
4. **Built-in non-LLM bots** for running 1,000–10,000 games quickly and cheaply.
5. **Append-only JSONL event logs**, one terminal `result.json` per game, and aggregate reports for batches.
6. **Replay and invariant tests** to detect engine bugs separately from game-design problems.

Claude Code may orchestrate **four role-playing subagents for a handful of selected games**. For large batches, do not invoke four LLMs on every turn: use built-in policies and reserve LLM agents for qualitative playtests.

### Non-goals for V0.1

No graphical user interface, network multiplayer, animated board, complex deck, special equipment powers, equipment theft, narrative story engine, database, or historically exact palace plan. The V0.1 board is a small graph abstraction of the six zones, four gates, and central junction in the provided images. All of these can be considered later.

## 2. Core game overview

- **Players:** exactly four, identifiers `P0`, `P1`, `P2`, `P3`.
- **Levels:** Level 1 (explore six districts to obtain six equipment types); Level 2 (earn two Imperial Seals and defeat the Emperor).
- **Turn structure:** each active player gets one movement die result, chooses **one** legal action, and resolves it immediately. A full *round* means that all four players have had one turn.
- **Movement:** orthogonal movement on a grid graph; a die result is a **maximum**, not an exact number of steps. Players can deliberately stop early. This is intentional to prioritize route planning over exact-roll luck.
- **Player encounters:** optional duels at short range. Winner receives Glory; loser keeps equipment and progress.
- **First complete objective:** the first fully equipped player to reach the central checkpoint starts a brief final countdown. At the end of that countdown, all players enter Level 2, with missing equipment granted automatically.
- **Victory:** first player to land two successful attacks on the Emperor in Level 2 wins. The game can also end in a timeout draw.

Record all decisions and outcomes; do not silently add rules or narrative effects.

## 3. Board abstraction

Use one **5 × 5 orthogonal graph** per level, coordinates `[x, y]` with `x,y ∈ {0,1,2,3,4}`. Every cell is a walkable waypoint, not a physical room interior. All horizontal and vertical neighbors are connected by undirected edges of length one. No diagonals or walls in V0.1.

### Level 1 sites

```
       x=0     1      2      3     4
 y=0    ·      ·     N/P0    ·     ·
 y=1   GP      A      B      C     GP
 y=2   W/P3    ·      X      ·    E/P1
 y=3   GP      D      E      F     GP
 y=4    ·      ·     S/P2    ·     ·

A–F: six equipment districts (physical board's six blocks)
X: central checkpoint
GP: Glory guard posts
N/E/S/W: entry gates / initial pawns
```

Six equipment names are shuffled bijectively among districts A–F **at game creation**. All district identities are initially hidden from players. Once any player uses `explore` at a district, its equipment identity is publicly revealed for everyone, for the remainder of Level 1. Every player may independently acquire that equipment type from the revealed district; cards are *not* depleted. A player never needs more than one copy of a type.

### Level 2 sites

Same grid and same gates, but the location functions change:

- Cellars: `[1,1]`
- Guard barracks: `[3,1]`
- Peristyle: `[2,2]`
- Emperor's chamber: `[2,4]` (southern side of the Palace)
- Failed-attack retreat: `[2,3]`

The remainder are transit nodes. Phase 2 challenges and movement are independent of the hidden equipment assignment.

**Trade-off to test:** the 5×5 graph is deliberately smaller than the number of white circles on the real board. It is for first-pass mechanics only. A later version should use an extracted adjacency graph of the actual printed paths once the game loop proves worthwhile.

## 4. State and visibility

Engine state (private) must include:

- Rules version and SHA-256 hash of an immutable config snapshot.
- Game id, seed, per-stream RNG state/counters, global turn number, full round number, active player, phase, current movement roll, phase countdown, termination status.
- Each player: gate, current coordinate, equipment set, Glory count, Imperial Seal set, Emperor hit count, number of turns, and counters relevant to telemetry.
- True equipment-to-district mapping and currently revealed districts.
- First Level 1 finisher, transition trigger round, phase start round.

**Player observation** must include only: phase, active player, dice result for the active turn, positions of all pawns, all players' publicly visible equipment counts/sets and Glory, seals and hits, revealed district identities, active progress conditions, and the full list of legal actions. Do not reveal unopened equipment locations, future rolls, private bot state, or RNG internals.

For this prototype, equipment sets, Glory, seals, and Emperor hits are all **public information**. The only hidden information is the unrevealed equipment mapping, future dice, and policy internals.

Observing is side-effect free: calling `observe` any number of times must never change RNG state or game state.

## 5. Deterministic turn protocol

1. At the **start** of a player's turn, the engine rolls a movement die (`1..6` by default), stores the result, and returns it with `observe`.
2. Engine calculates `legal_actions`; each action has a stable `action_id` for that turn, an endpoint, an action kind, an optional target and/or Glory-spend flag, and a deterministic shortest path.
3. Player submits **exactly one legal `action_id`**. The engine checks `player_id` and `turn_id` to reject stale or out-of-order actions.
4. Engine resolves movement, action outcome, any challenge dice, Glory, phase transitions, and victory checks. It appends a complete event record.
5. Engine advances the active player in the configured order, rolling the next movement die only when the next turn starts. Once a game ends, no further actions are legal.

### Movement and ending a turn

- Choose a destination whose **shortest-path distance** from current location is `≤ movement_roll`. Travel along the lexicographically deterministic shortest path, using neighbor tie-break order **north, east, south, west**. This makes movement reproducible and prevents agents from exploiting arbitrary loops.
- Ordinarily a move must travel at least **one edge**. A **zero-step action** is permitted only for `explore`, `claim_checkpoint`, `attempt_seal`, or `attack_emperor` when standing on the relevant site. These consume a full turn.
- Players may occupy the same node and may pass through each other. Passing through another pawn does **not** trigger combat. Only an explicitly selected `duel` action does.
- Exactly **one primary interaction** is allowed each turn: `move`, `explore`, `duel`, `guard_post`, `claim_checkpoint`, `attempt_seal`, or `attack_emperor`. For example, you cannot explore a district and fight a player in the same turn.
- Moving onto a special site without choosing its corresponding action has no effect.
- `move` (no interaction) is legal only for a nonzero move; zero-step no-ops are not legal.
- The command `legal_actions` must enumerate fully valid endpoint/action combinations. Do not require the player agent to calculate paths or infer whether an action is possible.

### Legal action conditions

- `explore`: Level 1; destination is one of A–F and player does not own the equipment at that district. If district is unrevealed, it remains a legal exploration target.
- `guard_post`: Level 1; destination is one of four GP sites; move distance ≥1; player has fewer than max Glory tokens.
- `claim_checkpoint`: Level 1; destination is X; player has all six equipment types; no prior player has triggered the transition. This action is legal as either a move or stationary action.
- `duel`: either level; move distance ≥1; select one other player whose **final position** is within `duel_range` orthogonal shortest-path edges of the mover's destination. No combat for merely passing a pawn.
- `attempt_seal`: Level 2; destination equals a challenge site; player does not yet own that challenge's seal; may be stationary if already there. For Peristyle, offer separate `roll` and `spend_glory` action IDs if player has sufficient Glory.
- `attack_emperor`: Level 2; destination is the Emperor chamber; player has at least the required number of **distinct** seals; may be stationary if already at chamber; offer both `spend_glory=false` and `true` when feasible.
- `move`: either level; any valid nonzero destination within range.

Action IDs can be sequential strings like `a0001`, but must be generated in a stable sorted order for a given observation. The engine must reject unknown IDs without advancing time.

## 6. Level 1 resolution

### Exploration

Upon a successful `explore` action, reveal that district's equipment identity to everybody and grant the type to the player. One district has exactly one type, each type occurs at exactly one district, and one player can collect at most one new type per turn. Visiting a district with equipment already owned offers no `explore` action. Equipment is never lost in V0.1.

### Guard posts and Glory

On a `guard_post` action, roll a new d6. If the value is **4, 5, or 6**, gain one Glory, subject to the cap; otherwise gain none. There is no additional failure penalty. A guard post cannot be used without first moving onto it on that turn (no stationary farming).

### Player duel

Each duelist rolls an independent d6. Add the current equipment bonus:

| Owned items | Bonus |
|---|---:|
| 0–2 | 0 |
| 3–5 | +1 |
| 6 | +2 |

A duel is initiated and resolved on the attacker's turn with **no defender decision** in V0.1. Higher total wins; on a tie, the **defender wins**. The winner gains one Glory (up to cap). No one loses equipment, seals, turns, Glory, or position. Log both dice, modifiers, final scores, winner, and whether Glory was actually awarded due to the cap.

### Level 1 transition

- A player with six pieces who successfully chooses `claim_checkpoint` at X is the **First Challenger**. Grant them +1 Glory subject to cap and record the trigger round `R`.
- Finish the remainder of round `R` and then **`grace_full_rounds` complete additional rounds**; default 2. For example, if a trigger occurs in round 5 (1-indexed), play through rounds 5, 6, and 7; transition before round 8.
- If nobody triggers the checkpoint by the end of `level1.max_rounds`, transition anyway and flag `phase1_timeout=true`.
- At transition, grant *all* missing equipment to *all* players, recording each auto-granted type. Preserve Glory, reset all pawns to their original gates, and start Level 2 at the beginning of a new full round, maintaining the same player order but resetting the per-phase round counter to 1. Only one movement die is rolled for each new turn; old Level 1 rolls do not carry over. This is a **catch-up rule to test**, not a settled design. Measure its effect on incentives and fairness.
- Once First Challenger has triggered, `claim_checkpoint` disappears from legal actions; other players may continue exploring, dueling, or earning Glory until transition.
- If the grace deadline and max round deadline both apply, transition at whichever occurs first.

## 7. Level 2 resolution

Each player starts Level 2 with all six equipment types. They retain Glory from Level 1. The three Imperial Seals are personal; challenge locations are shared and never depleted.

### Three challenges (claim two distinct seals)

| Site | Action | Success | Failure |
|---|---|---|---|
| Cellars | Roll d6 | 3–6 | Keep position, try again on a later turn |
| Guard barracks | Player rolls d6+equipment bonus; guard rolls d6+1 | Player score strictly higher | Keep position, try later |
| Peristyle | Roll d6 | 5–6 | Keep position, try later |
| Peristyle | Spend 1 Glory *instead of rolling* | Guaranteed success | Not applicable |

On success, add the seal identifier to that player's seal set. A player cannot repeat an already completed seal. A player needs **any two of the three different seals** before challenging the Emperor.

### Emperor encounter

- Chamber is at `[2,4]`. Each player requires **two successful hits** against the Emperor. Hits are tracked separately per player and persist after a failed attempt.
- Each attempt compares player **d6+equipment bonus** to Emperor **d6+2**. Ties go to Emperor.
- A challenger may **pre-commit** to spending 1 Glory; if spent, add **+2** to this attack, whether it succeeds or fails. Unlike the visual demonstration discussed earlier, Glory is spent **before** rolling here so the engine resolves each turn atomically with one chosen action.
- On success, award one hit, keep player in the chamber, and allow a stationary re-attack on their next turn. On failure, move them to retreat node `[2,3]`; no hits, seals, or other equipment are lost.
- The **first** player to reach `emperor_hits_to_win` wins immediately. If nobody succeeds by `level2.max_rounds` completed rounds, end in a draw and flag `phase2_timeout=true`.
- Other players may continue normal duels in Level 2. Glory earned from a duel can be used in a later Emperor attempt.

## 8. Rule configuration

Load all tunable values from the JSON at the start of a game and store an immutable copy with that run. At minimum, the baseline file exposes:

- Movement die size, duel distance.
- Coordinates of gates, six districts, guard posts, checkpoint, challenge sites, Emperor, retreat node.
- Equipment names and bonus tiers.
- Glory cap, guard-post threshold, Glory rewards, Glory attack bonus.
- Level 1 maximum rounds, grace rounds, auto-equipping toggle.
- Level 2 maximum rounds, seals needed, challenge difficulty, Emperor bonus, hits needed.

**Validation:** unknown keys may be rejected (preferred), and invalid combinations must be rejected with clear errors. Validate coordinates, site uniqueness where necessary, reachable graph sites, all four gates, six distinct equipment types/districts, threshold bounds, nonnegative bonuses, and `required_seals ≤ 3`. If `auto_equip_at_transition=false`, phase 2 must still be playable: either reject that configuration for V0.1 or define a separate mechanic explicitly; **prefer rejection** in V0.1.

Do not embed a second, diverging source of truth for defaults in the Python engine. `rules_baseline.json` is the canonical baseline and tests should load it.

## 9. Required command-line interface

Use `python sim.py <command> ...`. JSON output on stdout for machine-facing commands; errors on stderr and nonzero exit codes. All paths must be explicit (no implicit global state).

```bash
# Validate the rules (should exit 0 and print a short JSON report)
python sim.py validate --rules rules_baseline.json

# Create one persistent game; outputs game metadata and first active player
python sim.py new --rules rules_baseline.json --seed 42 --out runs/demo

# Observe: side-effect-free, includes current roll and numbered legal actions
python sim.py observe --run runs/demo --player <active_player_from_new>

# Submit an action_id and turn_id returned by observe; these are placeholders
python sim.py act --run runs/demo --player <active_player> --turn-id <turn_id> \
  --action-id <legal_action_id> --note 'Collect the nearest unknown district'

# Finish a partially played game with built-in policies
python sim.py auto --run runs/demo --policies balanced,greedy,aggressive,random

# Thousands of fast, headless games, with seeds seed-base ... seed-base+games-1
python sim.py batch --rules rules_baseline.json --games 1000 --seed-base 1000 \
  --policies balanced,greedy,aggressive,random --out results/v01

# Summarize an existing batch and verify one game's reproducibility
python sim.py report --input results/v01
python sim.py replay --run runs/demo --verify
```

Command arguments in the examples above are required interfaces except the arbitrary `--note` text, which is optional. If the chosen action ID is invalid, print `legal_action_error` and do not mutate game state. For `observe`, reject requesting an observation for someone other than the current player rather than leaking the next player's handoff.

`new` determines a **deterministically seeded turn order**. Keep player ids mapped to fixed gates (`P0` north, `P1` east, `P2` south, `P3` west), then shuffle the order per seed, and report it. Batch policy identifiers are seat assignments in the order `P0,P1,P2,P3`.

### Single writer / multi-agent orchestration

The game engine owns state. Claude Code is the **single orchestrator** and invokes at most one `act` per turn. Each of the four Claude subagents gets the current player's `observe` JSON and responds with `{ "action_id": "...", "reason": "..." }`. The orchestrator validates and applies that choice, then sends the next observation to the appropriate agent. **Do not give all four agents write access to `state.json` concurrently.** The game is sequential even if the four roles are maintained in parallel.

## 10. Built-in bot policies

Create at least these four bots. They must pick only from the action list exposed by the player observation; no inspection of the private mapping or future RNG draws.

1. **`random`** — sample an *action category* first (to avoid the many ordinary `move` endpoints swamping interesting actions), then sample a legal action from that category. Keep category weights configurable or documented.
2. **`greedy`** — Level 1: prioritize collecting missing equipment, exploring unknown districts, then the checkpoint; Level 2: choose the closest two achievable seal sites and attack the Emperor as soon as eligible. Use shortest distance, then a stable coordinate tie-break.
3. **`aggressive`** — prefer duels when Glory is not capped, but still pursue gear and seals; use Glory aggressively for Peristyle and Emperor attacks.
4. **`balanced`** — pursue objectives but divert for nearby duels/guard posts if Glory is useful, and use Glory strategically for seals or Emperor. Avoid unnecessary fights while Glory is capped.

For `greedy`/`balanced`, when no priority action is reachable in this turn, choose a reachable `move` action that reduces distance to the best target. Unknown district values must be treated as unknown, not read from engine state. Each bot's heuristic should be separately unit-tested and documented.

At first, run **balanced vs balanced vs balanced vs balanced**, then rotate the policy assignments and gate order for policy comparisons. Do not mistake a fixed gate advantage for a strategic advantage.

## 11. Logs and output files

### Per-game directory

```
runs/<game_id>/
  rules.snapshot.json       # immutable config used for the game
  metadata.json             # seed, turn order, policy assignments, engine version
  state.json                # latest resumable state (private; agents must not read)
  events.jsonl              # append-only, one record per resolved turn
  result.json               # written when game finishes
```

Each JSONL record should minimally contain:

```json
{
  "event_seq": 16,
  "turn_id": 15,
  "round": 4,
  "phase": 1,
  "player": "P2",
  "movement_die": 5,
  "action_id": "a0008",
  "action": {"kind": "explore", "destination": [2, 1], "path": [[2, 3], [2, 2], [2, 1]]},
  "dice_used": [],
  "events": [{"type": "equipment_collected", "item": "scutum", "district": "B"}],
  "position_after": [2, 1],
  "glory_after": 1,
  "equipment_count_after": 4,
  "reason": "Collect the district north of the junction"
}
```

This event is **illustrative**; real coordinates, counts, and roll values must come from engine state. Include a `phase_transition` event when one occurs (either as a separate system event or within the triggering turn). `reason` comes from a bot/agent, is optional, and must not affect simulation.

`result.json` should include winner or draw, total turns and rounds, turns per level, phase timeouts, player-by-player metrics, and a short ordered list of high-impact events. Include rule hash and seed.

### Batch outputs

```
results/<experiment>/
  rules.snapshot.json
  experiment.json      # seeds, policies, engine version, timestamp
  games.csv            # 1 row per game, flattened statistics
  summary.json         # aggregate statistics and rates
  sample_games/         # full logs for e.g. first 5 seeds + edge cases
```

Full JSONL logs for 1,000+ games are optional (config flag) to limit disk usage. **Always** save the config/seed and per-game result; save full logs for a small reproducible sample and all anomalous games (timeout, invalid state, extreme game length).

## 12. Statistics to compute

At minimum, calculate the following over all games, by player/gate/seat/policy where relevant:

- Win rate; draws/timeouts; Level 1 checkpoint trigger rate; first-challenger rate; first-challenger eventual win rate.
- Duration in rounds and individual turns for each level and the complete game: mean, median, p90, p95, max.
- Collected equipment per player *before* auto-equip; count of auto-granted items; whether players deliberately avoid exploration because of auto-equip.
- Duels initiated, accepted/resolved, attacker win rate, defender win rate, number of turns without player interaction, Glory earned/spent/wasted at cap.
- Attempts and successes at each seal, seal acquisition order, Glory spent buying a Peristyle seal.
- Emperor attempts, attack success rate, hits per player, Glory spent on Emperor, player victories after comeback.
- Action-category frequencies, visited nodes/districts, percentage of players who actively explored at least three districts.
- Relative win rates by gate and by player turn-order position, with policies rotated.

Report both raw counts and denominators, and 95% confidence intervals for win-rate proportions if convenient (e.g. Wilson intervals). Avoid claiming precision from tiny sample sizes.

### Initial design questions / hypotheses

1. **Does Level 1 end too quickly?** If 90% of games auto-grant 3+ equipment per player, players may never feel the six-item collection challenge.
2. **Does aggression pay?** Does an `aggressive` bot win significantly more than `greedy`/`balanced`, or are duels pointless / overly rewarding?
3. **Does the game become a pure sprint?** If First Challenger wins most games, adjust their advantage or phase transition.
4. **Are dice too dominant?** Does a strong policy outperform `random`? If not, add meaningful decisions rather than adding more randomness.
5. **Do all gates have comparable odds?** Measure win rate by gate with policies permuted.
6. **Does the endgame drag?** Measure repeated seal failures, Emperor attack attempts, and phase 2 timeouts.
7. **Can a younger player recover?** Measure comeback wins and how often players who trail after Level 1 can still win.

## 13. Experiments and tuning protocol

### Minimum first experiment

Run **1,000 seeded games** per ruleset, distributed among:

- 250 games: `balanced,balanced,balanced,balanced`.
- 250 games: one `aggressive` and three `balanced`; rotate aggressive through all seats across seeds.
- 250 games: one `greedy` and three `balanced`; rotate greedy through all seats.
- 250 games: `random,greedy,aggressive,balanced`; rotate all policies through all gates/seat slots.

Keep exact seeds, fixed bot versions, and assignment schedules documented. Also replay three finished games and verify identical outputs. Then run five narrative games with Claude subagents to gather qualitative observations that counters cannot capture.

### Controlled rule changes

Change **one conceptual knob at a time** (even if that knob consists of linked JSON fields); reuse the same seed list and policy assignment schedule. Suggested first variants:

- `grace_full_rounds`: 0 vs 2 vs 4.
- `auto_equip_at_transition`: keep `true` for V0.1; a later experiment can introduce a fully specified non-auto-equip mode.
- `duel_range`: 1 vs 2 vs 3.
- `glory.cap`: 1 vs 2 vs 3.
- `emperor_hits_to_win`: 1 vs 2 vs 3.
- `emperor_bonus`: 1 vs 2 vs 3.
- `level1.max_rounds`: 16 vs 24 vs 32.
- Guard/Cellar/Peristyle success thresholds.

Never run a silent automated rule optimizer that edits `rules_baseline.json` mid-batch. Every variant gets a separate file (`rules_v02.json`, etc.) and independent results directory; compare with a table and recommend the next experiment. Human review chooses new rules after seeing the data.

### Suggested provisional success targets

These are **diagnostic targets**, not objective definitions of fun:

- >95% of balanced-bot games produce a winner rather than timing out.
- Median full game length about **20–35 full rounds** (80–140 individual player turns), subject to real-world playtesting.
- At least 2 duels per game on average (otherwise encounters may need stronger incentives).
- At least 3 equipment items actively collected per player on average before auto-equip (otherwise the six-item quest is mostly cosmetic).
- Balanced and greedy policies consistently beat random after gate/order balancing (otherwise player choices may be too weak).
- No single starting gate has a large, unexplained advantage after seat/policy rotation.

A game may meet these targets and still be boring. Use selected human/LLM playthroughs and eventually physical playtesting to assess subjective fun.

## 14. Tests and reproducibility

Provide unit/property-like tests using Python's `unittest` or `pytest` only if installed; no external dependencies required.

**Essential invariants:**

- A player never moves farther than the turn's movement die, except an explicitly declared Emperor failure retreat.
- Manhattan movement, no diagonal edges, correct deterministic shortest-path selection.
- `observe` is idempotent; invalid/stale actions do not mutate RNG, state, or logs.
- No player has duplicate gear or a Glory count outside `0..cap`.
- Exactly six equipment types are assigned uniquely to six districts; unrevealed mappings never appear in player observations.
- All players have full equipment after the Level 1 → Level 2 transition.
- Phase 2 seals are distinct and at most three per player; Emperor cannot be attacked with too few seals.
- Failed boss attacks cause the correct retreat; successful hits persist; first player hitting the threshold ends the game.
- Tie rules, edge cases when Glory is capped, and Peristyle spending are correct.
- Transition fires after the correct number of **full** grace rounds, independent of which seat triggered it.
- Replaying the same seed, immutable config and action sequence produces byte-equivalent normalized events and result (excluding timestamps).
- Games have a finite turn limit and cannot hang.
- Action IDs are legal only for their own turn, including after a phase transition.

For the selected tiny board, add a **bounded exhaustive test** over all action choices for depth 1–3 (and mocked fixed dice) to detect illegal transitions. Enumerating literally every complete game is computationally infeasible due to combinatorial randomness and action branches; use bounded enumeration, property tests, and Monte Carlo simulation instead.

## 15. Implementation organization

Recommended modules (flexible):

```
sim.py                 # CLI entry point
engine.py              # pure transition logic, legal action generation
board.py               # graph, shortest path and site lookups
policies.py            # observation-only bots
report.py              # aggregations, histograms, CSV/JSON
rules_baseline.json    # configurable rules
SPEC.md                # this specification
tests/                 # seeded regression + engine invariants
```

Prefer plain Python data classes and dictionaries, JSON serialization and `argparse`. `engine.apply_action` should be a deterministic function of `(state, valid_action, RNG)` and return `(new_state, events)`. Keep bot strategy outside the engine. When persisting a CLI turn, write `state.json` atomically (temp file + rename) and make replay robust to interrupted writes; only one orchestrator process should write to a run directory.

A simple implementation can use Python's `random.Random` with its state serialized reversibly in JSON (not `pickle`) or a counter-based hash RNG. The important contract is **determinism, replayability, and independence from observation calls**. Keep independent RNG streams for equipment placement, movement, and battle/challenges if practical; bot randomness must not alter game dice.

## 16. Delivery / acceptance criteria

Deliver the runnable engine, canonical JSON file, tests, README with exact commands, a 10-game smoke test log bundle, a 1,000-game summary, and a short `FINDINGS.md` that answers:

1. How often does a game reach a winner, and after how many turns?
2. How often are all six gear items collected *versus auto-granted*?
3. How often do players fight, and are those fights strategically useful?
4. Which strategies dominate, and do initial gates matter?
5. What are the top three suggested **single-knob** rule experiments next?

The coding agent should first implement the baseline **exactly**, then test it, and **only afterwards** propose changes; no silent deviations from the specification. If a rule is ambiguous, document the chosen interpretation in `DECISIONS.md` and add a test.
