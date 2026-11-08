# Autoresearch findings: V0.8 fee-1 ruleset

Run `autoresearch-ar1-001`, 2026-11-08. Offline bot experiments,
plus one user-authorized live Decisions comparison ($0.42 spent of a
$0.75 cap). No deployment, no live-rule changes. Every number
below comes from the archived suites under this directory. Every
offline game was re-run and replay-verified by the frozen audit tool.

**Recommendation: KEEP V0.8.** The live V0.8 rules stay as released
(fee 1, boost +2). The one offline survivor, `succession.challenge_bonus`
2 to 1, passed every preregistered offline gate and a 384-game
confirmation, then failed the live Decisions comparison
(section 8): live contests stop succeeding under the same empty
purses, and the endgame drifts toward first-claim coronation.
`BEST_CANDIDATE.json` is retained as an archived rejected artifact.
No rule change is recommended; the remaining questions go to human
playtests of the unchanged game.

## 1. Setup and the fee-2 verification

- Worktree `autoresearch/ar-fee1-20261108` at main `9ef8952`. The
  supplied programme is installed as the worktree `programme.md`
  (sha256 `4e7d30bc…`); the runner reads that path.
- Tests before any experiment: 188 Python tests, three Node suites,
  and the jsdom UI suite, all passing in the worktree.
- Incumbent: `rules_v08_succession.json`, hash `f6fb69a1…`, fee 1.
- Fresh seeds, preregistered: screen 200000+, holdouts 401000 to
  406000 by cycle, confirmation 600000+. No seed range was reused.
- New instrumentation, frozen before the search:
  `tools/contest_audit.py` re-runs every suite game and audits each
  claim response from public state. It records whether a contest was
  legal (offered), whether the fee was affordable, whether the boost
  was offered, what was chosen, and the duel outcome. The frozen
  evaluator and engine files are unmodified; their hashes are in
  `run-state.json`.

**Fee-2 diagnostic (before any candidate cycle).** The known-bad fee-2
variant went through the full evaluator. Result:

| Check layer | Screen | Holdout |
| --- | --- | --- |
| Existing mechanical checks alone | would promote | would promote |
| Added counterplay veto | rejected | rejected |

The mechanical checks still promote fee 2 (0 draws, median 21 rounds,
four winning profiles). The preregistered veto rejects it on both
suites: contests offered on 0.34 of response turns (floor 0.50,
incumbent 0.66), responders able to pay 0.44 to 0.46 (floor 0.60,
incumbent 0.78), and only 0.34 of incumbent response purses could pay
a fee of 2. At fee 2, 18 to 23% of claims were crowned with no
responder ever offered a legal contest (incumbent: under 1%). The
evaluation can no longer incorrectly promote the rejected variant.
Fee 0 and fee 2 also stay negative controls that bot evidence alone
may never promote.

## 2. Incumbent baseline (96 + 96 games, fresh seeds)

Draws 3.1%, median 24.5 rounds, contests offered on 0.68 of response
turns, 99% of claims had a legal contest option, 8.0 cancellations
per game, four winning profiles (collector 27%, counterleader 28%,
early support 25%, farmer 17% holdout). The +2 boost was an automatic
purchase: responders who could afford it bought it on 100% of
offered turns, and boosted contests won 77% versus 55% plain.

## 3. Experiment history

Six cycles, one key per candidate, each against the then-current
incumbent with paired screens and fresh holdouts. Full detail:
`experiments.tsv`, `cycles/NN/decision.json`, `cycles/NN/verdict.json`.

| Cycle | Change | Automated gates | Verdict |
| --- | --- | --- | --- |
| 1 | `succession.challenge_bonus` 2 → 1 | passed both suites | keep offline (amended, section 4); rejected on live evidence (section 8) |
| 2 | `succession.reset_positions` false → true | failed both suites | discard |
| 3 | `glory.cap` 3 → 4 | failed both suites | discard |
| 4 | `glory.cap` 3 → 2 | failed both suites | discard |
| 5 | `succession.support_cost` 1 → 2 | failed both suites | discard |
| 6 | `level1.grace_full_rounds` 1 → 0 | failed both suites | discard |

Cycle budgets 7 and 8 were not spent. Every remaining allowed value is
a negative control, a dead option, or a dominated extreme of a tested
direction. Running them would chase the budget, not a hypothesis.

**What the failures established:**

- Weakening the boost by one point (cycle 1) is the only change that
  cut cancellation churn enough to pass, because it attacks the
  strongest measured cause: a +2 boost that dominated equipment and
  was always bought when affordable.
- Returning pawns to gates at the transition (cycle 2) cuts the first
  claimant's edge but stretches every claim cycle: draws up to 7 to
  8%, cancellations up to about 9 per game. Position continuity is
  evidence-supported.
- A bigger bank (cycle 3) buys more boosted contests and more churn,
  not deeper saving decisions: cancellations rose to 9.25 per game
  and draws doubled.
- A smaller bank (cycle 4) barely dents churn. The churn is
  re-proclamation-limited, not purse-limited: proclaiming is free and
  support persists, so a canceled claimant walks back and proclaims
  again. Cap 2 also thinned counterplay slightly.
- Support at cost 2 (cycle 5) is a tax, not a choice. Purchase volume
  did not fall; games stretched to median 29 rounds; 5 games per
  suite ended the city phase with no player completing a set.
- The grace round (cycle 6) carries real decisions. Removing it saves
  one city round but hands out less transition equipment (4.41 to
  4.13 items), which the succession phase pays back with interest:
  total rounds flat or higher, screen draws doubled.

## 4. Correction to the cycle-1 verdict

The archived cycle-1 verdict said discard. It was wrong, and the
error is documented rather than hidden. The verdict compared the
candidate against baseline suites from *different seeds* (first
challenger 37.5%, farmer 16.7%) instead of the paired same-seed
incumbent suites. Programme section 8 names this exact confound.

Paired same-seed numbers: first challenger 55 → 52 (screen, lower)
and 41 → 49 (holdout, higher, inconsistent); farmer 6 → 5 and 7 → 11
(better on holdout); cancellations −30% and −25%; draws improved on
both suites. The driver's checks were paired and passed; this analyst
layer was not. The correction is in
`cycles/01/verdict-amendment.json` and `run-log.jsonl`.

## 5. Confirmation (384 paired games, fresh seeds 600000+)

Both arms on the same seeds, schedule, and policies. All 768 games
replay-verified.

| Measure | Incumbent (+2) | Candidate (+1) |
| --- | ---: | ---: |
| Cancellations per game | 8.00 | 6.22 (−22.2%) |
| Draws | 3.65% | 2.08% |
| Median rounds | 25 | 24 |
| Contests offered | 0.679 | 0.680 |
| Responders able to pay | 0.793 | 0.798 |
| Claims with a legal contest option | 99.5% | 99.5% |
| Claims crowned with no legal contest | 0.4% | 0.4% |
| Claims won by acclamation | 10.7% | 13.6% |
| Boosted-contest win rate | 0.77 | 0.65 |
| First challenger wins | 49.7% | 50.5% |
| Wins: collector / support / counter / farmer | 125/116/90/39 | 127/110/91/48 |

Section 8 supersedes this keep decision: the live comparison rejected
the candidate. This section records the offline evidence that stood
at the time.

This matches the programme's first example of a genuine improvement:
repeated cancellations fall while affordable, legal contests against a
prepared claimant remain. The boost stops being an auto-win button
for anyone holding 2 Prestige and becomes a marginal purchase
(+1 for 1 Prestige against a 1-Prestige duel reward). No other
measured dimension regressed. Complexity is unchanged: the same
sentence, one smaller number.

## 6. Fairness and strategy effects (384-game arm)

- The east gate is confirmed weak under both rules: 15.6% wins for
  the incumbent, 14.1% for the candidate (CIs overlap). The north and
  west gates win about 28 to 32%. This is the off-center cardo (the
  east gate sits 12 street steps from the crossing; the others 6).
  No permitted rule knob fixes geometry. Gate rotation across a
  session remains the correct mitigation; single-game equality is not
  claimed.
- The first challenger wins about half the games under both rules
  (49.7% and 50.5%). Comebacks exist but the collection head start is
  real. Humans may time proclamations differently than bots.
- The prestige farmer is the weakest profile under both rules (10.2%
  and 12.5% versus a 25% uniform share). Cap 4 made it worse, so its
  weakness is not the cap; the profile spends its Prestige on
  contests instead of converting position into claims.

## 7. Limitations

- Offline bot evidence only. Bots proclaim immediately and buy the
  boost mechanically. Live play at fee 1 produced about 2.3 canceled
  claims per game; bots produce 6 to 8. Treat churn numbers as
  upper bounds and relative comparisons, not human predictions.
- The improvement claim rests on paired seeds and shared schedules,
  but a changed action changes later die consumption. The streams are
  not identical hypothetical dice.
- 96-game suites carry wide intervals for profile and gate rates; the
  384-game confirmation narrows the headline comparisons only.
- Cycles 2 to 6 were tested against the pre-amendment incumbent
  (bonus 2). If the bonus-1 candidate survives human playtests, a
  follow-up run should re-test the most informative knobs against the
  bonus-1 base before any second promotion.
- Nothing here measures clarity, tension, or enjoyment. Only the
  human gate in `playtest/protocol-v08.md` can.

## 8. Live Decisions comparison (added after offline work)

User-authorized: $0.75 and 1,500 calls total, two arms, four live
`gpt-6-luna` seats per game. Spent $0.4243 over 1,172 calls. Arm A
(incumbent, +2) finished 6 of 6 games; arm B (candidate, +1) finished
4, with game 5 stopped mid-game at the call cap and recorded
incomplete. Parser `tools/live_contest_audit.py` was frozen before
the run and validated against the published V0.8 live probes
(fee 2: zero contests offered; fee 1: 12 of 13 claims challenged,
9 canceled). Full detail: `live/comparison.json`.

| Live measure, finished games | +2 incumbent | +1 candidate |
| --- | ---: | ---: |
| Claims per game | 4.67 | 1.25 |
| Contests offered per response turn | 0.47 | 0.24 |
| Contests chosen (turn level) | 28 | 4 |
| Contest win rate when chosen | 0.82 | 0.25 |
| Contests where the boost was affordable | 4 of 28 | 0 of 4 |
| Boost purchases | 4 of 4 affordable | 0 of 0 affordable |
| Cancellations per game | 3.83 | 0.25 |
| Claims crowned by acclamation | 18% | 80% |
| First challenger won | 0 of 5 | 4 of 4 |
| Median rounds | 32 | 19 |

Boost affordability is separate from contest volume: the boost costs
fee 1 plus challenge cost 1 in both arms. At +2, the four responders
who could afford it bought it every time — still an automatic
purchase when affordable. At +1, no responder at a contest ever held
2 Prestige, so the zero purchases reflect empty purses, not revealed
preference against the weaker boost.

**AR1.1 erratum.** The first version of this table and of
`live/comparison.json` counted claims and cancellations from all
games, including the +1 arm's stopped fifth game (which held 3
claims and 2 cancellations), while dividing by finished games. That
produced 0.75 cancellations per game instead of 0.25, and 50%
acclamations instead of 80%. Claim statistics now cover finished
games only, matching the evaluator's `claim_statistics_scope`.
Response purses are also reconstructed from every turn's Prestige
events; the first version missed rewards a defender earns on the
attacker's turn. The verdict is unchanged; the incomplete game is
preserved whole in `live/bonus1/base/`.

Every counterplay measure moved the same way. Live response purses
are thin (53% and 76% of turns at zero Prestige), so live contests
almost always run unboosted; at +2 the few affordable boosts were
bought and won, holding contest success at 82%. At +1 the same empty
purses meet a weaker boost, contest success falls to 25%, and the
first claim usually survives to acclamation. The offline gain came
from bots that auto-buy the boost on 82% of affordable turns and
hold richer purses than live players. This is the fee-2 lesson again
in miniature: scripted policies can mask an affordability-adjacent
failure that live play exposes.

Why this is a rejection rather than a mechanical veto: the offline
counterplay floors were calibrated on bot purses, and live purses are
thinner at every fee (the incumbent's own live offered rate, 0.47,
sits below the 0.50 bot floor). The floors do not transfer to live
play, so no gate fired. The rejection rests on the mechanism:
consistent degradation across boost use, contest success,
cancellations, acclamations, and game length, in the same direction
the cycle-1 bot run first showed.

## 9. Open questions for human playtesting

1. Live players bought the +2 boost on 14% of contests and the +1
   boost never. Ask humans why they pay or decline, and whether a
   paid +2 feels like strength or like a tax on the defender.
2. Do about two to four canceled claims per human game feel like
   exciting counterplay or like punishment? Watch the claimant sent
   back to the gate.
3. Does the east gate feel like the weak seat in a single game? Name
   it after four games with gate rotation.
4. The first player to complete a collection wins about half the bot
   games. Do humans punish that leader, or does the race feel
   decided at the transition?
5. The prestige-farmer plan (earn, hold, boost) wins least. Does any
   human choose it, and do they enjoy it?
6. Does the 1-Prestige contest fee read as a strategic cost or a
   surprise? (Carried over from V0.8; still unanswered.)

## 10. Reproducibility

`manifest.json` holds hashes, seeds, thresholds, and the veto.
`run-state.json` holds the frozen source hashes and cycle chain.
`run-log.jsonl` is the append-only event log. `experiments.tsv` is the
one-row-per-candidate history. Each cycle directory keeps the
proposal, candidate rules, paired suites, audits, decision, and
verdict. The fee-2 diagnostic is under `diagnostic/`. The
confirmation arms are under `confirmation/`.
