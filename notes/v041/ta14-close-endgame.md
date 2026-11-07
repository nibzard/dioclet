# ta14: the close Emperor endgame (V0.4.1, all-seats Decisions)

P0 won by Emperor at turn 91 (round 4 of phase 2) after 91 turns, 23 rounds,
and 14 duels. Every seat hit the Emperor at least once: P0 2/2, P1 1/1,
P2 1/1, P3 1/1. Turn order P2, P1, P0, P3; P3 never received a round-4 turn.

## Turn-by-turn reconstruction (turns 77-91)

Seal race first, then five attacks. Seat order rotated each round.

| Turn | Player | Action | Chance / roll | Result |
|------|--------|--------|---------------|--------|
| 77 | P1 | Seal, peristyle, spend 1 Glory | 100% (paid) | Seal (order 1) |
| 78 | P0 | Seal, cellars, roll | 67% | Roll 4: seal (order 1) |
| 79 | P3 | Seal, cellars, roll | 67% | Roll 5: seal (order 1) |
| 80 | P2 | Seal, peristyle, spend 1 Glory | 100% (paid) | Seal (order 1) |
| 81 | P0 | Seal, peristyle, spend 1 Glory | 100% (paid) | Seal (order 2), 0 Glory left |
| 82 | P3 | Seal, peristyle, spend 1 Glory | 100% (paid) | Seal (order 2), 0 Glory left |
| 83 | P2 | Seal, cellars, roll | 67% | Roll 1: FAILED |
| 84 | P1 | Seal, cellars, roll | 67% | Roll 2: FAILED |
| 85 | P3 | Emperor, spend 1 Glory (+2) | 72%, chosen at 0.56 (conf 0.53) | 8 vs 6: HIT 1 |
| 86 | P2 | Seal, cellars, roll | 67%, chosen at 0.33 | Roll 6: seal (order 2) |
| 87 | P1 | Seal, cellars, roll | 67%, chosen at 0.67 | Roll 4: seal (order 2) |
| 88 | P0 | Emperor, spend 1 Glory (+2) | 72%, chosen at 0.83 (conf 0.82) | 8 vs 5: HIT 1 |
| 89 | P2 | Emperor, spend 1 Glory (+2) | 72%, chosen at 0.98 (conf 0.98) | 8 vs 4: HIT 1 |
| 90 | P1 | Emperor, spend 1 Glory (+2) | 72%, chosen at 0.65 (conf 0.63) | 10 vs 7: HIT 1 |
| 91 | P0 | Emperor, NO Glory left to spend | 42%, chosen at 0.84 (conf 0.83) | 6 vs 3: HIT 2, game won |

Turn 91 was the decider. The candidate text read "Attack the Emperor without
Glory; exact hit chance 42% (wins the game on a hit)". P0 put 0.84 on it. No
Glory option existed because its last Glory went into the turn-88 attack. The
dice gave player 4 (score 6) against Emperor 1 (score 3).

## Findings

- The race was recognized by everyone. From turn 85 on, no player picked a
  move, seal, or duel over an available Emperor attack, and each earlier
  turn priced seals as the gate to attacking. P2 hit peak clarity at turn 89
  (0.98 on the 72% attack).
- Interference was available and declined. Every endgame turn listed duels
  against Emperor leaders ("target has 1 Emperor hits, 0 Glory"), priced at
  0.00 to 0.18. Duels could not remove hits and all targets held 0 Glory, so
  a duel only burned the attacker's own tempo.
- The miss-retreat rule never bit. All five Emperor attacks hit, and no
  emperor_miss or retreat event exists anywhere in the log. The rule stayed
  theoretical in this game.
- What actually cost the race: the two cellar seal failures. P2 (roll 1) and
  P1 (roll 2) lost round 2 turns 83-84, so their first attacks came in round
  4 instead of round 3, one round behind P0 and P3.
- P0's edge was Glory timing plus one lucky path. It rolled cellars at 67% on
  turn 78 (0.48 over paying Glory, 0.34) and saved a Glory, then spent that
  Glory on the turn-88 attack at 72% instead of 42%. P1 and P2 paid Glory at
  the peristyle first and had none to save.
- Seat order decided who could close. Round 4 ran P2, P1, P0, P3. P2 and P1
  tied the hit count at one, then P0 took the win slot before P3, the only
  other player on one hit, ever acted. P3, first to hit at turn 85, was
  denied a second swing by the rotation alone.
- Pure dice luck also ran hot. The chance of this exact 72/72/72/72/42
  all-hit sequence is about 6%, so no strategy was punished by a miss.

Verdict: initiative first (P0's slot before P3 in round 4), skill second
(saved Glory into the 72% attack), dice third (no attack missed).
