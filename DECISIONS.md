# DECISIONS.md — recorded interpretations of SPEC.md V0.1

Each decision below resolves an ambiguity or contradiction found while reading
SPEC.md and rules_baseline.json before implementation. Each has a test where
practical. No baseline rule values were changed.

- **D1 Explore on an unrevealed district whose hidden type the player already
  owns.** SPEC §5 makes unrevealed districts legal explore targets, and §6 says
  a district with owned equipment offers no explore action. Offering the action
  only when the hidden type is unknown would leak the secret mapping through
  `legal_actions`. Decision: the engine always offers `explore` on unrevealed
  districts; resolution reveals the district and grants nothing when the type
  is already owned (logged as `explore_no_gain`).
- **D2 Duels require movement.** §5 lists `duel` with "move distance ≥ 1" and
  permits zero-step actions only for explore, claim_checkpoint, attempt_seal,
  and attack_emperor. Decision: a stationary duel is never legal, even when a
  target is already within duel range at turn start. The player must move at
  least one edge (the destination may be any reachable cell within duel range
  of the target).
- **D3 Duels at the Glory cap stay legal.** §6 caps the reward but never makes
  the duel illegal. Decision: duels are always offered; a win at cap awards no
  Glory and is logged as Glory wasted at cap (a §12 metric).
- **D4 Effective Level 1 end round.** §6: finish round R, then
  `grace_full_rounds` more rounds, but transition "at whichever occurs first"
  when the max-round deadline also applies. Decision: when the checkpoint is
  claimed at round R, Level 1 ends after round
  `min(R + grace_full_rounds, level1.max_rounds)`. `phase1_timeout` is set only
  when no player claimed by the end of `level1.max_rounds`.
- **D5 Turn order.** One shuffle of the four seat ids drawn from the placement
  RNG stream at game creation; the same order continues in Level 2. Level 2
  starts a new full round with the first player of that order, round counter
  reset to 1.
- **D6 Glory pre-commit.** Peristyle `spend_glory` and Emperor `spend_glory`
  variants subtract Glory before any roll and never refund it on failure.
- **D7 Guard barracks equipment bonus.** Uses the same tier table as duels
  (`combat.equipment_bonus_tiers`; six items give +2).
- **D8 Emperor legality and variants.** `attack_emperor` requires at least
  `level2.required_distinct_seals` distinct seals and position at the chamber
  (move or stationary). Both `spend_glory=false` and `spend_glory=true`
  variants are offered exactly when Glory ≥ 1.
- **D9 action_id ordering.** Actions are sorted by kind name (alphabetical),
  then destination `[x, y]`, then target player id, then `spend_glory` (false
  before true). Ids are `a0001`, `a0002`, … regenerated per turn.
- **D10 Movement path.** Walk from start toward the destination, at each step
  taking the first neighbor in north, east, south, west order that reduces the
  shortest-path distance to the destination. On the V0.1 grid without walls
  this equals a Manhattan shortest path.
- **D11 auto_equip_at_transition=false is rejected.** SPEC §8 prefers
  rejection for V0.1; validation fails with a clear error.
- **D12 Diagram labels.** The "E/P1" label at `[4,2]` in the SPEC §3 diagram
  is the east gate, not district E. Gates come from `board.gates` in the JSON:
  P0 north `[2,0]`, P1 east `[4,2]`, P2 south `[2,4]`, P3 west `[0,2]`.
- **D13 random policy category weights** (configurable constant in
  policies.py): claim_checkpoint 4, explore 3, attempt_seal 3, attack_emperor
  3, duel 2, guard_post 2, move 1.
- **D14 Bot randomness isolation.** Only the `random` policy rolls dice; its
  private RNG is seeded from the game seed and never touches engine RNG
  streams, so bot choices cannot alter game dice. All other policies are
  deterministic given the observation.
- **D15 Glory accounting for rewards at cap.** Guard-post, duel-win, and
  first-challenger rewards that cannot be paid because of the cap are logged
  (`glory_wasted_at_cap`) and counted in reports.
- **D16 Comeback win definition.** A win by any player who is not the First
  Challenger (the Level 1 checkpoint triggerer) counts as a comeback win in
  the §12 metrics.
- **D17 Narrative-game orchestration.** SPEC §9 sketches four parallel
  role-playing subagents. For the five qualitative games, one subagent hosts
  all four seat personas and drives the same single-writer CLI loop
  (`observe` → `act`, one action per turn). This preserves the information
  boundary because every `observe` field is public knowledge for all seats;
  the only hidden data (equipment mapping, future dice) never appears in an
  observation, and the subagent is forbidden from reading `state.json`.
  Four separate seat agents remain fully supported by the same CLI.
- **D18 Duel tie knob (V0.2).** `combat.tie_goes_to_defender` may now be
  `false`; a tied duel then awards the attacker the win. The original V0.1
  hard rejection is lifted because the baseline showed attacker wins of
  only 38% (FINDINGS.md §3) and the game owner made ties-to-attacker the
  priority-1 experiment. Guard barracks ("strictly higher") and Emperor
  ("ties go to Emperor") contests are unchanged.
- **D19 Rotating first player (V0.2).** Optional top-level key
  `turns.rotate_first_player_each_round` (absent in the baseline, default
  `false`). When true, each full round starts one seat later in the base
  seeded order (round r starts at base position r mod 4). Level 2 restarts
  from the base order (`round_start` reset to 0 at the transition).
  Observations and results report the effective order of the current
  round, so turn-position win rates measure the final round's seating.
- **D20 Emperor-miss retreat fix.** Movement now resolves before the
  action outcome inside `apply_action`, so the retreat to `[2,3]` after a
  failed Emperor attack is no longer overwritten by the action
  destination. Found by three narrative playtest agents; covered by a
  strengthened test and a `check_invariants` rule.
- **D21 Duel Glory theft (V0.3).** Optional `combat.duel_glory_theft`
  (default false). When true, the winner's duel reward comes from the
  loser, not the bank: the loser pays 1 Glory (floor 0) and the winner
  keeps it subject to the cap; any overflow is logged as wasted. A duel
  against a Glory-empty loser pays nothing at all. The standard
  `glory.duel_win_reward` bank payment is replaced, not added.
- **D22 Duel displacement (V0.3).** Optional `combat.duel_displacement`
  (default false). When true, the duel loser's pawn is moved to the
  retreat node `[2,3]` regardless of level. This is the tested "blocking
  move": it can evict a player from the Emperor chamber.
- **D23 Duel lost turn (V0.3).** Optional `combat.duel_lost_turn`
  (default false). When true, the loser forfeits their next turn. The
  skip is processed in `_advance` before the turn starts: no movement die
  is rolled, a `skip_turn` record is appended, and the turn counts as the
  player's turn for the round. The pending skip is public information in
  observations; `skip_turn` records are regenerated (not applied) during
  replay.
- **D24 V0.3 experiment base.** `rules_v03_base.json` is the adopted
  V0.2 package: attacker-wins-duel-ties, `grace_full_rounds: 1`,
  rotating first player. V0.3 variants flip exactly one duel-consequence
  knob on top of it. Bot policies stay frozen across all experiments so
  rule effects are not confounded with strategy changes.
- **D25 V0.4 Decisions player boundaries.** The OpenAI Decisions policy
  receives only `engine.observe` output plus a projection and features
  computed from it and the public rules file; hidden state never
  reaches a request (sentinel-tested). One legal action takes no API
  call (the choice API needs ≥2 options). Candidate shortlists keep
  every mandatory action and distinct duel target, group ordinary
  moves, and escalate the cap rather than dropping wins. Provider
  metadata lives in `decisions.jsonl`, never in engine state. In the
  decision counters, `attempted` includes the turn blocked by a budget
  cap; `budget.calls` counts requests actually sent. Live variance
  note: openai SDK 2.21.0 lacks `client.decisions`; 3.46.0 is the
  first version verified to support it.
- **D26 Real-board district entries (V0.6).** Designer confirmation
  2026-11-07: the pale blue circles are the entry spaces into the six
  neighborhood blocks; a player stops on the entry to take the card.
  Decision: one entry per neighborhood, placed on the adjacent street:
  A `[0,3]`, B `[9,3]`, C `[18,3]`, D `[0,9]`, E `[9,9]`, F `[18,9]`.
  Block interiors are removed from the movement graph through the new
  optional `board.blocked` list; validation rejects a blocked special
  cell and any site unreachable from gate P0.
- **D27 Real-board checkpoint placement (V0.6).** The printed purple
  circle sits at the right-hand internal intersection, three spaces
  east of the board midline and closer to the east gate. The measured
  gate fairness (±3%) rests on a central placement, so the simulation
  adds the historical north-south cardo (the real palace's central
  street) as street column x=9 and places the checkpoint and Peristyle
  at the center crossing `[9,6]`. Recommendation to the designer: add
  the cardo lane, or at minimum move the purple circle three spaces
  west onto the midline. The rectangle keeps a residual asymmetry
  (north/south gates 6 spaces from the checkpoint, east/west 9);
  the batch measures whether it matters.
- **D28 Real-board Level 2 and guard posts (V0.6).** Designer
  confirmation: Level 2 has no map yet; historically the cellars
  mirrored the palace level and the Emperor's quarters were in the
  palace's southern half. Decision: keep the tested same-cell mapping:
  Cellars at district A `[0,3]`, Barracks at C `[18,3]`, Peristyle at
  the checkpoint `[9,6]`, Emperor chamber at the south gate `[9,12]`
  (P2's gate, as in every prior version), retreat one step north
  `[9,11]`. Guard posts: four, on the west and east edges near the
  corners `[0,2]`, `[18,2]`, `[0,10]`, `[18,10]`, matching the V0.1
  placement class (side edges, between corner and gate).
- **D29 Real-board pacing measurement (V0.6).** `rules_v06_realboard.json`
  changes exactly one knob versus `rules_v03_base.json`: the board
  graph (107 street spaces versus 25). The movement die (d6), duel
  range (2), and both phase round caps (24) stay at their tested
  values so the first measurement is clean. The V0.5 Level 1 cap of 16
  rounds is not carried over: it was derived from small-board pacing
  and will be re-derived from the new round distribution. Tuning (die
  size, ranges, caps) happens only after this baseline reports.
- **D30 Movement dice count (V0.6, user proposal 2026-11-07).** The
  movement roll sums `movement.dice_count` dice of `die_sides`
  (default 1; validation requires an integer >= 1). Two six-sided
  dice for movement is the tested real-board setting: average 7
  steps keeps the city phase finishable. Challenge, duel, and
  Emperor rolls always use a single die of `die_sides`, so all
  combat probabilities are unchanged. `replay --verify` now ignores
  the `engine_version` field when comparing results; it is run
  metadata, not game content (caught after the 0.1.0 -> 0.1.1 bump,
  which had falsely failed verification of older runs).
- **D31 Real-board content placement (V0.6, measured).** Content
  placement is a fairness lever as strong as any rule knob; both
  placements inherited from the physical description broke a gate:
  all six entries on the west/east streets gave those gates 44% each
  (north/south 6-12%), and both roll-seal sites on the north street
  gave north 32% (first-challenger rates were equal, so the skew
  lives in Level 2 travel). Adopted placement: Level 1 entries on
  the north street (2), south street (2), and cardo (2) - measured
  first-challenger rates 181/152/175/152 per gate; Level 2 seal
  sites in a triangle (cellars northwest `[3,0]`, barracks southeast
  `[15,12]`, peristyle center `[9,6]`), emperor at the south gate.
