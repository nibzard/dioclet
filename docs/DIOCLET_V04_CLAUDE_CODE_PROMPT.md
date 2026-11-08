# Claude Code task — Dioclet V0.4 OpenAI Decisions

Implement **Diocletian's Palace V0.4 — OpenAI Decisions Player Intelligence**.

Read `DIOCLET_V04_OPENAI_DECISIONS_IMPLEMENTATION.md` completely, and follow it as the implementation specification.

Repository: https://github.com/nibzard/dioclet

1. Fetch latest `main`, read the current engine, policies, spec, findings, tests, and record the head SHA. Create branch `feature/v04-openai-decisions`.
2. Verify the live OpenAI Decisions documentation at https://developers.openai.com/api/docs/guides/decisions and https://developers.openai.com/api/reference/resources/decisions/methods/create. Use the official Python SDK `client.decisions.create`, with `gpt-6-luna`, a `choice` question (array `questions`, array `choices`), and user `input_json` for sanitized public state. Never use TypeSafe/Jev libraries or the old pseudo-request schema.
3. Preserve engine authority, offline reproducibility, existing mechanics, built-in bots, and historical rules/results. Create an observation-only candidate shortlist, typed API boundary, mock/playback/live providers, decision logs and budget controls.
4. Implement a competent deterministic `tactical` bot to benchmark decision quality. Keep it frozen across comparisons.
5. Build an AI auto-play driver with mixed policies or four Decisions players. Handle one-legal-action turns without an API call; reject refusals and illegal IDs; do not silently count fallback decisions as OpenAI Decisions results.
6. Run all old tests and add comprehensive offline tests (including hidden-information redaction and replay). Then run bot-only batches. Do not report local mock games as real OpenAI decisions.
7. If `OPENAI_API_KEY` is available and live calls are permitted within the explicitly configured budget, run 2–3 real API contract checks and only a tiny 2–5 game pilot first. Do not initiate 32–64-game live experiments without explicit approval of cost/call budget. Save all logs and reproduce finished games with offline replay.
8. Write `FINDINGS_V04.md` with observed outcomes, token usage/cost, rates of invalid/refused/fallback choices, fairness comparisons, strategy insights and next experiments. Clearly mark unrun tests.
9. Provide a feature branch/PR or diff for review; don't quietly push to main.

Acceptance: the engine and historical data are unchanged, a legal action is always enforced, hidden information cannot reach the model, the new integration is optional and budget-capped, and a finished four-Decisions-player game replays offline.
