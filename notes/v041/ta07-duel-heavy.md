# ta07: the duel-heavy game (14 duels in 73 turns)

Outcome: P0 wins by Emperor (hits at turns 70 and 73; `comeback_win`). All four
seats run the OpenAI Decisions policy (`gpt-6-luna`). P2 is first challenger at
turn 44; phase 2 starts at turn 48 and auto-equips all seats to 6 items (+2).

Per-seat duel records (result.json): P0 initiated 3, won 3-0 attacking, was
never attacked, and went 2/2 on Emperor — won. P1 initiated 2 (2-0 attacking),
defended 12 (4-8), Emperor 1/4. P2 initiated 3 (2-1), defended 1 (0-1), no
Emperor tries. P3 initiated a game-high 6 (3-3), defended 1 (0-1), no tries.

## The duel war

Chances: 58% = equal equipment (ties to the attacker), 72% = attacker one
tier up. "Conf" is the model's stated confidence on the pick.

| Turn | Round | Attacker -> defender | Chance | Conf | Score | Glory |
|------|-------|----------------------|--------|------|-------|-------------------|
| 11 | 1-r3 | P1 -> P2 | 58% | 0.10 | 6-5 P1 | P1 +1 |
| 13 | 1-r4 | P3 -> P1 | 58% | 0.15 | 2-4 P1 | P1 +1 (cap 2) |
| 14 | 1-r4 | P1 -> P3 | 58% | 0.23 | 1-1 tie P1 | wasted at cap |
| 19 | 1-r5 | P0 -> P1 | 72% | 0.11 | 2-2 tie P0 | P0 +1 |
| 26 | 1-r7 | P3 -> P1 | 58% | 0.12 | 3-6 P1 | wasted at cap |
| 45 | 1-r12 | P3 -> P1 | 58% | 0.21 | 2-3 P1 | wasted at cap |
| 47 | 1-r12 | P2 -> P1 | 72% | 0.16 | 4-4 tie P2 | P2 +1 |
| 60 | 2-r3 | P2 -> P1 | 58% | 0.34 | 4-5 P1 | P1 +1 |
| 61 | 2-r4 | P3 -> P1 | 58% | 0.13 | 7-4 P3 | P3 +1 |
| 63 | 2-r4 | P2 -> P1 | 58% | 0.42 | 7-5 P2 | P2 +1 |
| 64 | 2-r4 | P0 -> P1 | 58% | 0.27 | 7-6 P0 | P0 +1 |
| 67 | 2-r5 | P0 -> P1 | 58% | 0.25 | 6-3 P0 | P0 +1 |
| 68 | 2-r5 | P3 -> P1 | 58% | 0.19 | 7-4 P3 | P3 +1 |
| 71 | 2-r6 | P3 -> P1 | 58% | 0.14 | 8-7 P3 | wasted at cap |

Phase 1 fights cluster around the equipment race; P1 wins 5 of 7 and sits at
the Glory cap (2) from turn 13. In phase 2 all tiers are equal, so every duel
is an even coin toss. From turn 60 to 71 three seats beat up the leader P1,
who still attempts the Emperor at turns 62, 65, and 72. P0 skips the pile-on,
collects both seals, and converts two duel wins into the two Emperor hits
that end the game. The best duelist lost; the selective one won.

## Findings

- Selection was flawless against the menu: all 14 duels took the highest
  chance on offer, never a 42% underdog fight, and the 72% edge both times it
  existed (turns 19, 47). Among equal 58% targets it picked the seat holding
  an Emperor hit — leader suppression.
- But it confused "favorable" with "useful". A duel pays +1 Glory to the
  winner only; the loser keeps everything (`glory_stolen` 0, no displacement).
  The phase-2 pile-on was mechanically unable to slow P1.
- Cap blocking burned 4 of 14 wins (29%): P1 at turns 14, 26, 45 and P3 at
  71. P1 held 2/2 Glory through late phase 1 with no sink, so its 5-2 fight
  record bought nothing. The pile-on even fed the leader: P1's only phase-2
  Glory was its turn 60 defense win, which funded its turn 62 Emperor try.
- The empty tank decided the game. P1's last two Emperor tries (turns 65, 72)
  ran with 0 Glory, so no +2 bonus: 5 vs 6 and 7 vs 8. One banked Glory at
  turn 65 is a hit, a second hit, and P1 wins there. Duels never drained P1;
  its own spending did.
- Pointless in hindsight: P3's phase-1 attacks on P1 (turns 13, 26, 45) went
  0-3 and each loss handed P1 a cap-wasted win. P3 attacked most in the game
  and finished with 2 unspent Glory, one seal, and zero Emperor tries.
- P0 was perfectly efficient: 3 duels, 3 wins, 3 Glory, all spent (peristyle
  seal at 51, Emperor tries at 70 and 73). Duel-pick confidence stayed low
  throughout (0.10 to 0.42), with mass spread over move options.

The scripted aggressive bot fails by attacking without an edge; these models
always took the best edge on offer, but the failure moved up one level: P2 and
P3 won 5 duels between them and made zero Emperor attempts.

Sources: ta07 decisions.jsonl, events.jsonl, result.json, rules.snapshot.json. 2026-11-07. state.json not read.
