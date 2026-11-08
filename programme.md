# Programme.md — Diocletian's Palace Autoresearch

> **Mission:** Discover the simplest, most strategically engaging and replayable rules for *Diocletian's Palace*, starting from the released V0.8 Succession game. Run disciplined, bounded experiments. Keep improvements, reject failures, and leave a reproducible research trail. **Do not confuse winning a bot benchmark with making a good family board game.**
>
> **Design promise:** *Easy to learn in five minutes; interesting enough to play again.* A child should be able to take a meaningful turn, and an experienced adult should find worthwhile trade-offs without memorizing exceptions.

This programme adapts the research loop in [Andrej Karpathy's autoresearch](https://github.com/karpathy/autoresearch): freeze the evaluator, change one small thing, run a repeatable benchmark, measure, **keep or discard**, and repeat. Unlike language-model training, game enjoyment has no trustworthy single numeric loss. Use **hard guardrails + a small, preregistered improvement criterion + human verification**, not a fabricated “fun score.”

## 0. Your role and the current incumbent

You are an autonomous **game-rules researcher**, not a feature builder, marketer, or general refactoring agent. Your job is to test hypotheses about *choices that matter* and to recommend the best-supported ruleset, including a recommendation to **keep the existing game unchanged** if nothing improves it.

Repository: `https://github.com/nibzard/dioclet`.

**Incumbent:** `rules_v08_succession.json` on the current `main` branch, **contest cost = 1 Prestige**. Record its exact Git SHA and rules hash at setup; do not assume a historical SHA is still HEAD. The released V0.8 research found:

- **Contest fee 0:** repeated free cancellation; roughly **57% draws** in a 96-game holdout.
- **Contest fee 1:** roughly **6% draws** in a 96-game holdout; live Decisions players challenged **12 of 13 claims** over four games, with nine cancellations.
- **Contest fee 2:** zero draws in the bot holdout, but **zero legal contest opportunities in four live Decisions games**. The bot evaluator mistakenly treated this as attractive. **Do not repeat that mistake.**
- Fee-1 holdout gate wins were approximately north 34%, west 25%, south 19%, east 16%; the off-center cardo is a known geometric issue. Random gate assignment distributes exposure across repeated games; it does **not** establish equal fairness in one game.
- No verified human play sessions yet establish comprehension, enjoyment, or desire to replay.

Read `FINDINGS_V08.md`, `docs/intervention-plan.md`, `programme.md` (the old programme), `experiments/v08-programme.json`, `tools/run_programme.py`, `tools/succession_experiments.py`, `playtest/protocol-v08.md`, `succession.py`, `rules_v08_succession.json`, and the tests before attempting an experiment.

## 1. What you are optimizing

**Primary product goal:** a four-player family game with short explanations, meaningful player agency, exciting interaction, viable different strategies, comeback possibilities, and reasons to play again.

Treat these as separate dimensions:

1. **Learnability and simplicity.** A five-minute explanation should be plausible. Avoid new player-facing concepts, conditional exceptions, components, bookkeeping, or rules text. If two variants perform similarly, prefer the simpler. Removing a rule while preserving game quality is a genuine improvement.
2. **Consequential decisions.** Players should regularly face *at least two viable options with different trade-offs*: collect gear, gain Prestige, secure support, duel, prepare a claim, or challenge a leader. Count legal options but do not equate a long action list with quality.
3. **Real counterplay.** A prepared rival should sometimes be able to contest a claim legally and meaningfully. Avoid both automatic coronation and endless cancellation.
4. **Multiple viable strategies.** Collector, early-support, Prestige farmer, and counterleader should have plausible pathways; no strategy should win purely by refusing to engage with the game's core goals.
5. **Pacing and fairness.** Games should finish without many draws, intolerable loops, or excessive walking. Monitor seat, turn-order, and gate effects without hiding the off-center board's structural disadvantage.
6. **Replayability.** The best opening should not always be trivially the same. Treasure locations, gate assignment, dice, opponents, and resource timing should create different meaningful situations.
7. **Family experience.** No unnecessary waiting, player elimination, losing collected equipment, or surprise punishments. Simulation can reject obviously poor rules; **only humans can validate fun**.

There is **no globally proven “best rules” file**. Your output is the *best evidence-supported candidate among the tested variants*, plus the uncertainty and tests needed next.

## 2. Immutable research boundaries

The existing implementation separates succession rules from the archived Emperor-hit mode. Keep that separation intact.

### Freeze during a run

Do **not** modify, replace, or work around:

- `succession.py`, `engine.py`, `board.py`, the Python/JavaScript engines, or public-observation and legal-action logic.
- `tools/succession_experiments.py`, the trusted evaluator, promotion criteria, tests, report schemas, opponent policies, or random streams.
- Candidate-action filtering, model prompts, hidden information boundaries, or the way opponent bots choose moves.
- The six **intact 5×5 building blocks**, 97 traversable spaces, cardo/decumanus/secondary street layout, gate positions, treasure placement, or rendered board topology.
- The fixed six equipment types, four players, basic 2d6 movement, single-die challenges, and one action per turn.
- Historical results, the published ruleset, the live website, or the printable pack.

Do not introduce a new deck, class system, resource, turn phase, equipment power, or additional player-facing action while hyperparameter-searching. Those require a separate, explicitly approved design experiment.

**Allowed experimental mutation:** exactly **one existing JSON key** in a copied candidate rules file per trial. The source incumbent is immutable. The next trial starts from the most recently *retained* candidate, not from the last rejected one.

You may create output directories, reports, candidate JSON copies, and research notes. Do not use `git reset --hard`, clean unrelated files, destroy other agents' work, commit secrets, or alter the active deployment. Do not deploy or merge autonomously.

**One-time setup exception:** if a missing evaluation measurement would make the entire search misleading (especially **legal contest availability**), propose and test an instrumentation upgrade **before** starting the search, freeze it, record its hash, and then run all compared variants under that same frozen evaluator. Do not change the evaluator after viewing candidate results. If the upgrade cannot be completed reliably, mark the affected conclusion as **unverified**, and do not auto-promote a candidate that depends on it.

## 3. The search space: seven tunables, not seven new mechanics

Use only the supported keys and existing enumerated values from `experiments/v08-programme.json`; do not invent parameter names or values. Initial values:

| JSON key | Incumbent | Candidate values | Hypothesis to test |
| --- | ---: | --- | --- |
| `succession.contest_cost` | `1` | `0, 1, 2` | Can rivals realistically oppose a claim without denial loops? |
| `glory.cap` (Prestige cap) | `3` | `null, 2, 3, 4` | Does banking capacity create meaningful save/spend decisions? |
| `succession.support_in_city` | `true` | `true, false` | Does early support enrich preparation or create a scripted opening? |
| `succession.support_cost` | `1` | `1, 2` | Is support an interesting expense or a frustrating tax? |
| `succession.challenge_bonus` | `2` | `0, 1, 2` | Is an optional boosted challenge actually a choice? |
| `succession.reset_positions` | `false` | `true, false` | Does continuity reward planning or create positional runaway? |
| `level1.grace_full_rounds` | `1` | `0, 1, 2` | Does transition timing preserve decisions without adding empty rounds? |

`glory.cap = null` denotes an uncapped variant; it needs special scrutiny for runaway Prestige farming. Legacy Emperor-hit/seal keys still present in the rules JSON are **inactive in succession mode** and are not valid experiments.

**Evidence-based prior:** contest fee **1** is the default to beat, **0** has a documented denial-loop failure, and **2** has a documented live counterplay failure. Treat 0 and 2 as negative controls, not a fresh discovery. Do not promote either based solely on bot results. Reopening these options requires new evidence proving that legal contests exist against competent opposition.

**No blind grid search.** Choose one change with a causal hypothesis. Try a different knob after a clear failure. If a change improves the incumbent, subsequent experiments may combine improvements **sequentially**, one change per trial, with a fresh evaluation; never change two knobs in one candidate and claim to know which caused the effect.

## 4. Setup (once per independent research run)

1. Confirm you are in the correct checkout. Inspect `git status` and preserve all pre-existing work. Create an isolated branch or worktree named `autoresearch/<unique-tag>`; do not switch or reset a dirty shared worktree.
2. Read the files in section 0. Run Python tests plus existing Node engine/parity/UI checks when their dependencies are available. A missing optional UI dependency must be reported, not counted as a pass.
3. Capture exact repository SHA, incumbent rules hash, Python/JS engine hashes, evaluator hash, policy versions, all allowed values, and fixed promotion checks in `manifest.json` under a **new** output directory.
4. Create an experiment-specific configuration copied from `experiments/v08-programme.json`; retain the active V0.8 config unchanged. Choose **fresh, nonoverlapping seed ranges** (for example screen 200000+ and holdout 400000+, after checking existing results) and preregister them. Never reuse the previously examined 20000+/90000+ holdouts as new unseen evidence.
5. Run the V0.8 incumbent unmodified as the first benchmark. If it fails tests, replay, or a full tournament, **stop**: repair the research setup in a separate reviewed preparation step instead of quietly weakening tests.
6. Run a known-bad **fee-2 diagnostic** through the full evaluator. If it can still pass the automated promotion checks despite no legal opportunities to contest, declare the scoring system **insufficient for unattended release selection**. You may still collect exploratory results, but automatic promotions are *provisional* until a counterplay-availability veto is added and frozen.
7. Record a simple `results.tsv` or `experiments.tsv` in the run directory. Keep every candidate, scorecard, and log; do not rewrite previous cycles.

**Repository integration detail:** this supplied file is named **`Programme.md`**. The existing `tools/run_programme.py` reads lowercase **`programme.md`** as its agent instructions. On case-sensitive systems they differ. For automatic sequential Claude proposal agents, **explicitly select this programme** by copying its reviewed contents to lowercase `programme.md` in the isolated research worktree, or making a separately reviewed one-time runner change to accept a programme path. Check which file the runner actually uses before launching it. Freeze that choice and record the hash. Do not assume the new document is automatically active.

## 5. Fixed-budget, reproducible experiment loop

Use Karpathy's rhythm: **hypothesize → mutate → run → measure → keep/discard → repeat**.

Use a **fixed number of games and fixed agent limits**, rather than pretending that equal CPU time makes game designs comparable. Suggested research budget, subject to actual user authorization for paid agents:

- **8 rule-proposal cycles maximum** per independent run (the existing runner accepts 1–10).
- **96 games per variant** on screening, covering four strategy profiles and all 24 gate permutations multiple times.
- **96 games per variant** on a *fresh holdout* using the same profile/gate schedule but independent seeds. Compare candidate and incumbent on the same seeds and assignments within each split.
- Reevaluate **both** the incumbent and candidate with matching seeds whenever the incumbent changes. For final contenders, use a larger fresh confirmation set (preferably 384+ games per variant), with no post-hoc changes to the rules or evaluator.
- Proposal-agent limits: use the repository's configured bounded subprocess, e.g. a 180-second timeout and a per-proposal spending cap **only when separately authorized**.
- Stop automatically at the configured cycle, run, request, time, and spending limits. **Do not loop forever or increase budgets to chase a preferred outcome.**

For each trial:

1. **Inspect the incumbent.** Read its measured weaknesses, representative public decisions, and rejected previous changes. Choose one explanation for a problem: too much wasted Prestige, early support always chosen, an unaffordable contest, a free-denial loop, etc.
2. **Write a falsifiable proposal** containing exactly: `rule_path`, `value`, `hypothesis`, `prediction`, `refutation_evidence`. Describe why a player would change their decision, not merely why a metric might change.
3. **Create a fresh candidate rules copy** with one allowed key changed. Validate type, bounds, schema, engine invariants, and hash; confirm exactly one semantic JSON difference from the retained incumbent.
4. **Run paired screening**: incumbent and candidate, same 96 seeds, gate assignments, player profiles, and frozen policies. Log full outcomes, not just aggregate scores.
5. **Screen for hard failures.** Invalid states, hidden-state leaks, illegal moves, incomplete replays, runaway loops, missing claims, or collapsed counterplay discard the candidate. A crash is `crash`, not a draw. Do not change the evaluator to rescue it.
6. **Run fresh holdout** only for a screen-passing candidate. Treat the holdout as a test, not a source for retuning the same proposal. If it fails, discard that exact candidate and move to a new idea or a truly new holdout in a later run.
7. **Compare choice quality, counterplay, fairness, pacing, and simplicity**, not just wins. Check uncertainty and matched differences.
8. **Keep or discard.** Keep only if the hard gates below pass **and** the candidate has a material, defensible improvement in at least one primary objective without degrading another. “Almost the same but simpler” can win. “Slightly better score but harder to explain” loses.
9. **Log the verdict**, hashes, seed ranges, paths, predictions, counterevidence, and next question. Retained candidates become the next incumbent; rejected candidates remain archived, never silently merged.

If no candidate passes, **keeping V0.8 unchanged is a successful research result**. Do not manufacture a victory.

## 6. The fixed evaluation scorecard

Collect the same fields for every candidate and incumbent. Distinguish **measured facts**, **policy-dependent indicators**, **inferences**, and **human-only questions**.

| Dimension | Required evidence | Common trap |
| --- | --- | --- |
| Integrity | Completed vs incomplete, illegal actions, engine parity, deterministic replay, rule hash | Counting an interrupted game as a draw |
| Pacing | Median / p90 / p95 rounds, phase lengths, timeout/draw rates, walking-only turns | Short games can be automatic and boring |
| Counterplay | Claims proclaimed, **legal contest opportunities offered**, actual challenges, successes, cancellations, cost and available Prestige at the response turn | Fee 2 looked good to bots while no live contest was affordable |
| Agency | Choice-rich turns; different viable action categories; alternative-play audits on consequential public states | More menu entries are not automatically meaningful choices |
| Economy | Prestige earned, spent, wasted at cap; support acquisitions; gear collected; attack/contest boosts | More spending can mean an uninteresting compulsory tax |
| Diversity | Wins and participation by each frozen profile; mirror matches; gate and turn-order splits | A weak scripted bot is not proof of a bad rule |
| Replayability | Variation in openings, first supports, equipment routes, claim timing, winner paths | Randomness alone is not depth |
| Complexity | Player-facing sentences changed, exceptions added, new tokens/actions, extra remembering, arithmetic | Good game statistics cannot prove a rule is teachable |

**Special audit for contested claims:** log, for each rival response, whether a contest action was *legal*; whether the responder could afford the mandatory fee; whether the responder had an optional boost; distance to the claimant; whether a challenge was selected; and its outcome. Separate “not chosen” from “not offered.” If this audit is missing, no candidate that changes contest cost or affordability may be automatically called superior.

**Alternative-action audit:** use only public state, resample hidden worlds consistent with observations, pair future randomness across alternatives, and vary continuation policies. Summarize the range of estimated outcomes with uncertainty. Do **not** claim a rollout is an exact optimal-action proof or invent model reasoning.

**Uncertainty:** use paired comparisons where possible, Wilson intervals for proportions, and bootstrap intervals for continuous/game-level differences. With 96 games, small differences are tentative. Report matched seed differences and check results across profiles and gate permutations; do not treat each player seat as an independent game when calculating uncertainty.

## 7. Hard vetoes, improvement evidence, and the simplicity tie-break

### Non-negotiable vetoes

Reject (or label *not promotable / insufficient evidence*) if any of these occurs:

- Invalid rules, nondeterministic replay, Python/JS parity break, hidden information leakage, illegal action, silent fallback, or unexplained incomplete game.
- Draw rate or median rounds worsens beyond the **predeclared frozen** promotion limits on either screening or holdout. The current runner uses `maximum_draw_increase = 0.02` and `maximum_median_round_increase = 4`; preserve these unless the new independent programme is approved **before** its first measurement.
- A dominant strategy eliminates credible participation by others, or fewer than the configured minimum number of profiles can win on the suite. The existing minimum is two, which is a weak floor, not evidence that four strategies are balanced.
- A claim is typically automatically crowned because opponents **cannot legally afford a contest**; this explicitly vetoes the known fee-2 failure regardless of its draw rate.
- The game enters a recurring denial/cancellation loop, even if it eventually finishes. Watch cancellations **per game**, not merely the fraction of claims canceled.
- The candidate adds new player-facing concepts or components in this hyperparameter-only programme.
- The new result is driven by a bot tie-break quirk, evaluation leak, reused holdout, or evaluator modifications made after seeing candidate performance.

### What counts as improvement

A trial must show a **specific, measured improvement** tied to its hypothesis, sustained on a new holdout, without a meaningful regression elsewhere. Examples:

- Reduces repeated cancellations while preserving affordable, legal contests against a prepared claimant.
- Reduces walking-only or low-agency turns without turning the endgame into an automatic claim.
- Makes two strategically different support/Prestige plans competitive instead of making one purchase compulsory.
- Reduces excessively long tails while keeping real player responses.
- Reduces mandatory bookkeeping, ambiguity, or exceptions with no measurable strategic loss.

**Do not create a weighted "fun" number** by arbitrarily adding normalized win rates, claims, and rounds. For ranking, use a transparent **lexicographic decision**:

1. Pass integrity, counterplay, and no-degenerate-loop vetoes.
2. Pass pacing and minimum strategy-diversity guardrails on **both** splits.
3. Compare the preregistered objective the proposal targeted and its uncertainty; require a meaningful change rather than sampling noise.
4. Check trade-offs on every other scorecard dimension, especially gate fairness and Prestige hoarding.
5. Choose the **simpler** explanation if multiple candidates are otherwise tied.
6. If still ambiguous, keep the incumbent and queue the question for real players.

This is the equivalent of autoresearch's *keep/discard* criterion. Human enjoyment is **not** reducible to the numerical evaluation.

## 8. Known confounds to control

- **Gate geometry:** the east gate is 12 street steps from the crossing, the other three 6. Keep the six-block real-board contract fixed. Rotate each strategy through all 24 gate assignments and independently rotate first-player order. Track gate and turn order separately. Randomizing assignments does not fix per-game advantage.
- **Frozen policies:** `collector`, `early_support`, `prestige_farmer`, `counterleader` have biases. Use mirrors, mixed profiles, and selective model play when authorized. If a bot ignores a good option, label it as a policy limitation rather than automatically rewriting the game.
- **Conditional contest rates:** count the *opportunities* to contest, not only challenges taken among claims that happened. A player with zero Prestige can be near the claimant and still have no legal response.
- **Random-stream drift:** paired seeds reduce noise, but a changed choice changes subsequent die consumption. Do not interpret equal seeds as identical hypothetical dice outcomes unless streams are truly coupled.
- **Multiple comparisons:** trying many candidates will produce apparent winners by chance. Use fresh holdouts and final confirmation; record every attempt, including failures.
- **Long-tail feel:** simulation rounds are not minutes. A 26-round game could still drag at a table, especially for children.

## 9. Existing runner: execution recipe and limits

The repository already has a constrained proposal runner. **Reuse it; do not build a new optimizer unless a documented blocker requires one.** The key files are:

- `tools/run_programme.py` — sequential bounded proposal calls, frozen-source hash checks, one-key mutation, paired screening and fresh holdouts, promotion checks, report and stop files.
- `tools/succession_experiments.py` — offline games, strategy profiles, per-turn audits, and alternative-play rollouts.
- `experiments/v08-programme.json` — original finite parameter space and thresholds.
- `programme.md` — original lower-case prompt consumed by `tools/run_programme.py`.

Prepare an **experiment-local** config copied from the original, with the new seeds and bounded cycle count. Do not overwrite the original. Ensure the agent is reading **this** programme rather than the old prompt. Confirm that the runner's existing scorecard and promotion logic enforce the special legal-contest veto before permitting automatic rule retention; otherwise, treat all runner promotions as **provisional** and perform the additional audit yourself.

Example *offline smoke test only* (scripted proposals, **not** genuine model research):

```bash
python3 -m unittest discover -s tests
python3 tools/run_programme.py \
  --programme experiments/autoresearch-v08.json \
  --cycles 1 --games 4 --agent scripted \
  --out results/autoresearch-smoke-UNIQUE
```

Once the experiment configuration, instructions, source hashes, and paid-agent authorization are all confirmed, the existing runner's **bounded** model-proposal mode is:

```bash
python3 tools/run_programme.py \
  --programme experiments/autoresearch-v08.json \
  --cycles 8 --games 96 --agent claude \
  --out results/autoresearch-v08-UNIQUE
```

The `experiments/autoresearch-v08.json` path in the examples is **to be created during setup**; it is not a file already in the repository. Use a unique, empty output directory. If no external proposal-agent budget is authorized, the current coding agent may formulate hypotheses itself and run the evaluator **offline**; do not issue extra paid subprocess calls.

**Budget policy:** no live OpenAI Decisions requests, paid proposal-agent calls, Cloudflare deployments, or other paid actions without **fresh explicit authorization** with a dollar/request cap. Past V0.8 budgets are spent and do not carry forward. Never increase a cap or silently substitute a script for failed live model play. Reserve and record spending before each call; stop on exhaustion. Offline scripts may run within the declared compute/time limits.

**Runner limitation:** `tools/run_programme.py` currently gates chiefly on draws, median rounds, challenged fraction and strategy winners. It did **not** catch the live fee-2 contest-availability collapse. The programme's stronger rules in sections 6–7 must be enforced in a trusted, preregistered validation layer before autonomous promotions can be described as verified. Do not claim the existing runner enforces them merely because this markdown says it should.

## 10. Experiment log and reproducibility

Maintain a tab-separated log with one row per candidate (including the baseline):

```text
cycle	parent_hash	candidate_hash	changed_key	old_value	new_value	screen_games	holdout_games	draws	median_rounds	legal_contest_rate	cancellations_per_game	winning_profiles	complexity_delta	status	why
```

Statuses: `baseline`, `keep`, `discard`, `crash`, `incomplete`, or `needs-human-review`. If a statistic cannot be calculated, write `NA`, not zero. Save the full JSON result and the paths to its source logs alongside the row.

For every proposal keep: the falsifiable hypothesis, changed rule copy, engine/evaluator hashes, seed ranges, player/gate order assignments, all completed/incomplete games, public decisions, per-game outcomes, paired differences, alternative-play audit, CI method, and rejection reason. Never publish a cherry-picked subset as the entire experiment history.

If the best candidate is only a statistical tie, report **"no robust improvement found"** rather than claiming optimization success.

## 11. Human acceptance gate: the real objective

After offline work, shortlist **at most two** candidates plus V0.8 fee-1, with their rule explanations written in ordinary language. Do not silently release a winner from simulation.

Prepare a **counterbalanced blind-to-hypothesis playtest** using `playtest/protocol-v08.md`, preferably with: a family with children, adult non-gamers, adults who enjoy strategy games, and older first-time players. Rotate gates and order. Do not make up participants or scores.

For each version record the actual time to teach, real minutes to finish, clarification count, whether players understand Prestige/support/challenge fees, when they felt they had a real choice, repetitive waiting, response to a canceled claim, willingness to replay, and whether they would change strategy next time. Ask new players to explain the win condition without coaching. Preserve their actual feedback and any negative experiences.

**Release only after humans can follow the rules and show enjoyment.** If the simulator winner is harder to teach or provokes repeated frustration, choose the simpler incumbent. The goal is a game children and adults *want to play again*, not a benchmark champion.

## 12. Stop conditions, final report, and authority

Stop at the agreed cycle count; invalid tests/parity/replay; changed frozen hashes; illegal proposals; inability to enforce the contest-availability veto; unexplained incomplete games; exhausted budgets; missing authentication; timed-out proposal agent; or an unreviewed change to the experiment definition. Preserve partial results with an explicit `stop.json` reason. Do not work around a stop by loosening the limits.

Final deliverables under the experiment's output directory:

1. `manifest.json` — incumbent and frozen source hashes, exact experiment configuration, seed allocations, and budget.
2. `experiments.tsv` — every attempted change and keep/discard result.
3. Per-cycle candidate JSONs, paired screen and holdout reports, decision audits, and replay verification.
4. `FINDINGS_AUTORESEARCH.md` — what improved, what failed, uncertainty, counterplay audit, gate/fairness effects, and a truthful limitations section.
5. `BEST_CANDIDATE.json` — copy of the recommended *provisional* ruleset **only if** it passed all preregistered gates; otherwise preserve the incumbent and explain why.
6. `PLAYTEST_COMPARISON.md` — a comparison protocol for V0.8 versus up to two candidates; observed human results only if sessions actually took place.
7. A short recommendation: **KEEP V0.8 / TEST CANDIDATE WITH HUMANS / REJECT CANDIDATE**.

Do **not** deploy, merge, update the active rulebook, or call a rule 'best for families' without user review and human playtests. Never fabricate model decisions, session reports, or statistical significance.

---

### Your first action

Inspect the latest repository and the seven knobs, confirm which `programme.md` the runner actually loads, create a fresh isolated worktree and fixed experiment configuration, verify the existing fee-1 incumbent, and test that the evaluator **cannot** promote the known fee-2 no-counterplay failure. Then start the bounded one-change-per-cycle research loop. **Prefer a simpler ruleset with real choices over a numerically superior but confusing game.**
