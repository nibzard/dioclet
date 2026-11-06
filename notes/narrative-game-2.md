> **Engine caveat:** this game ran before the emperor-miss retreat
> bug was fixed (the miss-retreat to `[2,3]` was overwritten; see
> FINDINGS.md §6). Impressions that the retreat penalty "never
> fired" trace to that bug, not to the rules. Other observations
> stand.

# Narrative playtest 2 — four duelist personas, seed 4102

Played 2026-11-06 via `sim.py observe` / `sim.py act`, one turn at a time.
Personas: P0 Ferox, P1 Lucanus, P2 Tigris, P3 Ursus. All four prefer duels
and Glory, but play to win. Run: `runs/narr2`, rules `rules_baseline.json`.

## Outcome (from runs/narr2/result.json)

- Winner: **P3 "Ursus"** by Emperor (2 hits), turn 55, round 14.
- 55 turns total: 40 in Level 1, 15 in Level 2. No phase timeout.
- First challenger was P1 Lucanus (round 8); he did not win
  (`comeback_win: true`).
- Final line for Ursus: cellars + barracks seals rolled for free,
  both Glory coins spent on Emperor attacks, 2 for 2 hits.

## How it felt

- **Duel availability was fine.** With four pawns on a 5x5 board, some duel
  was legal on almost every Level 1 turn. The move-at-least-one-step rule
  bit only twice (die rolls of 1 at a far corner), and even then duel
  endpoints existed. Availability was never the frustration.
- **The Glory cap of 2 was the biggest buzzkill.** Ferox went 4-0 in duels
  and three of those wins logged `glory_wasted_at_cap`. The engine kept
  telling our best brawler that his favorite action paid nothing. Late
  Level 1 duels became exhibition matches — fun in character, dead in
  mechanics.
- **Smart aggression beat pure aggression.** Lucanus opened with a
  heart-over-head duel (turn 6, no equipment edge) and lost 6-3. Ferox
  armed to three items first, then bullied Lucanus 7-3 with the +1 tier.
  The personas learned: duel with an edge, or farm a guard post.
- **Ties to the defender made equal fights feel rigged** against the
  attacker (41.7% to win an even duel). Tigris "won" a 3-3 roll-off purely
  on the tiebreak, which felt dramatic for him and cheap for Ferox.
- **Level 2 duels felt pointless.** A duel cannot remove hits, seals, or
  delay anyone. Once Ursus had one hit and one coin, no one could touch
  him. Ferox's only outlet was a pride duel on Lucanus while the bear
  strolled to the throne. The aggressors hated having no way to interfere.
- **Glory-spent Emperor attacks (about 92% to hit) made the endgame a
  purchase, not a fight.** Three players each spent a coin and hit on the
  same round. Ursus simply got there with two coins and two free seals.
  The Emperor never rolled high enough to punish a paid attack; the
  retreat rule never fired once.
- **Seals compressed into a purchase plus one free roll.** Three of four
  players bought the Peristyle, then rolled Cellars. Ursus alone rolled
  both seals free, and that coin advantage was the whole game. Seal paths
  felt same-y.
- **The first challenger bonus felt weak.** Lucanus traded it straight
  into a Peristyle purchase and still lost. The catch-up transition
  (everyone auto-equipped anyway, all Glory carried) erased most of the
  Level 1 race.
- **Pacing was snappy and satisfying.** 55 turns, about 14 rounds. No
  grind, no stall. The finish was sudden: three players at one hit, then
  one roll ended it — exciting to watch, hollow to lose.

## Open questions

- Should duels do something to an Emperor runner (delay, glory theft)?
- Should Glory above cap convert to anything, or cap at 3?
- Is the paid Emperor attack too reliable at +2?
