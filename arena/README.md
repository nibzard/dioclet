# Arena

Arena is a terminal application. Decision models play Dioclet against each
other and against the built-in bots. Each seat has its own provider and
model. Arena shows each turn while the game plays, and it records all data
for each turn in a log that you can use to train models.

```
R1 T1  P1 jev/jev-latest   → explore D   p=0.45  321ms  $0.00015
        P1 takes gladius
R1 T2  P2 clef/clef-flash   → explore D   p=0.20  338ms  $0.00010
R1 T3  P0 openai/gpt-6-luna   → move (12,3)   p=0.45  1138ms  $0.00034
R1 T4  P3 pplx/pplx-decider-v1.3   → move (6,6)   p=0.25  964ms  $0.00006
```

## 1. Quickstart (no keys)

You need [uv](https://docs.astral.sh/uv/). Arena uses Python 3.12.

```bash
cd arena
uv run arena --match matches/bots.json
```

Four built-in bots play one full game. At the end, Arena shows the
scoreboard and the run directory.

To set up a game in the terminal, start Arena without a match file:

```bash
uv run arena
```

The setup wizard asks for the rules file, the seed, the player for each
seat, and the budget.

## 2. Add model players

1. Copy the key file and fill in the keys for the providers that you use:

   ```bash
   cp .env.example .env
   ```

   | Provider | Variables |
   |---|---|
   | `openai` (OpenAI Decisions) | `OPENAI_API_KEY` |
   | `jev` (TypeSafe Jev) | `TYPESAFE_API_KEY` |
   | `clef` (Cloudflare Clef on Workers AI) | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` |
   | `pplx` (Perplexity Decider) | `PERPLEXITY_API_KEY` |
   | `gateway` (Vercel AI Gateway) | `AI_GATEWAY_API_KEY` |

   Arena also reads these variables from your shell. A variable in the
   shell has priority over the same variable in `.env`. Git ignores `.env`.

2. Add the `decisions` extra. The `openai` and `gateway` providers need it:

   ```bash
   uv run --extra decisions arena
   ```

3. Play a match between four providers:

   ```bash
   uv run --extra decisions arena --match matches/example.json
   ```

   This match file uses `openai`, `jev`, `clef`, and `pplx`. One game is
   approximately 110 turns. At the prices from November 2026, one game costs
   approximately $0.05.

The wizard shows only the providers that have all their keys.

## 3. Write a match file

A match file sets the rules, the seed, the four seats, and the budget:

```json
{
  "rules": "rules/v0102.json",
  "seed": 42,
  "seats": [
    {"provider": "openai",  "model": "gpt-6-luna"},
    {"provider": "gateway", "model": "nace-ai/drex-v2.0"},
    {"provider": "clef",    "model": "clef-flash"},
    {"provider": "tactical"}
  ],
  "budget": {"max_calls": 400, "max_usd": 0.50}
}
```

- `rules`: a path relative to `arena/`.
- `seed`: the same seed and the same choices give the same game.
- `seats`: exactly four seats, `P0` to `P3`. A local bot has no `model`.
- `budget`: `0` means no limit. Arena checks the budget before each call.

Arena rejects unknown keys, a seat count that is not four, unknown
providers, and remote seats without keys.

Examples are in [`matches/`](matches/):

| File | Players |
|---|---|
| `bots.json` | Four local bots. No keys. |
| `example.json` | `openai`, `jev`, `clef`, `pplx` |
| `gateway.json` | Four gateway models that work on the free tier |

## 4. Players and models

### Local bots

These bots need no keys and no network:

`tactical`, `balanced`, `greedy`, `aggressive`, `random`, `collector`,
`early_support`, `prestige_farmer`, `counterleader`, `balanced_se`

### Remote providers

| Provider | Default model | Other models | Timeout |
|---|---|---|---|
| `openai` | `gpt-6-luna` | — | 20 s |
| `jev` | `jev-latest` | — | 10 s |
| `clef` | `clef-flash` | `clef` | 30 s |
| `pplx` | `pplx-decider-v1.3` | `pplx-decider-v1.2`, `pplx-decider-flash-v1.3`, `pplx-decider-flash-v1.2` | 65 s |
| `gateway` | `nace-ai/drex-v2.0` | All models in [`arena/providers/gateway.py`](arena/providers/gateway.py) | 65 s |

The gateway uses `vendor/model` IDs, for example `baseten/elephant-1`. The
wizard shows the list. Arena refuses a gateway model that has no price,
because the budget needs a price.

On 2026-11-16, the gateway free tier blocked these models (HTTP 403):
`google/gemini-decision-1`, `liquid/d1`, `microsoft/microsoft-decision-1`,
`openai/gpt-6-luna-decisions`, and all `typesafe-ai/jev` versions. Paid
credits are necessary for them.

### What a model receives

A model sees only public information: the projection of the public
observation of its seat, and a shortlist of up to 16 legal actions with
descriptions. The model selects one action ID. Arena makes sure that the
action is legal. The engine controls the dice, the rules, and the result.

## 5. Budgets and failures

- Arena checks `max_calls` and `max_usd` before each remote call. When a
  limit is reached, the game stops and Arena marks it as incomplete.
- When a call fails (error, refusal, timeout, or illegal answer), Arena
  tries again one time. When the second try also fails, the game stops and
  Arena marks it as incomplete. Arena does not replace a failed answer with
  a bot move.
- When you push Ctrl-C, the game stops. Arena writes the result as
  `interrupted` and shows the scoreboard.

Costs are estimates from the price tables in the provider files. Make sure
that the prices are correct before long runs.

## 6. Run logs

Each game writes a directory:

```
arena/runs/<UTC time>-arena-<seed>-<rules hash>/
├── match.jsonl        all data for each turn, one JSON object per line
└── engine/
    ├── events.jsonl   engine record of each action
    ├── state.json     last full engine state (contains hidden information)
    ├── metadata.json  seed, turn order, engine version
    └── rules.snapshot.json
```

Git ignores `runs/`. A game with bots makes approximately 2.5 MB of log. A
game with remote models makes more, because the log also keeps each request
and response.

### `match.jsonl`

The log has these lines, in this sequence. The log schema is
`arena-match-v1`.

| `type` | When | Contents |
|---|---|---|
| `match_start` | One time, at the start | `schema`, `game_id`, `seed`, the seats, the budget, `engine_version`, and `rules` with `path`, `rules_hash`, and the full rules in `doc` |
| `decision` | One time for each turn | See below |
| `failure` | When a game stops on an error | The seat, the error, `attempts`, and what the seat saw |
| `result` | One time, at the end | `outcome`, `winner`, `end_reason`, the statistics for each seat, and `engine_result` (the full engine result) |

A `decision` line is a complete training example. It contains:

| Field | Contents |
|---|---|
| `seat`, `provider`, `model`, `round`, `turn_id`, `phase`, `seq` | Who decided, and when |
| `observation` | The full public observation of the seat, with all legal actions |
| `projection` | The game state in the form that the models receive |
| `candidates` | The shortlist for the models, with descriptions and features |
| `attempts` | Each try: `ok`, the error, and `exchange` with the exact `request` and the raw `response` |
| `action_id`, `action_kind`, `action_summary` | The selected action |
| `probabilities`, `p_chosen`, `confidence` | The full distribution from the model, and its confidence |
| `latency_ms`, `usage`, `cost_usd`, `attempt`, `reason` | Timing, tokens, and cost |
| `play` | The engine record of the action: dice, path, events, and positions after the action |

The bots write the same lines. Their `attempts` and `probabilities` are
empty, because the bots do not call a model.

The log never contains keys or HTTP headers. A test plants a secret in the
engine state and makes sure that the secret is not in a request or in
`match.jsonl`. Only `engine/state.json` contains hidden information.

Examples with [jq](https://jqlang.org/):

```bash
RUN=runs/<your run>

# The selected action and the confidence of each model decision
jq -c 'select(.type=="decision" and .model!="local")
       | {turn_id, seat, model, action_summary, confidence}' $RUN/match.jsonl

# The game result
jq 'select(.type=="result") | {outcome, winner, end_reason}' $RUN/match.jsonl
```

## 7. Rules files

Arena loads the rules from a JSON file in [`rules/`](rules/). The loader is
strict: the file must contain all the keys in
[`rules.schema.json`](rules.schema.json), and it must not contain unknown
keys. An error message gives the parent of a bad key.

`rules/v0102.json` is the current design (V0.10.2 big board). It has the
same values as `../rules_v0102_bigboard.json`, and it also gives the five
values that the engine supplied before: `claim_required_equipment`,
`set_completion_reward`, `proclaim_cost`, `ability_stacking`, and
`gate_rotation`.

To try a rules change, copy a rules file into `rules/`, change the values,
and select it in the wizard or in a match file. The engine accepts exactly
four players.

## 8. Development

```bash
cd arena
uv run pytest
```

The tests use no network. Test doubles replace the HTTP clients.

The live contract tests send one real request to each provider that has
keys. They spend a small quantity of money, so they run only when you ask:

```bash
ARENA_LIVE_CONTRACT=1 uv run --extra decisions pytest tests/test_live_contract.py -s
```

### Code map

| Path | Purpose |
|---|---|
| [`arena/cli.py`](arena/cli.py) | Entry point `arena` |
| [`arena/ui.py`](arena/ui.py) | Setup wizard, live stream, scoreboard |
| [`arena/match.py`](arena/match.py) | Match file, budget, game loop, `match.jsonl` |
| [`arena/engine_adapter.py`](arena/engine_adapter.py) | Thin adapter over the Dioclet engine |
| [`arena/rules_loader.py`](arena/rules_loader.py) | Strict rules loader |
| [`arena/providers/`](arena/providers/) | The provider contract, local bots, and remote adapters |

All providers use one contract: `decide(view) -> Decision`. The `jev`,
`clef`, and `pplx` adapters share the System One core in
[`systemone.py`](arena/providers/systemone.py). The `gateway` adapter uses
the OpenAI Decisions adapter with the gateway URL.

Arena uses the engine in the repository root as a uv path dependency
(`dioclet-engine`). Arena does not have its own copy of the rules logic.

### Add a provider

1. Add a module in `arena/providers/` with a `build(model)` function. The
   function returns an object with `name`, `model`, `timeout_s`, and
   `decide(view)`.
2. Put the price in USD for each million input tokens, so that the budget
   can operate.
3. Return the exact request and the raw response in `Decision.exchange`, and
   put them on each `ProviderError` that you raise.
4. Add the provider to `REQUIRED_ENV`, `REMOTE_PROVIDERS`, and
   `DEFAULT_MODELS` in [`arena/providers/__init__.py`](arena/providers/__init__.py).
5. Add fixture tests and one live contract test.

The design plan is in [`PLAN.md`](PLAN.md).
