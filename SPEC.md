# Imperial Rivals: 305 AD — Engine Specification

**Status:** Implemented. The engine, the rules file, the browser game,
the print kit, and Arena all describe **Imperial Rivals: 305 AD,
rules V0.10.2**. This document states what the code does.
**Rules text source of truth:** the printed kit under `print/bw/`
(rulebook and quick reference). **Behavior source of truth:** this
repository's code. History documents (`notes/`, `docs/findings/`,
`DECISIONS.md` D1–D54) record older versions and keep their own words.

## 1. The game

Imperial Rivals: 305 AD is a board game for exactly four players
(`P0`, `P1`, `P2`, `P3`). Diocletian has retired. Four rivals prepare
a claim to the throne.

The game has two phases and two boards:

1. **Palace phase.** Players collect equipment from the six treasure
   entries (A–F) and earn Prestige at guard posts and in duels. The
   first player who owns all six items may stand at the Peristyle and
   claim the checkpoint. The palace phase ends one full round after
   that claim, or at round 24 if nobody claims.
2. **Succession phase.** Every pawn returns to its gate on the
   succession map and keeps everything it owns; any seat entering
   below `transition_min_prestige` (1) rises to 1 Prestige. Six
   face-down faction cards sit on the card spaces: the Army, the
   Imperial officials, the City elites, and three empty streets.
   Players search the cards, pay 1 Prestige for a faction's support,
   and proclaim a claim at the Peristyle with support from two
   different factions.

**Win conditions, in the printed words:**

- A claim that stands one full round unchallenged makes the claimant
  **emperor** (engine `end_reason` `survived_window`). A claim
  proclaimed in round R wins when the last turn of round
  R + `claim_window_rounds` ends. The active rules set the window to
  1, so the claim survives round R + 1 in full.
- A rival cancels a standing claim only by winning a challenge duel,
  after paying the mandatory **contest fee** of 1 Prestige.
- If no claim stands by succession round 24, the game ends in a
  **draw** (`succession_timeout`).

The engine also implements a second win route for rules files that set
`succession.claim_window_rounds` to 0: a claim is crowned by
acclamation once every rival has completed one response turn
(`end_reason` `acclamation`). The active rules set the window to 1,
so this route does not fire in the printed game.

## 2. The rules file

One file feeds the engine, the web build, the print kit, and Arena:
`rules/imperial-rivals-v0.10.2.json`. One schema describes it:
`rules/rules.schema.json`. The engine validator and the schema accept
the same keys.

The validator (`engine.validate_rules`) requires every key below and
rejects every unknown key. No value is supplied by code.

```json
{
  "game":        {"name": "Imperial Rivals: 305 AD",
                  "rules_version": "0.10.2", "players": 4},
  "turns":       {"rotate_first_player_each_round": true},
  "movement":    {"dice": 2, "die_sides": 6, "allow_early_stop": true,
                  "pass_through_pawns": true,
                  "allow_stationary_special_actions": true},
  "treasures":   {"items": ["pugio", "pilum", "galea", "scutum",
                            "gladius", "lorica_segmentata"],
                  "start_face_up": 2,
                  "abilities": {"gladius": {"type": "attack_bonus", "value": 1}, "...": "..."},
                  "bonus_per_side": "best"},
  "prestige":    {"cap": 3, "guard_post_min_roll": 4,
                  "guard_post_reward": 1, "duel_win_reward": 1,
                  "duel_loss_penalty": 1},
  "duels":       {"range": 2, "tie_winner": "attacker"},
  "palace":      {"max_rounds": 24, "checkpoint_items_required": 6,
                  "rounds_after_checkpoint": 1, "map": {"...": "..."}},
  "succession":  {"max_rounds": 24, "support_cost": 1,
                  "factions_to_proclaim": 2, "contest_fee": 1,
                  "claim_window_rounds": 1, "proclaim_cost": 0,
                  "transition_min_prestige": 1,
                  "faction_cards": {"factions": ["army", "elites", "officials"],
                                    "empty": 3},
                  "gate_assignment": "random", "map": {"...": "..."}}
}
```

Key groups:

| Key | Meaning |
| --- | --- |
| `movement.dice`, `die_sides` | Two six-sided dice per turn; the total is the maximum number of steps. |
| `movement.allow_early_stop`, `pass_through_pawns` | You may stop before the whole roll; pawns never block a street. |
| `movement.allow_stationary_special_actions` | Explore, search, support, claim, proclaim, and the galea work without moving. |
| `treasures.start_face_up` | Two of the six cards start face up. |
| `treasures.bonus_per_side` | `"best"`: each duel side adds at most one item bonus, never a sum. |
| `prestige.cap` | Hold at most 3 Prestige; rewards above the cap are lost. |
| `prestige.guard_post_min_roll` | A guard-post die of 4+ earns 1 Prestige. |
| `prestige.duel_loss_penalty` | The duel loser pays 1 Prestige to the bank, as much as they hold. |
| `duels.range` | Duel a rival within two street circles of your destination. |
| `duels.tie_winner` | On an ordinary tie the attacker wins. |
| `palace.checkpoint_items_required` | Own all six items to claim the checkpoint. |
| `palace.rounds_after_checkpoint` | One more full round after the first claim, then the succession begins. |
| `succession.contest_fee` | The mandatory fee to contest a proclaimed claim. |
| `succession.factions_to_proclaim` | Two different factions must support you before you proclaim. |
| `succession.claim_window_rounds` | A claim proclaimed in round R wins at the end of round R + `claim_window_rounds`. |
| `succession.faction_cards` | Three factions and three blanks, dealt blind onto the card spaces. |

### Maps

Both maps are 19 x 13 grids. `blocked` cells are building interiors;
streets are everything else. Each map carries `width`, `height`,
`blocked`, `gates` (compass names `north`, `east`, `south`, `west`),
`checkpoint`, and `guard_posts`.

- The palace map adds `streets` (cardo, decumanus, secondary),
  `buildings` (six blocks, one per district), and `treasure_entries`
  A–F. The Peristyle (checkpoint) sits at the cardo–decumanus crossing
  `[6, 6]`.
- The succession map adds `card_spaces` (six cells, one in front of
  each block door). Its Peristyle is at `[9, 6]`, three steps east of
  the palace crossing, so every gate is nine steps from it.

Geometry checks inside `validate_rules` (via `board.py`): the palace
map must contain six intact blocks, each block entered by its own
district, with gates ending the main streets; all four gates, guard
posts, and card spaces must sit on reachable street cells; card
spaces may not sit on a gate or the checkpoint.

### Treasure abilities

| Item | Type | Effect |
| --- | --- | --- |
| sword (`gladius`) | `attack_bonus` | +1 to your attack in any duel you start. |
| shield (`scutum`) | `defense_bonus` | +1 to your defense in any duel. |
| javelin (`pilum`) | `attack_vs_claimant` | +2 to your attack against the standing claimant. |
| dagger (`pugio`) | `win_ties` | The lone holder wins tied duels. Both or neither: the attacker wins. |
| helmet (`galea`) | `reveal_district` | Once per game (either phase), as your action: publicly reveal any one face-down treasure or faction card. |
| armor (`lorica_segmentata`) | `prevent_displacement` | Once per game: when your claim is beaten, keep your square instead of returning to your gate. |

The pugio is a passive tie-break, not a number bonus. It works next
to the one number bonus. The number bonuses never stack.

## 3. Engine public API

`engine.py` is a pure state machine. `apply_action` mutates the state
in place and returns the turn record. All randomness flows through
named streams serialized inside the state, so a (rules, seed, action
sequence) triple reproduces a game exactly.

| Function | Signature | Returns |
| --- | --- | --- |
| `new_game` | `(rules, seed, game_id, policies=None)` | New state. Validates the rules first. `policies` maps seat ids to bot names. |
| `observe` | `(state, player)` | Public observation for the active player. Errors `not_your_turn`, `game_over`. Never changes state. |
| `legal_actions` | `(state)` | List of legal actions for this turn, each with a stable `action_id` (`a0001`, `a0002`, ...). |
| `apply_action` | `(state, player, turn_id, action_id, reason=None)` | The turn record. Errors `stale_turn_id`, `legal_action_error`, `not_your_turn`, `game_over`. |
| `result` | `(state)` | Final result blob with per-player metrics (section 8). |
| `is_finished` | `(state)` | True when `status` is not `in_progress`. |
| `check_invariants` | `(state)` | True, or raises `AssertionError` on a broken state. |
| `write_run` | `(run_dir, state)` | Writes `rules.snapshot.json`, `metadata.json`, `state.json`, appends `events.jsonl`; writes `result.json` when finished. |
| `load_run` | `(run_dir)` | The saved state. |
| `reset_events_file` | `(run_dir, state)` | Truncates `events.jsonl` to match the state. |
| `rules_hash` | `(rules)` | SHA-256 of the canonical JSON. |
| `load_rules` | `(path)` | Parsed and validated rules dict. |
| `validate_rules` | `(rules)` | True, or `EngineError` code `invalid_rules`. |
| `choose_policy` | `(policy_name, obs, rng=None)` | `(action_id, reason)` chosen from `obs["legal_actions"]` only. |

Errors are `engine.EngineError(code, message)`; the machine-readable
code rides on `.code`.

## 4. State vocabulary

Top-level state keys: `gameplay_mode` (`"succession-v1"`),
`engine_version`, `rules`, `rules_hash`, `game_id`, `seed`, `rng`,
`players`, `turn_order`, `round_start`, `turn_index`, `rotate_first`,
`turn_id`, `round`, `phase`, `current_roll`, `current_dice`,
`active_player`, `gate_assignments`, `pending_claim`,
`first_challenger`, `trigger_round`, `district_equipment`, `revealed`,
`setup_reveals`, `equipment_at_transition`, `faction_sites`,
`faction_sites_revealed`, `palace_timeout`, `succession_timeout`,
`rounds_palace`, `status`, `winner`, `end_reason`, `event_seq`,
`events`, `policies`, `policy_version`, `created`.

**Phase encoding:** `phase` is an integer. `1` is the palace phase,
`2` is the succession phase. Events and results carry the same
encoding.

Each player (`state["players"][pid]`) holds: `gate_id` (a seat id
`P0`..`P3`), `gate` (cell), `pos` (cell), `equipment` (sorted item
names), `prestige` (integer), `support` (faction names), `turns`,
`stats` (telemetry counters), `abilities_used` (ability type to item).

Hidden state: the item under each unrevealed treasure entry
(`district_equipment` minus `revealed`), the faction under each
unsearched card space (`faction_sites` minus `faction_sites_revealed`),
and future dice. Everything else is public.

## 5. Observation vocabulary

`observe(state, player)` returns, for the active player only:

- `gameplay_mode`, `game_id`, `seed`, `engine_version`, `status`,
  `phase`, `round`, `turn_id`, `active_player`, `viewer`,
  `movement_die` (the summed roll), `movement_dice` (each die),
  `turn_order`, `gate_assignments`.
- `board`: `width`, `height`, `blocked`, `gates` (by seat id),
  `districts` (letter to entry cell), `guard_posts`, `checkpoint`,
  and in the succession phase either `card_spaces`
  (`candidates` plus everything already `revealed`) or `factions`
  (fixed meeting-place cells, used when no blind deal exists).
- `revealed_districts`: district letter to revealed item.
- `prestige_cap`, `equipment_names`.
- `players[pid]`: `gate`, `gate_id`, `position`, `equipment`,
  `equipment_count`, `attack_bonus`, `defense_bonus`,
  `attack_vs_claimant_bonus`, `prestige`, `support`, `turns`.
- `pending_claim` (or `null`).
- `progress`: `first_challenger`, `players_with_full_equipment`,
  `claim_required_equipment`, `palace_max_rounds`,
  `succession_max_rounds`, `grace_full_rounds`, `support_cost`,
  `required_support`, `contest_cost`, `claim_window_rounds`,
  `proclaim_cost`, `duel_loser_cost`, and `transition_after_round`
  once the checkpoint is claimed.
- `legal_actions`: the same list `legal_actions(state)` returns.

## 6. Actions

Each action carries `kind`, `destination`, `path` (a deterministic
shortest path, tie-break north, east, south, west), `action_id`, and
where relevant `target`, `faction`, `district`, `contest_cost`, or
`spend_prestige`. One action per turn.

| Kind | Phase | Conditions |
| --- | --- | --- |
| `move` | both | Destination within this roll; at least one step. |
| `explore` | palace | Destination is a treasure entry whose item you do not own, or that is unrevealed. Grants the item; reveals the district to everyone. |
| `inspect` | both | Helmet unused: publicly reveal any one unrevealed district (palace) or unrevealed card space (succession), without moving. |
| `guard_post` | both | You moved onto a guard post and your Prestige is below the cap. Roll one die; 4+ earns 1 Prestige. |
| `duel` | both | You moved; the target's position is within `duels.range` of your destination. Against the standing claimant, pay the contest fee first. |
| `search_site` | succession | Destination is an unrevealed card space. Turns its card face up for everyone. |
| `gain_support` | succession | Destination holds a revealed faction you do not already have; pay `support_cost`. |
| `claim_checkpoint` | palace | You stand at the Peristyle, own all six items, and nobody has claimed yet. |
| `proclaim` | succession | You stand at the Peristyle, hold `factions_to_proclaim` support, no claim stands, and you can pay `proclaim_cost`. |
| `maintain_claim` | succession | Your own claim stands and you are still at the Peristyle. |

Duel resolution order: both sides roll one die; each side adds its one
best number bonus; the higher total wins; only on equal totals does
the lone pugio holder win, otherwise the attacker wins. The winner
earns 1 Prestige; the loser pays 1 Prestige to the bank, as much as
they hold. A won challenge against a claimant cancels the claim and
sends the claimant back to their gate unless an unused lorica
segmentata saves the square (the claim still dies).

Leaving the Peristyle by your own move cancels your own standing
claim. Equipment and support are never lost.

## 7. Events and the turn record

Each applied turn appends one record to `state["events"]`:

```json
{
  "event_seq": 16, "turn_id": 15, "round": 4, "phase": 1,
  "player": "P2", "movement_die": 5, "movement_dice": [2, 3],
  "action_id": "a0008",
  "action": {"kind": "explore", "destination": [12, 3], "path": ["...": "..."]},
  "dice_used": [],
  "events": [{"type": "district_revealed", "district": "B", "item": "scutum"}],
  "position_after": [12, 3], "prestige_after": 1,
  "equipment_count_after": 4, "reason": "open the nearest district"
}
```

`prestige_after` is the acting player's Prestige after the turn.
`dice_used` lists the dice the action itself rolled, in roll order.
`reason` is optional caller text and never affects play.

Event types: `prestige_earned`, `prestige_spent`,
`district_revealed`, `equipment_collected`, `explore_no_gain`,
`guard_post`, `duel`, `ability_used`, `card_space_revealed`,
`support_gained`, `first_challenger`, `claim_proclaimed`,
`claim_maintained`, `claim_response`, `claim_cancelled`,
`phase_transition`, `game_won`, `game_draw`. The
`phase_transition`, `game_won`, and `game_draw` events ride inside the
turn record that triggered them.

## 8. Result and end of game

`result(state)` reports: `outcome` (`win`/`draw`), `winner`,
`end_reason` (`survived_window`, `acclamation`, or
`succession_timeout`), `first_challenger`,
`palace_timeout`, `succession_timeout`, `rounds_palace`,
`rounds_succession`, `turns_palace`, `turns_succession`,
`total_turns`, `total_rounds`, `policies`, `turn_order`,
`gate_assignments`, per-player `players` metrics (final Prestige and
equipment, support, abilities used, telemetry counters,
`equipment_at_transition`, districts explored), and
`high_impact_events`.

`palace_timeout` is true when the palace phase ended at round 24 with
no checkpoint claim. `succession_timeout` is true when the succession
phase ended at round 24 with no standing claim (a draw).

## 9. Randomness and determinism

Five named xorshift32 streams live in `state["rng"]`: `gates` (gate
assignment), `order` (turn order, then the blind faction deal),
`equipment` (treasure shuffle and start-of-game reveals), `movement`
(the dice of each turn), `combat` (guard-post and duel dice). Each
stream starts from the seed mixed with a fixed salt, so the same seed
and action sequence always replay the same game. Observing never
advances a stream.

## 10. Built-in bots

Bots read only the public observation and choose only from
`legal_actions`. The registry is `engine.POLICY_NAMES`; `policies.py`
wraps it and `engine.choose_policy` does the choice. The nine bots in
the golden-trace pool (`tests/fixtures/golden/meta.json` `bot_pool`):

| Bot | Behavior |
| --- | --- |
| `balanced` | Follows the base ladder: claim and proclaim when able, gear up, secure support, fund Prestige. |
| `balanced_se` | The same ladder with the opposite shortest-path tie-break. |
| `greedy` | Collector profile: rushes the six-item checkpoint requirement. |
| `aggressive` | Funds Prestige through duels when income is wanted. |
| `random` | Samples a weighted action category first, then an action in it. |
| `collector` | Collector with fixed item preferences (lorica, scutum). |
| `early_support` | Skips gear and heads for the factions early. |
| `prestige_farmer` | Keeps a deep Prestige buffer; farms guard posts and duels. |
| `counterleader` | Duels the leading rival once that rival nears the proclamation requirement. |

`POLICY_NAMES` also contains `tactical`, a legacy name that behaves
like `balanced`. The golden pool does not use it.

## 11. Run directories

`write_run` keeps one game per directory:

```
runs/<game_id>/
  rules.snapshot.json   # the exact rules used
  metadata.json         # game id, seed, rules hash, turn order, policies, engine version
  state.json            # the full resumable state (private; agents must not read it)
  events.jsonl          # one line per turn record, append-only
  result.json           # written when the game finishes
```

Writes are atomic (temp file plus rename). `sim.py replay --verify`
rebuilds a finished game from `rules.snapshot.json` and `events.jsonl`
and compares events and result.

## 12. Command line (`sim.py`)

All commands print JSON on stdout; errors go to stderr with a nonzero
exit code. Run from the repository root.

```bash
python3 sim.py validate --rules rules/imperial-rivals-v0.10.2.json
python3 sim.py new --rules rules/imperial-rivals-v0.10.2.json --seed 42 \
  --out runs/demo --policies balanced,greedy,aggressive,random
python3 sim.py observe --run runs/demo --player P0
python3 sim.py act --run runs/demo --player P0 --turn-id 1 \
  --action-id a0001 --note 'open the nearest district'
python3 sim.py auto --run runs/demo
python3 sim.py batch --rules rules/imperial-rivals-v0.10.2.json --games 1000 \
  --seed-base 1000 --out results/baseline-demo
python3 sim.py report --input results/baseline-demo
python3 sim.py replay --run runs/demo --verify
```

`--policies` takes one name for all seats or four comma-separated
names in seat order `P0,P1,P2,P3`. `batch` writes `games.csv`,
`summary.json`, `experiment.json`, and sample game logs;
`--schedule experiment` rotates policies and gates across seeds
(`report.schedule_for`), the default `fixed` uses `--policies`.
`report` summarizes a batch directory; `compare.py` prints a markdown
table across batch summaries.

Supporting tools: `tools/table_seat.py` lets one human or agent play
one seat of a persistent run; `tools/obs.py` prints a condensed
observation for narrative playtests.

## 13. Model players

`candidate_actions.py` builds, from one public observation plus the
public rules file only: `project_observation` (a compact public
projection with an objective statement and `rule_summary`) and
`build_candidates` (a deterministic shortlist of at most 16 actions
with exact one-step probabilities and an exclusion audit). Arena
(`arena/`) feeds these projections to decision models; see
`arena/README.md`.

## 14. Golden traces

`tools/make_golden_traces.py` plays 200 seeded games (seeds
1000–1199) with the nine pool bots and records a **name-neutral**
trace per game: player, action verb, destination, target, dice, the
score of each seat, positions, items, support, claim state, and the
result. The fixtures live in `tests/fixtures/golden/`
(`traces.jsonl`, `meta.json`, `web-parity-baseline.txt`).
`tests/test_golden_traces.py` replays the same seeds and demands the
exact traces back, so renames cannot change behavior. Set
`GOLDEN_FAST=1` to check every fourth game only.

## 15. Web engine and parity

`web/` holds a browser port of the same game
(`succession-engine.js`, `succession-bots.js`, `engine.js`, `app.js`).
Its board data and rulebook text are generated from the rules file by
`tools/make_web_board.py`. Serve it locally with
`python3 -m http.server 8000 --directory web`.

## 16. Checks

```bash
python3 -m pytest -q                                   # Python suite
node tools/test_succession_engine.mjs                  # web engine mechanics
node tools/test_web_engine.mjs                         # web board-data contract
node tools/test_web_ui.mjs                             # UI (needs jsdom; else SKIP)
node tools/test_succession_parity.mjs                  # web vs Python, seeded games
cd arena && uv sync --extra decisions && uv run pytest -q
cd arena && uv run arena --match matches/bots.json     # a bots match, end to end
```

The Python suite needs `reportlab` and `pypdf` for the print checks.
The parity check replays seeded games against `engine.py` and matches
every legal action, die, and state.

## 17. Module map

| Path | Purpose |
| --- | --- |
| `engine.py` | Rules validation, state, legal actions, resolution, events, bots, run files. |
| `board.py` | Board graph, shortest paths, site lookups, six-block layout check. |
| `policies.py` | Bot name registry; dispatch into `engine.choose_policy`. |
| `candidate_actions.py` | Public projections and candidate shortlists for model players. |
| `report.py`, `compare.py` | Batch running, aggregation, and comparison. |
| `sim.py` | Command-line interface. |
| `rules/` | The shared rules file and its JSON schema. |
| `tools/` | Trace generator, print and web generators, seat and observation tools, Node checks. |
| `web/`, `print/`, `art/` | Browser game, printable kits, drawn assets. |
| `arena/` | Terminal app where decision models play the game. |
| `playtest/`, `tests/` | Human playtest protocol and the test suite. |
