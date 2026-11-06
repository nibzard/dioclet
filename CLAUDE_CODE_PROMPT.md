# Prompt to give Claude Code

Implement the headless, four-player **Diocletian's Palace** game simulator specified in `SPEC.md`, using `rules_baseline.json` as the canonical configuration. This is a simulation and experimentation project, not a graphical game.

Build the Python CLI, deterministic engine, legal-action generator, four observation-only built-in policies, JSONL event logging, batch runner, reports, replay verification, and tests. Follow the turn protocol and game rules literally. Do not silently invent features or modify the baseline rules; put any necessary clarifications in `DECISIONS.md` and test them.

Work in this order:

1. Read and validate the complete spec and JSON; identify any contradictions before implementation.
2. Implement the graph, state, RNG, game transitions, and action validation.
3. Add CLI commands (`validate`, `new`, `observe`, `act`, `auto`, `batch`, `report`, `replay`).
4. Add bots, event logs, reports, tests and replay checks.
5. Run 10 smoke-test games and verify invariants and deterministic replays.
6. Run the 1,000-game baseline experiment with the policy rotations in the spec.
7. Write `FINDINGS.md` with win rates, full-game duration, number of collected/auto-granted equipment items, duel frequency, strategy balance, gate fairness, and proposed next rules experiments. Cite result file names and never invent metrics.
8. Only after baseline results exist, propose 2–3 *new JSON files*, each changing one conceptual rule knob, to compare. Do not overwrite `rules_baseline.json`.

For optional four-LLM-agent games, act as a **single turn orchestrator**: give only the current `observe` output to the agent playing that seat, receive an `action_id` and reason, then invoke `act`. Never allow agents to read `state.json` or choose actions from unseen information. Use cheap scripted bots for thousands of games; use LLM role-play for a handful of interesting games.

The project is done when I can change a value in a copied `rules_*.json`, run a reproducible 1,000-game batch, and inspect summary statistics plus a few individual readable logs to decide whether the change improved the game.
