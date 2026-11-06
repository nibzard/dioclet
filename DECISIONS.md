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
