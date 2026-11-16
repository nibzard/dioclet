# Arena: decision models play Dioclet

## Goal

Arena is a terminal application. It loads the game rules from a JSON file.
The user sets up a game and selects a player type and a model for each seat.
Then the application runs the game. It shows each turn and each decision as
the decision occurs.

Arena does not show graphics. It shows the game progression only:

- the current round and turn
- the player that is active
- the provider and model for that player
- the decision that the player made, with its result

You run it with `uv run arena`.

## Current state of the rules (audit)

The rules are mostly in JSON. `rules_v0102_bigboard.json` is the current
design candidate. It contains the board, movement, combat, glory, equipment,
factions, succession costs, and turn order. `sim.py validate` checks it.

These gaps exist:

1. **Hidden defaults.** `succession.py` reads six keys with default values in
   the code. These keys are not in the JSON:

   | Key | Default in code |
   |---|---|
   | `claim_required_equipment` | `6` |
   | `set_completion_reward` | `0` |
   | `proclaim_cost` | `0` |
   | `ability_stacking` | `"best"` |
   | `gate_rotation` | `0` |
   | `setup_reveals` | `[]` |

   Thus the JSON file alone does not fully describe the game.
2. **Fixed player count.** The JSON has `players`, but `engine.py:74`
   requires exactly 4. The seat IDs `P0`–`P3` are fixed in the code.
3. **No schema.** No document specifies the required keys. If a key name has
   a typo, the engine uses its default value and does not show an error.

## Decisions

- **Engine access: adapter.** A small `pyproject.toml` at the repository root
  makes `engine.py`, `succession.py`, `board.py`, and `candidate_actions.py`
  installable. Arena uses them as a uv path dependency. The rules logic stays
  in one location. The Arena code is new.
- **Provider failure: retry once, then stop.** If a provider call fails
  (error, refusal, timeout, or illegal answer), Arena retries one time. If the
  retry also fails, the game stops and Arena marks it as incomplete. The
  stream, `match.jsonl`, and the scoreboard show the seat, provider, error,
  and turn.
- **No mock provider.** Arena does not ship a fake provider. The local
  players are the real `tactical` bot and the real scripted bots. They
  operate without keys. Test doubles are in the test code only.

## Steps

### Step 0: Complete rules file

- Write `arena/rules.schema.json`.
- Write a strict loader. It rejects unknown keys and requires all keys.
- Copy the current rules to `arena/rules/v0102.json` and add the six hidden
  keys with their current values.
- Keep 4 players. Record this limit in the schema.

### Step 1: Project setup

- Python 3.12, managed with uv.
- Dependencies: `rich` (terminal output), `httpx` (HTTP), `python-dotenv`
  (keys), `pytest` (tests).
- Optional extra: `openai`, version 3.46 or later (earlier versions do not
  have `client.decisions`).
- Entry point: `uv run arena`.

### Step 2: Engine adapter

- A thin module over the existing engine: new game, observe, legal
  candidates, apply action, terminal result.
- The model sees only the public observation of the active player.

### Step 3: Provider per seat

Each seat is `Seat(name, provider, model)`. All providers use one interface:

```
decide(observation, legal_candidates) -> Decision(
    action_id, probabilities, latency, usage, cost)
```

A match file configures the seats:

```json
{"rules": "rules/v0102.json", "seed": 42,
 "seats": [{"provider": "openai", "model": "gpt-6-luna"},
           {"provider": "jev",    "model": "jev-latest"},
           {"provider": "clef",   "model": "clef-flash"},
           {"provider": "pplx",   "model": "pplx-decider-v1-27b"}],
 "budget": {"max_calls": 400, "max_usd": 0.50}}
```

Local providers: `tactical` and the scripted bots.

### Step 4: Remote adapters

- OpenAI Decisions, TypeSafe Jev, Cloudflare Clef, Perplexity Decider.
- Cloudflare states that Clef is compatible with the Jev API. Jev and Clef
  can possibly use one adapter.
- Build each adapter from the documentation of its vendor, not from blog
  posts. Do one live contract call for each provider with real keys.
- Each provider has its own pricing table and timeout. Perplexity can need
  30 seconds or more.
- Each answer must be one of the current legal `action_id` values.

This step is the only step that needs API keys and money.

### Step 5: Match runner

- Plays one game.
- Validates each answer against the legal actions.
- Enforces the budget for the match (calls and USD).
- Writes `match.jsonl`.

### Step 6: Terminal UI

- Setup wizard: select the rules file, seed, provider and model for each
  seat, and budget. The wizard shows only the providers that have keys.
- `--match file.json` starts a match without the wizard.
- One line for each decision, as it occurs. A "thinking" indicator shows
  while a model call is in progress:

  ```
  R3 T41  P2 clef/clef-flash   → duel P1   p=0.62  340ms  $0.00004
          dice 5 vs 3 → P2 wins, +1 Prestige
  ```

- At the end, a scoreboard: winner, calls, cost, and errors for each seat.

## Keys

Arena reads keys from `.env` or from environment variables:

| Provider | Variables |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| TypeSafe Jev | `TYPESAFE_API_KEY` |
| Cloudflare Clef | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` |
| Perplexity Decider | `PERPLEXITY_API_KEY` |

## Tests

- Strict rules loader and schema.
- Hidden information: no hidden state goes into a request or a log (port of
  the current sentinel test).
- Illegal answers are rejected.
- Retry once, then stop.
- Each remote adapter against recorded fixtures (test doubles at the HTTP
  boundary).
- One full game with bots only.

## Out of scope

- Series with seat rotation.
- More than 4 players.
- Graphics.
