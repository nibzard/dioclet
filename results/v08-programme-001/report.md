# V0.8 programme run: v08-programme-001

Finished: 2026-11-08T10:32:32Z. Agent: `claude`.
Cycles recorded: 2 of 3.

| Cycle | Agent | Proposal | Decision | Reason |
| --- | --- | --- | --- | --- |
| 1 | claude | `succession.contest_cost = 1` | promoted | all binding promotion checks passed on screen and holdout |
| 2 | claude | `succession.contest_cost = 2` | promoted | all binding promotion checks passed on screen and holdout |

Final incumbent: `results/v08-programme-001/cycles/02/candidate-rules.json`
Rules hash: `fb7a41feab56e9ceeabbfd4e78220bb8b88466df31720c42f44add28553c6fac`

Promotion checks are mechanical guards, not a fun score. Simulation
screens mechanics and strategies; human playtests decide clarity,
tension, and replay value (`playtest/protocol-v08.md`).

Stopped early: `agent_timeout` (cycle 3).
