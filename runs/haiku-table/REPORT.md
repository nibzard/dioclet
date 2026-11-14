# Four-agent table: game 1

- Date: 2026-11-14
- Rules: `rules_v094_twinboard.json` (0.9.4 twin-board), seed 20261114
- Seats: four Claude Haiku agents, one per seat, through
  `tools/table_seat.py`. Each agent saw only its own seat's view.
- Verify with: `python3 sim.py replay --run runs/haiku-table/game1 --verify`

## Result

P1 won at turn 116 (`survived_window`). P1 proclaimed in succession
round 4 with army and elites support, then won the duels when the other
three seats contested.

| Seat | Items | Duels won | Guard posts | Support |
| --- | --- | --- | --- | --- |
| P0 | 4 | 11 | 0 of 2 | elites |
| P1 | 5 | 9 | 1 of 1 | army, elites |
| P2 | 2 | 11 | 1 of 5 | elites, officials |
| P3 | 3 | 16 | 1 of 2 | army, officials |

## Findings

- Nobody collected all six items, so the palace map ran to its round 24
  timeout. The agents duelled far more than they explored.
- All four agents looked for "claim the checkpoint" on the palace map.
  They did not know that it needs all six items: the quick reference
  listed the action but not the requirement. The quick reference now
  states it.
- The shortlist in `candidate_actions.py` measured phase 2 distances on
  the palace map and raised `KeyError` at turn 98. This is fixed, with
  the regression test `TestTwinBoardShortlist`.
- Two seats stalled the table. P2 stopped at the crash and was resumed
  after the fix. P3 stopped to save tokens and was replaced by a fresh
  agent at turn 106. Long games need a supervisor.

## Open questions

- Is the duel-heavy palace phase an artefact of the agents, or does it
  also happen with people? Compare with `playtest/human-session-001.md`.
