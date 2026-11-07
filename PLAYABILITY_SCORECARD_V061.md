# PLAYABILITY_SCORECARD_V061.md — accessibility and depth

Two dimensions, scored separately. Evidence type is marked:
**[M]** measured offline (simulator, this cycle or earlier),
**[S]** structural (countable from the rules text),
**[P]** pending, answerable only by human playtest. No human session
has been played; nothing below pretends otherwise.

## Accessibility

| Question | Answer | Evidence |
|---|---|---|
| Can a six-year-old follow the basic turn? | Plausibly yes: one turn is three steps, and the dice are separate by purpose (two for feet, one for fights) | [S][P] |
| Can an older first-time player read the board? | The board has three visual classes only: street circles, building blocks, marked specials. The quick-reference fits one page | [S][P] |
| Is two-dice movement easy? | Sum two ordinary dice, move up to that far. Familiar from mainstream family games | [S][P] |
| Are the required actions memorable? | Seven action types exist, but a turn offers at most a handful where you stand; the rulebook states each in one sentence | [S][P] |
| Are there too many exceptions? | Three exceptions total (stop-on-entry to take a card; guard posts and duels always need a move; the Emperor miss step-back). No powers, no phases inside a turn | [S] |
| Is game duration right for a family? | Median 26 rounds, p90 32; with 48% walking turns this is the main open risk | [M][P] |
| Does the game avoid elimination and skipped turns? | No elimination; no player ever loses a turn under the adopted rules (the lost-turn penalty was rejected in V0.5) | [M] |
| Walking share | 48.1% of all turns are pure movement (small board: 4.6%). Mitigation is pace, not rules: median 4 steps used of an average-7 roll; something eventful happens on almost every consecutive turn somewhere on the board | [M] |
| First treasure | Median turn 4 globally: someone collects within the first round; early hook exists | [M] |
| Waiting between own turns | A player acts every 4th global turn; between two of a child's own turns, 1 to 4 other-player events occur (median 1) | [M][P] |

Accessibility verdict: the rule load is genuinely small (the teaching
script is eight sentences). The one open accessibility risk is the
walking share and total table time; both are human questions now.

## Strategic depth

| Question | Answer | Evidence |
|---|---|---|
| Multiple viable routes to winning? | Yes, at least two measured: full collection versus the Glory engine (fight for Glory, let the free gate gear finish the kit), plus seal-order choices (buy the safe Peristyle or roll two cheap sites) | [M] |
| Does Glory create trade-offs? | Yes: one currency, two sinks (safe seal, powered strike), cap 2 forces spending choices; close AI games turned on Glory timing | [M] |
| Does equipment matter? | Gear bonus feeds every fight and trial; collecting 3-5 versus 6 items changes duel odds by tiers | [M] |
| Do different openings emerge? | AI games produced Glory-engine, collector, and duelist openings; entry spread gives four symmetric-but-distinct starts | [M] |
| Is interaction worthwhile? | Partially: duels are frequent (8.1 per game) and pay Glory, but a duel still cannot slow a leader. This remains the one design gap, deliberately untouched this cycle per the brief | [M] |
| Can a trailing player recover? | 68% of wins are comebacks (2d6 arm, 1,000 games) | [M] |
| Reward skill without being predictable? | Policy choice explains most of the win spread (random wins 1-2% under the same rules); dice decide fights but not the race | [M] |
| Variation for repeated play? | Hidden treasure shuffle, first-claim race, duel webs, Glory timing; no two AI games alike in the qualitative studies | [M] |

## Improvement filter

Every proposed improvement must answer: what new meaningful choice
does it create, and what new rule must a player remember?

- **Leader bounty duel** (from V0.5): creates the choice "spend a
  turn fighting the leader". Cost: one sentence. Still untested;
  queued as its own experiment, not adopted.
- **Checkpoint requires 4 of 6 treasures**: creates the choice "race
  early or gear up". Cost: changes the meaning of the six-treasure
  quest. Needs its own arm; not adopted.
- Everything else examined this cycle (die changes beyond 2d6, caps,
  placements) tunes feel without adding a choice.

## What only humans can answer

The four playtest groups (children, family, gamers, older adults)
must answer: real table time, whether 48% walking turns feels like
movement or dead time, whether the city phase drags before the gate,
whether the Emperor finish excites, and whether anyone asks to play
again. Protocol: `playtest/protocol.md`.
