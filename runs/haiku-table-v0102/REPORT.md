# Four-agent table: 0.10.2 (six-block succession map), game 1

- Date: 2026-11-15
- Rules: `rules_v0102_bigboard.json` (0.10.2-bigboard), seed 20261115
  (the same seed as the two earlier table games).
- Seat tool: `tools/table_seat.py` with the claim-line and map
  orientation fixes from PR #26. `RULES.md` is the 0.10.2 quick
  reference plus notes on reading the view.
- Seats: four Claude Haiku agents. Each saw only its own seat's view.
  They could not edit files or run git; `git status` showed no change
  to tracked files after the game. All four seats played to the end.
- Verify with: `python3 sim.py replay --run runs/haiku-table-v0102/game1 --verify`
  (92 turns, verified).

All numbers below come from the event log. Prestige rebuilt from the
events matches every turn's `prestige_after` and the final state.

## Result

P0 won at turn 92 (`survived_window`). The game took 24 rounds: 13 on
the palace map and 11 on the succession map. The bot median on 0.10.2
is 15 and 10.

| Game | Rules | Palace rounds | Succession rounds | Winner |
|---|---|---|---|---|
| `haiku-table-v010` | 0.10.0, four blocks, no succession posts | 15 | 9 | P1 |
| `haiku-table-v0101` | 0.10.1, four blocks, posts, reserve line | 17 | 13 | P3 |
| `haiku-table-v0102` | 0.10.2, six blocks | 13 | 11 | P0 |

## Faction cards

The deal put army on (7,6) and elites on (11,6), the two cards next
to the Peristyle. Officials went to the far corner (15,12), and nobody
searched it. Seats searched 5 cards in rounds 1 and 2. All four seats
then bought army and elites. P1, P2 and P3 had two supports by round
5; P0 bought its second in round 8.
With a random deal, both near cards hold factions in one game in five.

## The claims

| Claim | Round | Prestige when proclaimed (P0/P1/P2/P3) | Rivals able to contest | Outcome |
|---|---|---|---|---|
| 74 (P1) | 6 | 1/0/0/1 | 2 | cancelled by P3 |
| 77 (P1) | 7 | 1/0/0/1 | 2 | cancelled by P3 |
| 79 (P2) | 7 | 1/0/0/1 | 2 | cancelled by P0 |
| 86 (P0) | 9 | 0/1/0/1 | 2 | P3 and P1 contested and lost (2-3, 3-4); P0 won |

## Findings

- **No lockout.** Every claim faced two rivals who could pay the fee.
  The seats paid 5 contest fees (P3 three, P0 one, P1 one) and
  cancelled 3 of 4 claims. The winning claim held through two close
  duels.
- **Fewer broke turns.** 33% of succession turns were taken at 0
  Prestige (13 of 40), against 40% in the 0.10.1 game. One action note
  mentions saving Prestige (P2, palace round, "preserve Prestige").
- **Support came fast.** With both factions next to the Peristyle,
  support cost almost no walking. Prestige, not distance, decided who
  could proclaim. Every claim was proclaimed at 0 Prestige. The first
  three were cancelled on the next turn; P0's claim survived because
  both contests lost.
- **Fewer duels.** 11 duels in the succession phase (23 in the 0.10.1
  game). Prestige went mostly to support (8 purchases) and contests
  (5 fees); duel shame cost 1.
- **One guard post attempt** in the succession phase (P1, round 8),
  which earned 1 Prestige.

## Seat view and rules confusion

- **The Peristyle moves.** Three seats (P0, P2, P3) said the
  Peristyle was at (6,6) on the palace map and (9,6) on the succession
  map, and this confused them. On 0.10.2 the two maps share one
  street grid, so the shift is easy to miss. On the printed board the
  octagon marks it; the rules text does not say it moves.
- **No seat misread the claim lines.** P3 described its palace
  checkpoint claim as entering the succession as first challenger,
  which is correct. No seat confused it with a standing claim.
- No seat complained about the map orientation (y 0 now at the top).
- Seats still report some things the log does not show. P1 said it
  "spent 1 prestige to win against P0 in a duel"; its one win against
  P0 (round 5) was a plain duel with no fee. Treat seat reports as
  impressions.

## Open questions

- Should the rules text (quick reference and rulebook) say that the
  Peristyle is in a different place on the succession map? For
  example: "On the succession map the Peristyle is the octagon in the
  middle of the centre street, not the palace crossing."
- The two cards next to the Peristyle held both factions here. Watch
  whether this makes support too easy in live play. The bots search
  about 5.9 times a game on every map.
