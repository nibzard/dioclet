# Run directories

- `narr1`–`narr5`: qualitative playtests from the V0.1 study. They ran
  on an engine that still had the emperor-miss retreat bug, so their
  event logs no longer replay under the corrected engine. They are
  kept as historical artifacts; the notes in `notes/` carry caveat
  banners.
- `narr6`, `narr7`: endgame repeat playtests on the corrected engine.
  Both replay byte-identical (`sim.py replay --run runs/narr6
  --verify`).
- Batch sample games live under `results/<experiment>/sample_games`
  and all replay-verify.
- `haiku-table/game1`: a four-agent game on the 0.9.4 twin-board rules
  (seed 20261114, 2026-11-14). Each seat was a separate Claude Haiku
  agent playing through `tools/table_seat.py`. P1 won at turn 116.
  Replays byte-identical. `haiku-table/RULES.md` is the rules sheet the
  agents read, and `haiku-table/REPORT.md` summarizes what they did.
