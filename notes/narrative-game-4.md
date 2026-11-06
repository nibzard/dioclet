> **Engine caveat:** this game ran before the emperor-miss retreat
> bug was fixed (the miss-retreat to `[2,3]` was overwritten; see
> FINDINGS.md §6). Impressions that the retreat penalty "never
> fired" trace to that bug, not to the rules. Other observations
> stand.

# Narrative game 4 — the catch-up rule

Research date: 2026-11-06. Seed 4104, `rules_baseline.json`, run `runs/narr4`.
Personas: P0 Prima (racer), P1 Secunda (Glory grinder), P2 Tertia (duels
Prima), P3 Quarta (explorer). Replay verified.

## Outcome (runs/narr4/result.json)

- Winner: P3 Quarta, by two Emperor hits in round 5 of Level 2.
- Quarta was also the First Challenger, so `comeback_win=false`.
- 53 turns total: 36 in Level 1 (9 rounds), 17 in Level 2 (5 rounds).
- Auto-granted gear at transition: P1 got 4 items, P2 got 6 items,
  P0 and P3 got 0 (both had collected all six).
- Collected gear by hand: P0 6, P1 2, P2 0, P3 6.

## Comeback experience

- The auto-equip flattened Level 1 completely. Tertia explored nothing,
  dueled all game, and entered Level 2 with the same six items and the
  same 2 Glory as Prima, who had explored all six districts and won 7 of
  10 defended duels. Prima's whole Level 1 scorecard bought her nothing.
- The deflation is real but did not decide the game. Quarta, a full
  collector, won. Turn order (P3 first, from the seed) and Level 2 dice
  decided it, not the free gear. From Prima's seat the rule still feels
  unjust: 6 explores plus 10 duels defended equaled Tertia's zero effort.
- The two grace rounds created no tension. After the claim, three of four
  players sat at the Glory cap with full or soon-free gear, and pawn
  positions reset at transition. All they could do was duel for spite.
  Nine of the game's duels happened in rounds 6 through 9.
- The grace window helped only the First Challenger. Quarta sat at 1
  Glory after the +1 reward. She reached the cap by defending Secunda's
  spite duel. The chasers gained nothing from the free rounds.
- The first challenger's +1 Glory mattered. It let Quarta buy the
  peristyle seal and still keep one Glory. That token powered her first
  Emperor hit (+2 for 72% instead of 42%). Without it she likely arrives
  with one fewer purchase.
- The chasers could realistically win. Secunda bought a peristyle seal
  with ground Glory, rolled a 6 at the cellars, and hit the Emperor in
  the same round as Quarta. She attacked one seat later in the order.
  One missed Quarta roll and a Secunda hit would have ended the game the
  other way. The margin was a single die.
- Prima, the strongest Level 1 player, never reached the Emperor. She
  rolled 1 and 2 at the cellars, paid Glory for peristyle, and finished
  a full round behind. The catch-up plus seal luck can erase a leader
  without ever making the leader feel outplayed.
- Everyone bought the peristyle seal with Glory; nobody used the guard
  barracks seal. With a cap of 2, Glory is really one peristyle pass plus
  one Emperor swing. The grind role (Secunda) converted posts into exactly
  that, and it nearly won her the game.

Open question: would grace rounds feel different if Glory were not capped
at 2, or if positions carried into Level 2? Both changes would give the
chasers something real to do while the clock runs.
