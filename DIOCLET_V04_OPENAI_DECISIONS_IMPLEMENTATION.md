# Diocletian's Palace — V0.4 OpenAI Decisions Player Intelligence

**Implementation brief for Claude Code**  
**Repository:** https://github.com/nibzard/dioclet  
**Reference revision inspected when this brief was written:** `51c30fc12763621790c5c1761826397f3f0ec566` (verify the current branch before editing).  
**API reference:** https://developers.openai.com/api/docs/guides/decisions  
**Endpoint reference:** https://developers.openai.com/api/reference/resources/decisions/methods/create  
**Scope:** integrate an optional *OpenAI Decisions* player and strengthen player-evaluation methodology. **Do not change mechanics or historical experiments in this phase.**

## 0. Goal and guardrails

Add an observation-only AI policy that selects **one of the current legal game actions** using the OpenAI **Decisions API**. This is **not** a Responses API/chat-completion integration and not a Claude subagent taking every move. Use the Decisions API's typed `choice` question and return its selection to the existing deterministic game engine.

- The Python engine alone owns the game state, random dice, legality, movement, battles, turn advancement, phase transitions, and winning conditions.
- The model sees only `engine.observe(state, player_id)` (or a strictly sanitized projection of it), plus deterministic features computed from that observation and the *public* rules. It never reads `state.json`, hidden equipment placements, unrevealed RNG state, or another player's private memory.
- The decision model **does not** supply coordinates, invented actions, or engine state mutations. It selects a **current-turn action_id** from a validated finite list.
- Keep existing `sim.py new/observe/act/auto/batch/report/replay`, existing bots, all tests, historical rules/results, and offline replay working. Store V0.4 outputs in new directories only.
- Separate questions: (a) are the policies intelligent?, (b) are the mechanics balanced? Do not silently adopt `rules_v03_lostturn.json` or introduce new combat rules to boost AI results.

**Primary experiment:** Does an OpenAI Decisions policy improve the quality of turn choices over existing scripted bots and a new deterministic tactical baseline? **Secondary:** Does the observed relative value of aggression change under more competent players?

## 1. Read existing code and official API docs first

1. Fetch the current `main`, review `README.md`, `SPEC.md`, `DECISIONS.md`, `FINDINGS_V02.md`, `FINDINGS_V03.md`, `sim.py`, `engine.py`, `policies.py`, `report.py`, and `tests/`. Run the existing tests and record the git SHA.
2. Create `feature/v04-openai-decisions` from the latest main. Keep historical result directories and existing rule JSONs byte-for-byte unchanged.
3. Read the live official docs for **Decisions**, **Create a decision**, and the **official OpenAI Python SDK** before implementing the service call. The API is evolving; if docs differ from the examples in this file, follow docs and record the variance.
4. Use the optional official Python package `openai`, pinned to a version verified to support `client.decisions.create(...)`, in `requirements-decisions.txt`. Existing standard-library-only code and tests must work with `openai` uninstalled.
5. Auth is via `OPENAI_API_KEY`. No TypeSafe/Jev SDK, `TYPESAFE_API_KEY`, `jev-latest`, or TypeSafe question format. Do not introduce TypeScript just to call the API.

As documented at the time of writing (November 7, 2026), OpenAI Decisions is generally available, its currently supported model is **`gpt-6-luna`**, `POST /v1/decisions` accepts 1–400 typed questions, and a `choice` question accepts **2–255 unique options**. Verify these constraints when implementing.

## 2. Recommended architecture

Suggested new modules (adapt names to repository style where appropriate):

- `candidate_actions.py` — pure projection and shortlist generation; functions accept only an observation and public rules/config.
- `tactical_policy.py` — locally computed deterministic baseline for evaluating policy competency.
- `decisions_policy.py` — provider wrapper for OpenAI `decisions.create`; request and response validation, strictly typed result.
- `ai_driver.py` or a clean extension of `sim.py` — sequential single-writer game orchestration, mixed policies, budgets, logging.
- `decisions_config.json` — model, candidate cap, decision prompt/version, top-choice vs sampled-choice, network limits, policy persona, fallback strategy.
- `tests/test_candidates.py`, `tests/test_decisions_policy.py`, `tests/test_ai_driver.py` — offline mock, adversarial, and replay tests.
- `FINDINGS_V04.md` — **measured** results and limitations, never speculative scores.

Use `dataclass` / `TypedDict` / SDK types plus runtime validation at each network boundary. Define an internal `PlayerDecision` e.g.:

```python
@dataclass(frozen=True)
class PlayerDecision:
    action_id: str
    policy: str                      # "decisions", "tactical", etc.
    reason: str                      # concise machine-readable rationale
    metadata: dict                   # model, probabilities, confidence, latency, usage, provider, error
```

Keep engine event logs authoritative. Use a distinct append-only `decisions.jsonl` for provider decisions. Do **not** embed API HTTP metadata or secrets into the game's deterministic state machine.

## 3. Information boundary and state projection

The model must receive only the active player's observation returned by `engine.observe`. Allowed: current already-rolled movement die, positions, public equipment, revealed districts, Glory, seals, Emperor hits, current phase/turn, checkpoint progress, legal action list, public rules such as combat bonuses, and features computed exclusively from those inputs.

Forbidden: inspection of `state.json`, hidden item-to-district mapping before reveal, future dice, bot RNG, unrevealed events, logs from later turns, and file reads from the model adapter. Default **stateless** per-turn decisions. If memory is later considered, keep it per-seat and derived solely from public observations; test separately.

Build a compact, stable **JSON projection** containing:

```json
{
  "objective": "Defeat Emperor first; play to maximize eventual win chance",
  "turn": {"id": 41, "round": 4, "phase": 2, "player": "P1", "movement_die": 4},
  "self": {"position": [2, 3], "equipment_count": 6, "glory": 1, "seals": ["cellars", "peristyle"], "emperor_hits": 1},
  "opponents": [{"id": "P2", "position": [2, 4], "glory": 2, "seals_count": 2, "emperor_hits": 1}],
  "public_locations": {"emperor": [2, 4], "peristyle": [2, 2]},
  "rule_summary": {"emperor_hits_to_win": 2, "duel_lost_turn": false, "glory_cap": 2},
  "candidate_count": 2
}
```

This is an **illustrative fragment**, not a fixed schema or actual run. Include full necessary opponent/public state from the current observation. Avoid fabricating interpretations of rule JSON fields. Use stable sorting and stable serialization for reproducible hashes. Add a test that purposely plants a hidden sentinel in `state.json` and confirms it is not in any request or decision log.

## 4. Candidate actions: good shortlist, no lost winning options

The engine can expose many near-duplicate moves. Construct an observation-only deterministic shortlist; default target **12–16**, configurable maximum **24**. The Decisions API allows 2–255 `choice` options, but avoid huge choice sets that obscure meaningful distinctions.

Requirements:

1. Consider **every** action in `observation["legal_actions"]`, never invent an action or change an action ID. Keep the full legal set intact in the engine.
2. Always retain any immediately game-winning `attack_emperor` alternatives, `claim_checkpoint`, and meaningful `attempt_seal` / `explore` actions. Keep spend-Glory and no-spend alternatives when strategically distinct.
3. Preserve different opponent duel targets, high-urgency interference options, guard-post candidates, and distinct goal-directed movement paths. Never automatically remove duels at Glory cap: `duel_lost_turn` may still matter.
4. Group equivalent movement actions using explicit deterministic criteria (distance to goal, positional difference, future opportunities). Keep at least one non-greedy alternative. If mandatory actions exceed configured cap, **increase the cap or fail explicitly**; do not discard wins silently.
5. Include `action_id`, `kind`, destination, path length, target, spend-Glory flag, and a concise accurate description; compute useful features including distances, expected gains, duel win probability (enumerate 6×6 dice combinations when applicable), success odds for public challenges, and whether opponents are near a win. Unrevealed items remain uncertain.
6. If **exactly one legal action** exists, take it **without a Decisions API call**, log `single_legal_action`. The `choice` API requires at least 2 choices. If none exists in a live turn, surface an engine error rather than making an API call.
7. Deterministically sort candidates and log exclusions/reasons so that no outcome can be blamed on hidden filtering.

Candidate descriptions must **not** include guessed win probabilities over the full multi-turn game presented as facts. Distinguish exact immediate roll odds from heuristic estimates.

## 5. Correct OpenAI Decisions request

Use the **official `choice` question schema**: `model`, `input`, and `questions` as an **array**. One `choice` question per real decision, named `best_action`. Use **`choices` as an array of `{value, description}` objects**. Use a structured `input_json` content part in a **user** message for the public observation. Model `gpt-6-luna` is the supported Decisions model at the time of writing.

Illustrative Python SDK call:

```python
from openai import OpenAI

client = OpenAI()   # reads OPENAI_API_KEY from environment

request = {
    "model": "gpt-6-luna",
    "input": [{
        "role": "user",
        "content": [
            {"type": "input_text", "text": "Select the best legal board-game move given this public state."},
            {"type": "input_json", "data": public_observation_projection},
        ],
    }],
    "questions": [{
        "type": "choice",
        "name": "best_action",
        "instructions": (
            "You are one player in a four-player competitive board game. "
            "Pick the option most likely to improve your eventual chance to be "
            "first to defeat the Emperor. Prefer an immediate legal win over "
            "unrelated actions; consider progress, opponents, and resource tempo. "
            "Use only the supplied public information and action descriptions."
        ),
        "choices": [
            {"value": c["action_id"], "description": c["description"]}
            for c in candidate_shortlist
        ],
    }],
}

response = client.decisions.create(**request)
answer = response.answers[0]
if answer.type == "refusal":
    raise RuntimeError("Decisions refused best_action")
if answer.type != "choice" or answer.name != "best_action":
    raise RuntimeError("Unexpected Decisions answer type/name")
selected_action_id = answer.choice
# Additional validation against shortlist and observation.legal_actions required.
```

**This is an integration pattern, not proof that a request was executed.** Confirm SDK availability and exact installed type names against the current docs. The endpoint is `POST https://api.openai.com/v1/decisions` if using a direct HTTP fallback (official SDK preferred).

**Important differences from the previous Jev draft:**

- The old pseudo-schema `{"state": ..., "questions": {"best_action": {"criteria": ...}}}` is **wrong for OpenAI Decisions**.
- `questions` is an **array**, and each `choice` question supplies `choices`, not `criteria`.
- `input_json` carries the structured state. You can also send a plain text `input` string; JSON is preferred for auditability.
- Never set `model="jev-latest"` or install `typesafe-sdk`.
- Do not request free-form explanation as a field on the Decisions answer; `choice` returns a typed answer, not an arbitrary rationale. Local `reason` can be `openai_decisions_choice` with attached features.

## 6. Correct response parsing and type checks

The `response.answers` array returns a matching answer per question. For `best_action`, expect a typed choice answer with:

```json
{
  "type": "choice",
  "name": "best_action",
  "choice": "a0042",
  "probabilities": [
    {"value": "a0042", "probability": 0.72},
    {"value": "a0051", "probability": 0.28}
  ],
  "confidence": 0.86
}
```

This response is **illustrative**, not a measured output. Importantly, `probabilities` is an **array of objects**, not a map from option to probability.

Validation:

- The answer must be the correct type/name; a `refusal` must be handled explicitly, not treated as an action.
- The `choice` must be a **string** equal to a current shortlisted `action_id` **and** a current engine legal action ID. A response containing any other ID is invalid and must never reach `engine.apply_action`.
- Validate probability entries as distinct option values with finite `[0,1]` numbers. Accept that the API response may omit/return empty probability entries according to schema; do not assume every input option always appears. If nonempty and complete, check approximate normalization with tolerance and log discrepancies rather than changing the selected action. Do not fabricate or renormalize probabilities silently.
- Validate confidence as finite `[0,1]` when present. **Confidence is not the probability that the selected action will win the game**, and the choice distribution is not a distribution of ultimate game outcomes.
- Default to selecting the returned `choice` deterministically (`selection_mode="top"`). Optionally sample from the returned probabilities with a separate seeded policy RNG in a later explicit experiment; sampling must be implemented only when a valid complete distribution is returned. Do not advance engine RNG.
- Record response `model`, token `usage` when returned (including cached-input breakdown if available), request ID when available, latency, input/config hashes, and actual action executed.

## 7. Reliability, cost and secrets

- Keep `OPENAI_API_KEY` in environment; never commit `.env`, keys, raw auth headers or secrets to the public GitHub repository. Make `.gitignore` cover `.env`, `.env.*` while optionally allowing `.env.example`.
- Provide mock and recorded-response providers with **no API key needed**. Existing commands and unit tests must never attempt network calls without an explicit live flag.
- **Explicit opt-in** to live Decisions via `--live-decisions` or `--provider live`. On authentication, no credits, missing key, invalid model, refusal, repeated rate limiting or hard budget exhaustion: **stop the live batch cleanly**, preserve the partial logs and status, and do not silently substitute `tactical` and count the result as a Decisions win. For a one-off interactive turn, a separately enabled fallback can be logged and included in fallback statistics.
- Network timeout, bounded retries for genuine transient faults, conservative concurrency limits. Avoid retrying ambiguous write side effects (Decisions is read-only from the game's perspective but repeated requests still incur API usage). Log attempts.
- Add `--max-decisions-calls`, `--max-input-tokens-estimate`, `--max-cost-usd`, and a wall-clock timeout. Enforce call budgets **before** sending each request. Use conservative projected costs and actual usage afterward; projected dollar values are estimates, not a guaranteed provider billing ceiling. Enforce a hard call cap even if cost can't be estimated.
- Document model-dependent pricing rather than hardcoding it in code without versioning. As of the reference guide, `gpt-6-luna` Decisions uncached input costs **$0.10 per million tokens**, output tokens are not billed, and caching/regional multipliers can apply; read official pricing immediately before live experiments.
- Consider prompt caching only as a performance optimization after tests. The guide notes that matching shared `input` prefixes need at least 1,024 tokens for cache reuse; do not bloat state merely to achieve caching. In any case, log cached and cache-write token counts when available.
- No extra LLM subagent needed for normal matches. Four `decisions`-controlled players mean four **independent decisions on sequential turns**, never concurrent writes to the same state.

## 8. CLI and orchestration

Preserve existing commands and add a driver that can run live/mock/playback Decisions policies and built-in bots in the same game. The existing `sim.py batch` / `report.play_game` routines assume synchronous local policies; do not add hidden network calls to them without explicit separation.

Proposed interface (adjust ergonomics if necessary and document actual commands):

```bash
# Existing tests and engine unaffected
python3 -m unittest discover -s tests

# New offline adapter + driver tests
python3 -m unittest tests.test_candidates tests.test_decisions_policy tests.test_ai_driver

# Mock game: no API calls, deterministic action selection
python3 sim.py ai-auto --rules rules_v03_base.json --seed 4400 \
  --players decisions,decisions,decisions,decisions \
  --provider mock --out runs/v04_mock_4400

# Live pilot (requires OPENAI_API_KEY and an explicit finite cap)
python3 sim.py ai-auto --rules rules_v03_base.json --seed 4401 \
  --players decisions,decisions,decisions,decisions \
  --provider live --live-decisions --model gpt-6-luna \
  --max-decisions-calls 100 --max-cost-usd 1.00 \
  --out runs/v04_decisions_4401

# Mixed players, same mechanics
python3 sim.py ai-auto --rules rules_v03_base.json --seed 4402 \
  --players decisions,tactical,balanced,greedy \
  --provider live --live-decisions --max-decisions-calls 100 \
  --out runs/v04_mix_4402

# Reproducible replay: MUST NOT contact OpenAI
python3 sim.py replay --run runs/v04_decisions_4401 --verify
```

Support `--decisions-config decisions_config.json`, `--selection-mode top|sample`, `--provider mock|playback|live`, `--model`, and per-player policies, with explicit handling of run-dir collisions. Record only the action chosen in engine logs; write provider metadata separately.

### Suggested configuration

```json
{
  "provider": "mock",
  "model": "gpt-6-luna",
  "candidate_cap": 16,
  "prompt_version": "v04-1",
  "selection_mode": "top",
  "max_retries": 1,
  "timeout_seconds": 20,
  "fallback_on_live_error": false,
  "persona": "win_focused"
}
```

This is application-specific config, **not** a raw OpenAI request body.

## 9. Decision audit logs and replay

Append `decisions.jsonl` for each real decision. Each record should include:

- `game_id`, `turn_id`, `player`, policy, public observation hash and projection schema version;
- full legal-action count, shortlist / descriptions / candidate features, excluded-action count / reasons;
- model and provider, request/config/prompt hash (or redacted payload if recording), API request ID when available;
- chosen action, top alternatives, model's probability array and confidence, selected mode, fallback/refusal/error;
- per-call latency, input/output/total tokens, cached and cache-write breakdown if supplied, estimated cost;
- action actually applied and engine turn result reference.

Store raw user-visible sanitized observations if useful for offline comparative scoring, but **never** include secret hidden engine fields. A final-run report must count every attempted, refused, failed, retried, and fallback decision. If interrupted at the budget cap, mark the game **incomplete**, not a draw or finished result. Crash/restart should not duplicate game actions or API calls inadvertently; implement recoverable checkpoints or fail closed.

**Replay uses recorded action IDs, not model calls.** Existing `replay --verify` checks that same actions plus seeded engine RNG reproduce the game. A separate policy-decision playback test can verify parsing/selection from recorded provider responses. Model probability outputs need not be exactly reproduced by a fresh API call.

## 10. Tactical baseline (important methodological control)

Add a deterministic `tactical` policy that can outperform an overly eager `aggressive` bot by making rational short-horizon decisions. Its logic must depend only on observations. At minimum:

1. Check for an immediate game-winning Emperor attack **before** selecting a duel. Note that the attack is stochastic; rank by odds, not certainty.
2. Prioritize reaching a needed second seal and a possible winning attack when available.
3. Evaluate duel expected payoff **including** a target's threatening position/progress, win probability, potential skipped turn under the active rules, wasted Glory, and the opportunity cost of not making progress toward the Palace objective.
4. Evaluate use of Glory on seals versus the Emperor with explicit approximate marginal value; do not hoard tokens blindly.
5. Avoid repeated worthless movement or repeatedly visiting already-known duplicate equipment locations.
6. Use deterministic tie-breakers and stable action IDs; log compact *reason codes*.

The tactical policy is a benchmark, not an oracle. Freeze its version and parameters **before** running comparisons; do not tune it after seeing just one loss without recording a new experiment version.

## 11. Experimental design and report

### Phase A — offline engineering (no API key)

- Verify historical suite unchanged. Add at least 100 fixture-based or generated observations to exercise candidates, engine-authority, probability validation, refusal handling, deterministic mock decisions, singular legal action, 255-option bound, no hidden-state leakage, call-budget stops, and replay.
- Run 1,000+ games with existing and tactical local bots using `rules_v03_base.json` to confirm no engine regression. Use identical published seed/seat protocols for broad comparability. **These do not test the OpenAI model.**

### Phase B — tiny live pilot

- Only with an explicitly available API key and authorized budget: 2–5 games total, some mirror and some mixed. No bulk live API calls without checking API access, budget/cost, latency, invalid-response rate, and successful `replay --verify`.
- Before these games, run 2–3 **real** Decisions choice calls on stored fixture observations to validate the SDK/model schema and returned probability structure. Mark them as API contract tests, not game performance samples.

### Phase C — evaluation (separately authorized budget)

- 32–64 four-`decisions` mirror games with balanced gate/seat placement and explicit confidence intervals; 32–64 games against `tactical` and the existing bots, with each policy rotating seats. Record exact schedules and per-policy denominators. These are pilots, not conclusive proof of game fairness.
- The principal rule file is **`rules_v03_base.json`**. A smaller matched follow-up with **`rules_v03_lostturn.json`** can test whether the combat conclusion changes, but **do not combine** decisions policy development with simultaneous rule modifications.
- Same seeds do not imply identical dice trajectories or hidden future states when actions diverge. Compare on matched initial conditions; avoid claiming identical subsequent RNG events.
- For prompt comparisons, use a fixed bank of **recorded public observations** to isolate decision changes from whole-game trajectory changes.

### Phase D — findings

Report: games completed/draws/incomplete, policy win rate with Wilson intervals, duration (turns/rounds), equipment actively collected vs auto-granted, duel frequency and effectiveness, chances to delay Emperor leader, Glory economy, goal progression, fraction of apparently dominated moves, near-term blunders (e.g. duel instead of plausible Emperor win), initiative advantage, and cost (calls/game, latency percentiles, token breakdown, cost/game). Model confidence and choice probabilities express model choice uncertainty, **not calibrated win probability**: analyze them accordingly.

**Interpretation caution:** In the current `policies.py`, `aggressive` attempts duels before attacking the Emperor and `greedy` never spends Glory. Winning more often than those particular bots alone does not establish expert play. Benchmark against the new `tactical` policy and identical-policy mirror matches.

## 12. Acceptance criteria

- [ ] All historical tests pass; existing rules/results unchanged.
- [ ] `openai` is optional for offline engine; live Decisions requires explicit opt-in and `OPENAI_API_KEY`.
- [ ] All API requests use `client.decisions.create`, model `gpt-6-luna` unless docs have changed, a single `choice` question with `choices[]`, and sanitized `input_json`.
- [ ] Exactly one legal action: no API call. For 2+ choices: request has within documented option limit.
- [ ] No chosen action outside `legal_actions` ever reaches the engine; refusal/invalid answer handled explicitly.
- [ ] No hidden game state or API key appears in decision inputs/logs.
- [ ] Four Decisions players can complete a game (live, when access exists) and pass offline `replay --verify`.
- [ ] Every model-driven turn has logs of action, choice probabilities/confidence (as available), usage, latency, errors, fallback, prompt/config hash.
- [ ] Exact rules hash, engine SHA, model version, seeds and player seat assignments reported.
- [ ] Hard **request-call cap** enforced, incomplete games excluded from win-rate samples, no silently substituted fallback in headline model statistics.
- [ ] `FINDINGS_V04.md` separates validated engineering results, actual model observations, and unrun experiments.
- [ ] Feature branch + PR/diff summary for review, not an unreviewed push to `main`.

## 13. Deliverables

Complete code and tests, `requirements-decisions.txt`, `decisions_config.json`, sample/mock request and response fixtures, a README section showing the new CLI, a `results/v04_*` area for new experiments, and `FINDINGS_V04.md`. Clearly state which live calls were/weren't run; never claim API performance without API calls.

Do **not** introduce a game GUI, replace the simulator, introduce new mechanics, or rewrite old historical findings. Close V0.4 with a recommendation about whether OpenAI Decisions is useful for this game's AI-turn policy, including measured costs and design insights.

---

### Official sources (read live before coding)

- OpenAI Decisions guide: https://developers.openai.com/api/docs/guides/decisions
- Create a decision API reference: https://developers.openai.com/api/reference/resources/decisions/methods/create
- OpenAI SDK overview: https://developers.openai.com/api/docs/libraries
- Repo: https://github.com/nibzard/dioclet
