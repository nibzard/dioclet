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
