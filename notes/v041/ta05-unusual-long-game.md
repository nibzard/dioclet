# ta05: the 26-round game (longest of Tournament A)

Source: `results/v041/games/ta05/` (decisions.jsonl, events.jsonl, result.json; rules.snapshot.json).
Reviewed 2026-11-07. All four seats: OpenAI Decisions (`gpt-6-luna`), seed 5105.

**Outcome:** P0 won by Emperor kill at turn 104. 26 rounds / 104 turns: Level 1 = 22 rounds
(88 turns), Level 2 = 4 rounds (16 turns). P0 was first challenger (t83), needed 2 Emperor
attempts (2 hits, t97 and t104, both with 1 Glory spent). P1 hit the Emperor once (t103).
P2 and P3 never attacked; each finished with 1 Glory and 2 seals in hand.

## Where the extra ~10 rounds went

- Split: Level 2 was fast (4 rounds, near the ~3-round minimum). The whole overrun sits in
  Level 1: 22 rounds against a Tournament A median of 11.5 (range 9 to 19), and only 2 rounds
  under the `level1.max_rounds = 24` timeout. `phase1_timeout` stayed false by two rounds.
- Exploration itself was normal. Districts A, B, D, E were revealed by round 5, C at t35 (R9).
  District F at [3,3] held scutum, the last of the six items, and stayed unrevealed until t80.
- From t46 (R12) all four players sat at 5 of 6 items. Scutum had to be in F by elimination.
  For the next 35 turns (R12 to R20) nobody explored it: 29 moves, 5 duels, 1 explore. The
  one explore, t80 by P0 (p=0.30, conf=0.20), revealed scutum and ended the stall.
- Players repeatedly arrived on F and declined it. P1 moved onto [3,3] as a plain move at
  t47 and t66; P2 did the same at t78. Each time the candidate "Move to district F
  (unrevealed) and explore it" was offered and rated p=0.06 to 0.07.
- After the reveal the herd landed at once: P2 explored F at t81, P3 at t87. P0 claimed the
  checkpoint at [2,2] on t83 (conf=0.47, its first confident turn of the game) and the
  phase transition fired at t88.
- Level 2 was a clean race: all four bought the peristyle seal with Glory (t89 to t91, t98),
  P0 and P1 rolled cellars (t93, t94), P0 attacked with Glory at t97 (hit) and again at t104
  (win). P2 was attack-eligible from t99 but rolled a movement die of 1 on both its turns
  (t96, t102) and could not reach the chamber at [2,4] from [1,2]. P3 qualified at t101 and
  never got another turn.

## Diagnosis

- Not mutual interference. Zero guard-post attempts (the action was offered 70 times), zero
  displacements, zero Glory stolen. Only 10 duels total, 5 inside the stand-off.
- Wasted motion is the dominant cause. 29 of 35 stand-off turns were moves (38 movement steps)
  while the only progress action was legal every turn. Destinations collapsed onto three
  adjacent nodes: [2,4] x11, [2,3] x10, [3,3] x6. Players milled in one corner of the board.
- Caution showed up as flat distributions, not as deliberate waiting. Mean confidence was
  0.18 to 0.19 in Level 1 versus 0.41 in Level 2; the chosen action was rated below p=0.15 on
  15 turns. The chosen action matched the model's own argmax on 101 of 104 turns, so the model
  always took its top pick; the top pick itself was noise spread across ~16 near-tied moves.
- The explore-F candidate never ranked above p=0.10 during the stall. It spiked to 0.21 to
  0.31 only on t15, t16, t35, and t80, that is when the actor already stood on the unrevealed
  district. The players could rank "explore where I stand" but not "walk to the last unknown".
- Glory hoarding at the cap of 2. P0, P2, and P3 each wasted one duel win at the cap
  (`glory_wasted_at_cap = 1`), and three seats sat capped from about R13. Stalling had no
  payoff either: Glory carries into Level 2, and triggering the transition costs nothing.
  The delay was drift, not strategy.
- Herd behavior twice. Pre-reveal, all four seats packed the same [2,3]/[2,4]/[3,3] corridor
  for seven rounds and piled duels on P0 (defended at t56, t58, t69). Post-reveal, three of
  four seats converged on F within eight turns.
- Biggest single time sink: the district-F stand-off, t46 to t79. Sharpest evidence: t47, t66,
  and t78, where a player spent a full turn walking onto F and chose `move` over the explore
  sitting in the same candidate list.

## Verdict

Mostly an artifact of four flat-distribution AI players simultaneously failing to rank the one
progress action for ten rounds, with one design amplifier: a single unrevealed district can
gate the level transition, and the capped Glory economy gives no incentive to break the stall.
