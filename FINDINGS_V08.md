# V0.8 findings: the succession prototype

Date: 2026-11-08. All numbers come from the result directories named
below. Every simulation number is offline bot play unless the line
says live. Live games used the OpenAI Decisions harness
(`gpt-6-luna`) under the shared caps `$0.75` and 1,200 requests
(`results/v08-live-budget.json`).

## What works and what is live

- The V0.8 succession mode is finished, tested, and released with a
  contest fee of 1 Prestige (`rules_v08_succession.json`, hash
  `892a1f64…`).
- The browser game is live at
  `https://dioclet-board.nikola-balic.workers.dev`
  (version `85717cd3`). It serves the fee-1 rulebook and rules.
- The print-and-play pack (`playtest/playtest-pack.html`) teaches
  the same fee.
- Test state: 188 Python tests pass. The four JavaScript suites pass
  (legacy engine, succession engine, Python/JavaScript parity, jsdom
  UI). A full Chromium session played a fee-1 game to game over with
  zero console errors.
- The fee decision: fee 0 loses to a free-denial loop, fee 2 removes
  live counterplay. Fee 1 keeps both sides of the contest. See below.

## The fee ladder under bot play

Paired screens (seeds 20000+) and fresh holdouts (90000+), 96 games
per suite, four strategy profiles over 24 gate permutations.

| Measure | Fee 0 | Fee 1 | Fee 2 |
| --- | ---: | ---: | ---: |
| Draws, screen / holdout | 0.63 / 0.57 | 0.03 / 0.06 | 0.00 / 0.00 |
| Median rounds, holdout | 40 | 26 | 21 |
| Claims challenged (holdout) | 0.99 | 0.99 | 0.84 |
| Canceled claims per game | 25.4 | 8.8 | 1.9 |
| Winning profiles | 4 | 4 | 4 |

Sources: `results/v08-contestcost-001` (fee 0 vs 1, seeds 90000),
`results/v08-programme-001` cycles 01 and 02 (fresh holdouts 91000,
92000). At fee 1 the holdout win rates were collector 33%,
counterleader 31%, early support 19%, Prestige farmer 10%. At fee 2
they were 27%, 25%, 31%, and 17%. No profile collapses under either
fee.

Gate win rates at fee 1 (holdout): north 34%, west 25%, south 19%,
east 16%. At fee 2 the spread narrows to 23–29%. The east gate sits
12 steps from the crossing; the other gates sit 6. This is the known
off-center-cardo geometry, not a fee effect. Street changes are out
of scope for this programme.

## The deciding evidence: live Decisions play

Two bounded live runs, four games each, four live seats, shared
ledger.

| Measure | Fee 2 (seeds 130000+) | Fee 1 (seeds 140000+) |
| --- | ---: | ---: |
| Games finished / incomplete | 4 / 0 | 4 / 0 |
| Claims proclaimed | 4 | 13 |
| Claims challenged | 0 | 12 (92%) |
| Claims canceled by a challenge | 0 | 9 |
| Games won by acclamation | 4 | 4 |
| Draws | 0 | 0 |
| Game rounds | 16, 11, 5, 5 | 9, 23, 16, 14 |

Why fee 2 produced zero contests: the response logs
(`decisions.jsonl`) show that no responder was ever offered a contest
option. Contesting a claim costs the full fee before the roll, and
every responder held 0 or 1 Prestige at the response turn. Two
responders stood one step from the claimant, so distance was not the
blocker. The live claimants timed their proclamations against empty
rival purses, and the first claim won every game.

Fee 1 keeps the contest reachable: rivals need one Prestige, and 12
of 13 claims drew a challenge. Nine claims were canceled. The
endgame produced real fights, not silent coronations.

A contest at fee 1 plus the optional +2 boost costs 2 of the 3
Prestige cap. A contest at fee 2 plus the boost costs the whole cap.

## Programme run record

`results/v08-programme-001`: three configured cycles, two recorded,
run by `tools/run_programme.py` with one tool-free Claude proposal
agent per cycle.

| Cycle | Proposal | Decision |
| --- | --- | --- |
| 1 | `succession.contest_cost = 1` | promoted, all checks pass |
| 2 | `succession.contest_cost = 2` | promoted, all checks pass |
| 3 | agent call exceeded 180 s | stopped `agent_timeout` |

The cycle-2 promotion was later overturned by the live fee-2 probe
above. The promotion checks are mechanical guards on bot evidence;
they cannot see a counterplay collapse that appears only against
live opponents. This is the division of labor working as intended.

Both agent proposals arrived inside the permitted change space with
hypothesis, prediction, and refutation evidence filled in. The full
prompts, proposals, decisions, and suite metrics are in the cycle
directories.

## Alternative-play audits

`results/v08-altaudit-fee1` and `results/v08-altaudit-fee2`, three
audited turns each, 16 paired rollouts per alternative. Audited
turns offered competing choices of these kinds: move, explore, duel,
guard post, gain support, maintain claim.

- Fee 1: win-fraction spreads 0.03 to 0.47 across legal actions; the
  played action was the estimated best in 3 of 3 turns.
- Fee 2: spreads 0.03 to 0.81; the played action was the best in 2
  of 3 turns.

Small samples. They show that single turns carry real choice weight
under both fees, not that one fee plays better.

## Spending

- Live Decisions: `$0.3198` of the `$0.75` cap; 904 of 1,200
  requests; 3.20 M billed input tokens. Ledger:
  `results/v08-live-budget.json`.
- Claude proposal agents: two completed calls (58 s and 106 s), each
  capped at `$0.50` and 180 s. The CLI result envelope reports no
  cost fields, so the caps are the bound on record. The third call
  hit the 180 s timeout and the run stopped; no proposal was
  recorded for it.
- No scripted proposal was ever recorded as model output. Scripted
  proposals exist only in smoke runs and tests, and the run report
  labels them as such.

## Rejected variants

- **Fee 0** (`rules_v08_succession.json` before this release):
  free denial. 99% of claims challenged, 25 canceled claims per
  game, 57% draws, 40-round medians. The response window becomes a
  loop.
- **Fee 2** (`results/v08-programme-001/cycles/02/candidate-rules.json`):
  excellent bot numbers, but zero contests in four live games. No
  responder could legally pay. Rejected on live evidence; retained
  as a tested variant.

## Limits

- Offline suites are 96 games per arm. Wilson 95% intervals are in
  each `summary.json`. Strategy-rate differences under about 12
  points are inside the noise.
- Live probes are four games per fee. They settled the fee question
  because the fee-2 failure was total (0 of 4 games with any
  contest option offered), but they cannot rank gates or profiles.
- Bots idle about 28 to 30 moves per game, roughly a third of turns.
  Live Decisions players idled 60 to 87 times per game. Humans will
  likely walk less; treat idle counts as an upper signal.
- Nothing here measures human clarity, tension, or enjoyment.
  `playtest/protocol-v08.md` carries those questions.

## Open human questions

1. Does the 1-Prestige fee read as a strategic cost or a hidden
   rule at the table? (Protocol question 4.)
2. Nine of thirteen live claims were canceled. Does the canceled
   claimant feel punished or re-engaged when sent back to the gate?
3. The east gate won 16% of fee-1 holdout games. Do rotation
   playtests name it as the weak seat?
4. Idle moves: do humans report dead turns, and where?
5. Do players ever choose an ordinary free duel over other actions
   on purpose?

## Next playtest

Run `playtest/protocol-v08.md` against this release: the printed
pack, fee 1, the four-group plan, and the four-game gate rotation
with the adult strategy group. Record sessions in that file only.
