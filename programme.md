# Programme: test the succession game

Your task is to find game rules that create understandable, consequential choices for human players.

Do not confuse a bot winning, a high choice count, or a short game with human enjoyment. The purpose is to find promising mechanics, competing strategies, and useful questions for human playtests.

## Context and fixed requirements

Read `docs/intervention-plan.md`, `rules_v08_succession.json`, and the latest experiment report before proposing a change. The game has four claimants, six intact blocks, persistent equipment, Prestige, faction support, and a claim that rivals can contest.

Keep the six-block board fixed. Keep the cardo north–south, the decumanus east–west, and the four gates at their ends. Do not add streets, split a block, move a gate, change the evaluator, weaken a test, expose hidden equipment, or change bot code while comparing rule candidates.

Names and colors identify players. Gates are independently assigned. Compare all 24 assignments and independent player-order rotations. Never claim that random assignment removes a positional advantage.

## The experiment loop

1. Inspect the incumbent's results and representative public turns. Identify one causal problem, such as free denial, ineffective preparation, or a dominant farming strategy.
2. Propose one permitted rule change. State the predicted effect, the mechanism, and what result would count against it.
3. Let the trusted runner validate the candidate and run the fixed screening suite. The agent cannot edit scores, tests, logs, or engine code.
4. Compare paired results against the incumbent. Inspect strategy outcomes, gate outcomes, resource use, claims, cancellations, and alternative plays.
5. Validate a promising candidate on fresh holdout seeds. Each cycle uses a new holdout set; never tune against the same holdout after seeing its results.
6. Retain a candidate only when the fixed promotion checks pass on screening and holdout. Otherwise keep the incumbent and record the rejection.
7. Hand the evidence and unresolved questions to the next agent. Stop after the configured cycle count, time limit, or budget limit.

A retained candidate is a provisional mechanical improvement. It is not certified as balanced or enjoyable.

## Strategies to challenge

Compare collection-first, early-support, Prestige-farming, and leader-challenging policies. Include mirror games and independent gate assignments. Watch for a strategy becoming useless, one strategy winning by avoiding the main game, or two policies cooperating accidentally through fixed priorities.

Examine alternative legal actions at consequential turns. Resample hidden worlds compatible with public information and use paired future random streams for each alternative. Vary opponent continuation policies. Record truncated rollouts. A rollout win estimate is conditional on those assumptions, not an exact action value.

The model receives only public state and a diverse legal-action shortlist. It must see claims, support opportunities, and ways to oppose a rival. Do not show the hidden treasure mapping or future dice.

## Permitted changes

`experiments/v08-programme.json` contains the exact finite search space and thresholds. Change one path per cycle: contest cost, Prestige cap, early support, support cost, challenge bonus, position reset, or grace rounds.

The initial claim prototype allows free opposition. Initial simulations found repeated cancellation and many draws. A mandatory Prestige cost for contesting an active claim is a test candidate. Ordinary duels remain available under their normal costs. The optional roll bonus is a separate expense.

Do not add several new systems to rescue one result. A change outside the permitted space needs a separate proposal and experiment definition.

## Evidence to retain

Keep the exact rules, rule hash, source hashes, policy version, seeds, assignments, game logs, public choices, alternative-play audits, proposal, prediction, decision, and rejection reason. Never overwrite a previous cycle.

Report finished and incomplete games separately. Record draws, game length, equipment collected, support gained, Prestige earned/spent/wasted, claim attempts, cancellations, opponent responses, and outcomes by strategy and gate. Report sample sizes and uncertainty. An observation from four games is a diagnostic, not a balance result.

The fixed promotion checks guard against more draws, longer games, lost counterplay, or a collapse to one winning profile. They do not measure fun. When measures disagree, retain the incumbent and document the tradeoff for human review.

## Live play exercises

Use the repository's OpenAI Decisions harness with `gpt-6-luna`, the existing legal-action validation, and an explicit shared budget ledger. Use the correct succession objective. Preserve candidate probabilities as model outputs; do not invent a written rationale that the Decisions endpoint did not return.

Use live exercises to inspect plausible play and strategic alternatives. Small live samples do not establish win rates. Models are simulated players, not human participants. Do not label offline policies as live AI play, and do not replace failed live calls with bots while claiming a completed live game.

The first exercise has a total ceiling of $0.75 estimated API cost and 1,200 requests across all games and cycles. A persistent ledger reserves costs before calls and carries usage across restarts. Stop when that budget ends. Any later run must receive its own explicit budget.

## Run sequential unattended agents

Preferred bounded runner:

```bash
python3 tools/run_programme.py --cycles 3 --games 96 \
  --out results/v08-programme-001
```

The runner gives each fresh `claude -p` process this programme, the incumbent, prior evidence, and a strict JSON proposal format. Claude proposes a rule change. The runner applies it, runs experiments, and decides promotion using frozen checks. Agents run sequentially.

The equivalent proposal call uses the generated cycle prompt:

```bash
claude -p --tools '' --output-format json --max-budget-usd 0.50 \
  < results/v08-programme-001/cycles/01/prompt.txt
```

The `yolo` alias expands to `claude --dangerously-skip-permissions` on this machine. Noninteractive Bash does not load that alias. The bounded runner does not need it because proposal agents have no tools. Use the explicit `claude` command.

For a smoke test of the runner without a model call, use `--agent scripted --games 4`. These proposals are labeled scripted. They are not evidence that a model played or reviewed a game.

## Human playtest questions

After selecting a candidate, give new players the printed quick reference and ask them to explain their goal without coaching. Record where they hesitate.

Ask which turns had two appealing alternatives, whether equipment helped later, whether Prestige spending involved a choice, whether they could stop a leader, and whether they would try a different strategy next game. Record waiting and repetitive turns. Use that feedback to revise the experiment questions rather than calling a numerical score “fun.”

## Stopping and publication

Do not deploy, merge, commit, install software, or delete session data during an experiment cycle. Do not modify the active rules file. Write candidates and retained incumbents under the run's output directory.

Stop on invalid rules, changed source hashes, invalid actions, engine disagreement, exhausted budget, unavailable authentication, or a stalled agent. Keep partial evidence and report the stop. Do not expand the cycle count or spending cap to obtain a preferred result.

The final handoff names the retained candidate, rejected alternatives, evidence limits, and questions for human play. A separate release step updates the website, rulebook, print pack, and version together.
