# Four-agent table: big board, game 1

- Date: 2026-11-14
- Rules: `rules_v010_bigboard.json` (0.10.0-bigboard), seed 20261115
- Seats: four Claude Haiku agents, one per seat, through
  `tools/table_seat.py`. Each agent saw only its own seat's view.
- Verify with: `python3 sim.py replay --run runs/haiku-table-v010/game1 --verify`
  (events and result match).

## Result

P1 won at turn 92 (`survived_window`). The game took 24 rounds: 15 on
the palace map and 9 on the succession map. The bot median on this
board is 15 and 12.

| Seat | Gate | Items | Searches | Support at the end |
| --- | --- | --- | --- | --- |
| P0 | east | 6 | 1 | army |
| P1 | west | 6 | 1 | army, elites |
| P2 | south | 6 | 1 | elites |
| P3 | north | 5 | 2 | army, elites |

## Faction cards

- Every seat searched a card in succession round 1. The agents found
  the `?` cells and the search action without help.
- Round 1: P2 found elites (9,11), P0 found officials (18,12), and P1
  and P3 found blanks (4,6) and (0,0). Round 2: P3 found army (9,1).
  After two rounds, all three factions were public.
- Nobody bought officials. It sits in the far corner (18,12), 15
  steps from the Peristyle. Army and elites are 5 steps from it.
- P1 and P3 both reached two supports in round 6. P1 proclaimed
  first, in round 7.

## Findings

- The palace map ended on its own (P1 claimed the checkpoint), not
  at the round cap. Three seats had all six items.
- Prestige decided the endgame, not the cards. Seats held 0 or 1
  Prestige for most of the succession phase. Once P1 proclaimed, no
  rival duelled P1 inside the window: the other duels were between
  the rivals. This matches the lockout complaint from
  `playtest/human-session-001.md` and the 0.9.4 review.
- Two agents said the card rule was "not immediately clear", but
  both searched in round 1. The `?` on the map and the shortlist
  label "Search the face-down faction card" were enough.
- No seat stalled. All four played to the end.

- In a follow-up note, P0 asked for clearer words about three
  things. First, how "claim the checkpoint" (palace map) differs
  from "proclaim" and "maintain claim" (succession map). Second,
  why the view shows "first challenger: P1" next to "pending claim:
  None". Third, how long the claim window lasts.

## Open questions

- Do the two far-corner sites ((0,0) and (18,12)) matter? A faction
  there costs a long walk. This is symmetric across gates, but it
  can make one faction a dead card in a game.
- The Prestige lockout in phase 2 is still the main design problem.
  It is not caused by the map.
