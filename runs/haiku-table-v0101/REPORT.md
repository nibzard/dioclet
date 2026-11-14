# Four-agent table: 0.10.1 (guard posts and the reserve line), game 1

- Date: 2026-11-14 to 2026-11-15
- Rules: `rules_v0101_bigboard.json` (0.10.1-bigboard), seed 20261115
  (the same seed as `runs/haiku-table-v010/game1`). This game ran on
  the four-block succession map. D53 replaced that map with six blocks
  while the game was running.
- Seats: four Claude Haiku agents through `tools/table_seat.py`. Each
  seat read `RULES.md` (the 0.10.1 quick reference, with the line
  "Keep 1 in reserve") and saw only its own seat's view. The seats
  could not edit files or run git; `git status` showed no change to
  tracked files after the game.
- The first P0 and P1 agents stopped in succession rounds 10 and 11
  (token budget). Fresh agents took over both seats from the seat view.
- Verify with: `python3 sim.py replay --run runs/haiku-table-v0101/game1 --verify`
  (116 turns, verified).

All numbers below come from the event log, not from the seat reports.
Prestige rebuilt from the `prestige_earned` and `prestige_spent` events
matches every turn's `prestige_after` and the final state.

## Result

P3 won at turn 116 (`survived_window`). The game took 30 rounds: 17 on
the palace map and 13 on the succession map. Game 1 on 0.10.0 took 15
and 9.

P2 claimed the checkpoint on the palace map (first challenger) but
never gained support. P3 gained army (round 2) and elites (round 4) and
then proclaimed four times.

## The claims

| Claim | Round | Prestige when proclaimed (P0/P1/P2/P3) | Rivals able to contest | Outcome |
|---|---|---|---|---|
| 88 | 5 | 1/0/3/0 | 2 | cancelled by P2 in round 6 |
| 94 | 7 | 0/1/3/0 | 2 | cancelled by P2 in round 7 |
| 97 | 8 | 1/1/2/0 | 3 | P2 and P0 lost their contests; P1 cancelled it |
| 110 | 11 | 0/2/0/1 | 1 | P2 and P0 contested and lost; P3 won |

## Findings

- **The lockout from game 1 did not happen.** In game 1 all three
  rivals held 0 Prestige when the winning claim was proclaimed, and
  nobody contested. Here every claim faced at least one rival who could
  pay the fee. The seats paid 8 contest fees (P2 four, P0 three, P1
  one), and 3 of 4 claims were cancelled. The winning claim was contested twice and held because
  P3 won both duels (5-3 and 7-3).
- **The reserve line did not show in the seats' reasons.** No action
  note mentions a reserve or saving Prestige. 40% of succession turns
  were taken at 0 Prestige (19 of 48). The bot rate on 0.10.1 is about
  35%.
- **Rivals drained the one seat that could contest.** When claim 110
  was proclaimed, only P1 could pay the fee (2 Prestige). On the next
  two turns P2 and P0 duelled P1 "for Prestige" and took it to 0. The
  duel shame cost moved Prestige away from the only seat that could
  contest. Then P2 and P0 used the Prestige they won to contest, and
  lost.
- **The succession guard posts were used but paid nothing.** Three
  attempts (P1 twice in rounds 1 and 2, P3 once in round 9) rolled 1,
  2 and 1. With a 50% chance, three misses happen one time in eight.
- **Duels were the main action.** 23 duels in the succession phase,
  against 4 searches and 2 support purchases. 15 of 25 Prestige
  payments were duel shame.

## Seat view confusion

- The seat view prints `first challenger: P2` next to
  `pending claim: None`. The first P1 agent read this as a standing
  claim by P2 ("P2's claim stood from succession round 1 through
  round 11 without triggering automatic victory"). P0 in game 1 asked
  about the same pair of lines. Proposed fix: label the line as the
  palace-map checkpoint claim, or hide it in the succession phase.
- Some seat reports state things the log does not show. The first P1
  said it contested P3's claims twice and won both; the log shows one
  contest (turn 100, won). The first P0 placed P1 "at Peristyle
  [6, 6]"; the succession Peristyle is (9,6), and P1 stood at (5,6).
  Other report details check out: P0 paid three contest fees (turns
  89, 99 and 115) and lost all three duels. Treat seat reports as
  impressions, and check them against the log.

## Open questions

- Would the reserve line work better as a rule than as advice? For
  example: a duel cannot take a rival's last Prestige while a claim
  stands.
- Repeat on 0.10.2 (six blocks) for a first agent game on the adopted
  map.
