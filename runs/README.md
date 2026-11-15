# Run directories

- `haiku-table-v0102/game1`: a four-agent game on the V0.10.2 big-board
  rules. Each seat was a separate Claude Haiku agent playing through
  `tools/table_seat.py`. `haiku-table-v0102/RULES.md` is the rules sheet
  the agents read, and `haiku-table-v0102/REPORT.md` summarizes what
  they did. Verify with `sim.py replay --run runs/haiku-table-v0102/game1
  --verify`.

The V0.1–V0.9 run directories (narr1–narr8, the V0.4 decision-tournament
games, and the earlier Haiku tables) were removed in the V0.10.2 cleanup;
git history keeps them. Their conclusions live in
[docs/findings](../docs/findings) and `DECISIONS.md`.
