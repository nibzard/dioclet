# Plan: one game, one rules file, the printed names

Status: proposal, 2026-11-16. Nothing in this plan is done yet.

## Goal

The code, the rules JSON, the browser game, the print tools, and Arena must
describe the game that the printed kit describes: **Imperial Rivals: 305 AD,
V0.10.2**. They must use the names that the print uses.

The game mechanics do not change. A golden-trace test proves this (Phase 0).

## Decisions

1. **No backward compatibility.** Old run directories, old rules files, and
   old experiment results do not need to load or replay after this work.
2. **Remove the V0.1 Emperor game.** The Emperor boss fight, seals, cellars,
   the retreat, the guard barracks, Emperor hits, and the classic
   `engine.py` rules go. The repository has one game: the succession game.
3. **The print is the reference.** When the code and the print use
   different names, the code changes. The source for this plan is
   `print/bw/imperial-rivals-305ad-rulebook-A4-BW.pdf` and the quick
   reference, both V0.10.2.
4. **History stays as it is.** `notes/`, `DECISIONS.md` entries D1–D53,
   versioned `docs/findings/FINDINGS_V*.md`, and `reports/*.html` record
   what was true when they were written. Do not rename terms in them. Git
   history keeps the removed code and data.

## Audit: the JSON against the print

All mechanical values in `rules_v0102_bigboard.json` agree with the print.
These problems exist:

| Problem | Where | Examples |
|---|---|---|
| Old game name | `game_name` | "Diocletian's Palace: Six Treasures" |
| Old currency name | `glory` section, keys, state, events | `glory.cap`, `glory_posts`, `spend_glory`, `glory_after` |
| Two names for one value | event log | `glory_after` (palace) and `prestige_after` (succession) |
| Emperor-game keys that the succession game does not read | `combat`, `level2`, `board.level2_sites`, `logging` | `emperor_bonus`, `emperor_hits_to_win`, `imperial_guard_bonus`, `glory_attack_bonus`, `cellars_success_min_roll`, `peristyle_success_min_roll`, `peristyle_glory_cost`, `required_distinct_seals`, `level2_sites` |
| Keys that exist only to pass the V0.1 validator | `succession.py:116-120` builds a `legacy` copy for `engine.validate_rules` | `equipment_bonus_tiers` (must be all 0), `auto_equip_at_transition` |
| Settings that contradict the print | `succession` | `support_in_city: true` (`blind_support` silently overrides it, `succession.py:531`) |
| Confusing names | `succession` | `challenge_cost: 1` is the price of a switched-off bonus option; the real fee is `contest_cost` |
| Data that only a validator reads | `succession.factions` | palace cells for factions; the cards go on `board_level2.support_sites` |

## Terminology

| Print | Old code and JSON | New code and JSON |
|---|---|---|
| Imperial Rivals: 305 AD | Diocletian's Palace: Six Treasures | `Imperial Rivals: 305 AD` |
| Prestige | glory, prestige (mixed) | `prestige` |
| guard post | glory post | `guard_post` |
| palace phase, palace map | level 1, `board` | `palace` |
| succession phase, succession map | level 2, `board_level2` | `succession` |
| treasure entry, district (A–F) | district | `treasure_entries` (map), `district` (A–F letter) |
| card space | support site | `card_space` |
| contest fee | `contest_cost` | `contest_fee` |
| claim the checkpoint | claim checkpoint | `claim_checkpoint` (no change) |
| proclaim, maintain the claim, claim window | same | no change |
| emperor (the title of the winner) | Emperor (a boss piece) | only the win title |

## The new rules file

One file: `rules/imperial-rivals-v0.10.2.json`. One schema:
`rules/rules.schema.json`. The engine and Arena use the same schema. The
engine validator requires every key and rejects unknown keys. No value is
supplied by code.

The file keeps every number that a designer can tune in the printed game.
It does not keep switches for mechanics that the print does not have.

Proposed shape (values are the V0.10.2 values):

```json
{
  "game": {"name": "Imperial Rivals: 305 AD", "rules_version": "0.10.2",
           "players": 4},
  "turns": {"rotate_first_player_each_round": true},
  "movement": {"dice": 2, "die_sides": 6, "allow_early_stop": true,
               "pass_through_pawns": true},
  "treasures": {"items": ["pugio", "pilum", "galea", "scutum", "gladius",
                          "lorica_segmentata"],
                "start_face_up": 2,
                "abilities": {"gladius": {"type": "attack_bonus", "value": 1},
                              "...": "..."},
                "bonus_per_side": "best"},
  "prestige": {"cap": 3, "guard_post_min_roll": 4, "guard_post_reward": 1,
               "duel_win_reward": 1, "duel_loss_penalty": 1},
  "duels": {"range": 2, "tie_winner": "attacker"},
  "palace": {"max_rounds": 24, "checkpoint_items_required": 6,
             "rounds_after_checkpoint": 1, "map": {"...": "..."}},
  "succession": {"max_rounds": 24, "support_cost": 1,
                 "factions_to_proclaim": 2, "contest_fee": 1,
                 "claim_window_rounds": 2, "proclaim_cost": 0,
                 "faction_cards": {"factions": ["army", "officials", "elites"],
                                   "empty": 3},
                 "gate_assignment": "random", "map": {"...": "..."}}
}
```

Each map has `width`, `height`, `buildings` (with doors), `gates` (compass
names), `peristyle`, and `guard_posts`. The palace map also has
`treasure_entries` (A–F). The succession map also has `card_spaces`.

The exact key list is settled in Phase 2 against the code paths that remain.

## What goes

**Code paths** (the print does not have these mechanics):

- the Emperor game in `engine.py`: Emperor, seals, cellars, retreat, guard
  barracks, Emperor hits, `attack_emperor`, `attempt_seal`, equipment count
  tiers, auto-equip at the change
- succession switches that are off in V0.10.2: support in the palace phase
  (`support_in_city`), open faction sites (`blind_support: false`), the
  paid challenge bonus (`challenge_bonus`, `challenge_cost`),
  `challenge_radius`, `reset_positions`, `gate_rotation`, `ability_stacking:
  "sum"`, `set_completion_reward`, `first_challenger_reward`
- the `legacy` rules copy and the V0.1 validator

**Files** (superseded; Arena or git history replaces them):

- `rules_baseline.json`, `experiments/rules/*.json`, `experiments/`
- the V0.4 model player: `ai_driver.py`, `decisions_policy.py`,
  `decisions_config.json`, `requirements-decisions.txt`, `tournament.py`,
  `analyze_v041.py`, and their tests (Arena replaces them)
- one-time experiment scripts in `tools/`: `v09_*`, `v10_*`,
  `succession_experiments.py`, `autoresearch_run.py`, `run_programme.py`,
  `mirror_batch.py`, `contest_audit.py`, `live_contest_audit.py`
- `arena/rules/v0102.json` and `arena/rules.schema.json` (Arena uses the
  shared file)

**Stays:** `sim.py` (validate, new, observe, act, auto, batch, report,
replay), `report.py`, `compare.py`, `board.py`, `candidate_actions.py`,
`policies.py`, `tactical_policy.py`, `tools/table_seat.py`, the web game,
the print tools, and Arena.

## Phases

Each phase ends with all tests passing and one commit. Do not start a phase
before the previous phase is green.

### Phase 0: Golden traces (before any change)

- Play 200 seeded games with the current engine and a mix of the built-in
  bots. Record a name-neutral trace for each turn: player, action kind,
  destination, target, dice, Prestige of each player, positions, items,
  support, claim state, and the result.
- Commit the traces as test fixtures, and a test that replays the same
  seeds and compares.
- Record the current web parity result (`tools/test_succession_parity.mjs`)
  as a baseline.

Exit: the trace test passes on the current code.

### Phase 1: One engine

- Move the succession game into `engine.py`, so that `engine.py` is the
  game. Keep its public API: `new_game`, `observe`, `legal_actions`,
  `apply_action`, `result`, `write_run`, `load_run`, `rules_hash`.
- Delete the Emperor game, the `gameplay_mode` dispatch, and
  `succession.py`.
- Delete the tests for the Emperor game.

Exit: golden traces equal; all remaining tests pass.

### Phase 2: The new rules file and validator

- Write `rules/rules.schema.json` and `rules/imperial-rivals-v0.10.2.json`.
- Write one strict validator in the engine. Delete the `legacy` copy.
- Remove the switches listed under "What goes" and their code paths.
- Delete `rules_v0102_bigboard.json`. Point `sim.py`, the web build, the
  print tools, and Arena at the new file.

Exit: golden traces equal; a test makes sure that the schema and the
validator accept the same keys.

### Phase 3: Prestige and the print names in the engine

- Rename in state, events, observations, and actions: `glory` → `prestige`,
  `spend_glory` → `spend_prestige`, `glory_posts` → `guard_posts`,
  `glory_after` → `prestige_after`, level 1/2 → palace/succession, support
  sites → card spaces.
- Update `candidate_actions.py`, `policies.py`, `tactical_policy.py`,
  `report.py`, `compare.py`, `board.py`, and `sim.py`.

Exit: golden traces equal (the trace is name-neutral); `rg -i glory` finds
nothing in code outside the history folders.

### Phase 4: Web game

- Update `web/succession-engine.js`, `web/succession-bots.js`,
  `web/engine.js`, `web/app.js`, `web/style.css`, and
  `tools/make_web_board.py`. Regenerate `web/board-data.js`.
- The web game has no Emperor code (`attack_emperor` and `attempt_seal`
  occur only in `engine.py`), so this phase only renames.

Exit: `node tools/test_succession_parity.mjs`, `test_web_engine.mjs`, and
`test_web_ui.mjs` pass.

### Phase 5: Print tools

- Update `tools/make_a4_print_kit.py` and `tools/make_print_pack.py` to
  read the new file and names. Regenerate the kit.
- Compare the text of each new PDF with the old PDF. The text must be the
  same, except where the old text was wrong.

Exit: print tests pass; the PDF text differences are reviewed.

### Phase 6: Arena

- Arena loads `rules/*.json` from the repository root and uses the shared
  schema. Delete the Arena copies.
- Update the stream labels (`+glory` → `+prestige`) and the README.
- Bump the log schema to `arena-match-v2`.

Exit: Arena tests pass; a bots match plays to the end.

### Phase 7: Delete superseded files

- Delete the files listed under "What goes" and their tests.
- Fix the links in `README.md` and `programme.md`.

Exit: all tests pass; no link points at a deleted file.

### Phase 8: Documents

- Rewrite `SPEC.md` so that it agrees with the printed rulebook.
- Update `README.md` (versions table, commands, project map).
- Add decision D54 to `DECISIONS.md`: one game, the print names, the
  Emperor game removed. Do not change D1–D53.
- Update `playtest/protocol.md`.

Exit: `rg -i "glory|emperor_|seal|cellars"` finds matches only in the
history folders.

## Checks that run after each phase

```bash
python3 -m pytest -q              # Python suite
node tools/test_succession_parity.mjs
node tools/test_web_engine.mjs
node tools/test_web_ui.mjs
cd arena && uv run pytest -q && uv run arena --match matches/bots.json
```

## Risks

- **A silent change of mechanics.** The golden traces catch it. If a trace
  differs, stop and find the cause. Do not update the fixtures to make the
  test pass.
- **The web port drifts from Python.** The parity test runs in Phases 3–6.
- **The print kit changes by accident.** Phase 5 compares the PDF text.
- **Removed switches were still useful for experiments.** Git history
  keeps them. A new experiment adds a switch again, with a test.

## Questions for Niko

1. Delete the V0.4 model player (`ai_driver.py`, `tournament.py`, and the
   other files listed), because Arena replaces it?
2. Keep `sim.py batch`, `report.py`, and `compare.py` for balance runs?
3. The rules file name and folder: `rules/imperial-rivals-v0.10.2.json`?
