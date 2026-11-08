# Contest-cost comparison: 0 versus 1

Date: 2026-11-08. Offline policy probes (`offline-bots` provider);
no live model play. Four suites of 96 games: paired screen seeds
(20000+) and fresh holdout seeds (90000+). Profiles rotate through
`collector`, `early_support`, `prestige_farmer`, and `counterleader`
across all 24 gate permutations.

- Incumbent: `rules_v08_succession.json`
  (`succession.contest_cost: 0`, hash `eb6d2186…`).
- Candidate: identical except `succession.contest_cost: 1`
  (`candidate-rules.json`, hash `f6fb69a1…`).

## Headline (holdout, 96 games)

| Measure | Fee 0 | Fee 1 |
| --- | ---: | ---: |
| Draw fraction | 0.573 | 0.062 |
| Median rounds | 40 | 26 |
| Claims made per game | 26.1 | 9.7 |
| Canceled claims per game | 25.4 | 8.8 |
| Claims challenged (fraction) | 0.99 | 0.99 |
| Median choice-rich turns | 66% of turns | 66% of turns |

Screen seeds agree (draws 0.625 → 0.031; median rounds 40 → 24).
The free-challenge denial loop is confirmed and the mandatory fee of
one Prestige breaks it while challenges remain available: 99% of
claims still draw a challenge attempt.

## Promotion checks

All binding checks pass on screen and holdout
(`comparison.json`): draws improve, rounds shrink, counterplay
persists, all four profiles win. One interpretation change is
recorded in `tools/run_programme.py`: the cancellation-reduction
check now measures canceled claims per game (loop volume), not the
canceled share of claims. Under the share reading, a candidate that
keeps 99% of claims challenged and cuts cancellations per game by
two thirds would still fail; that contradicts the paired
counterplay floor. The revision was made before any model proposal
cycle ran.

## Strategy and gate detail (holdout)

- Win rate by profile, fee 0 → fee 1: collector 17% → 33%,
  counterleader 14% → 31%, early_support 10% → 19%,
  prestige_farmer 2% → 10%. Four viable strategies; the
  counterleader (leader-challenging) profile roughly doubles.
- First complete collector wins 47% of games at fee 1 (23% at
  fee 0): collecting remains a strong line but not a lock.
- Win rate by gate at fee 1: north 34%, west 25%, south 19%,
  east 16%. The east gate sits 12 steps from the crossing; the
  others sit 6. This is the known off-center-cardo geometry, not a
  new imbalance created by the fee. Random and rotation assignment
  share access to positions; they do not equalize gate strength.
  Changing the streets is out of scope for this programme.
- Idle moves (a plain move with no action): 30 per game at fee 1
  (31 per game at fee 0), about a third of turns. Watch this in
  human playtests; bots may walk more than people would.
- Prestige wasted at the cap: 1.8 per game at fee 1 versus 4.3 at
  fee 0.

## Limits

Offline bots with fixed probing policies; 96 games per suite;
Wilson 95% intervals in each `summary.json`. No claim here measures
human clarity, tension, or enjoyment. Live Decisions play and human
playtests remain separate steps.
