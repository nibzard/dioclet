# V0.5 experiment plan

Research date: 2026-11-07. Status: proposed. Owner: design agent.

Sources:

- PR #2 review (V0.5 priority order), 2026-11-06.
- `FINDINGS_V041.md` question 9 and the decision-quality scorecard.
- `FINDINGS_V03.md` duel-consequence batches (bots only).
- `FINDINGS_V02.md` adopted base package.

## Goal

V0.5 tests three rule changes under strong AI play. The question for
each is the same: does the change move the game toward "strategically
interesting", measured with Decisions players, not only frozen bots?

## Method (shared by all three experiments)

Each experiment pairs a free bot baseline with a live AI tournament:

1. Bot baseline: 1,000 games, seeds 1000–1999, SPEC §13 schedule,
   frozen bot policies. Free and fully offline.
2. AI tournament: 32 live games (16 rotation `decisions/tactical/
   balanced/greedy` + 16 pairs `decisions/tactical`), model
   `gpt-6-luna`, prompt `v04-1`, projection `v04-proj-1`. Seeds are
   new (6101+, 6201+, and so on) and do not overlap V0.4.1.
3. Analysis: `analyze_v041.py` scorecard plus the same metrics used
   in `FINDINGS_V041.md`, compared against the V0.4.1 base results.

Only one rule knob changes per experiment. `rules_v03_base.json`
stays frozen as the control.

## Experiment 1 — lost turn (`rules_v03_lostturn.json`)

Knob: `combat.duel_lost_turn: true`. A duel loser skips their next
turn.

- Bot evidence (V0.3): aggressive seats rise from 6% to 14% wins;
  3.91 turns lost per game; zero draws. But bots only — the confound
  is that no bot targets leaders.
- AI-era motivation (V0.4.1 Q7): under competent play, nothing slows
  a leader. `ta07`'s seven-attack pile-on cost the leader zero tempo.
  A lost turn is the cheapest knob that makes a duel cost tempo.
- Prediction (from `FINDINGS_V041.md` Q9): decisions duel rate stays
  near 1.4 per seat but shifts toward leaders; watch the
  tactical-versus-decisions gap and the low-value-duel share.
- Success looks like: interference duels at the Emperor rise; the
  leader's win share from one-hit-ahead positions falls; game length
  grows by at most one round; draws stay near zero.
- Failure looks like: duels still target Glory-empty victims, or the
  pace penalty makes Level 2 drag past 24 rounds.

## Experiment 2 — Peristyle seal costs 2 Glory (`rules_v05_peristyle2.json`)

Knob: `level2.peristyle_glory_cost: 2`.

- Motivation (V0.4.1 Q2, Q5): the Peristyle buy is underpriced.
  Decisions seats got the best seal efficiency (0.73 per attempt) by
  buying the guaranteed Peristyle seal early. Guard posts, the only
  reliable Glory source, were used once in 176 seat-games.
- At cost 2, the guaranteed seal consumes the full Glory cap — the
  same bank as one Emperor attack bonus (+2). The economy's central
  tension sharpens: seal, strike, or save.
- Prediction: seal efficiency drops toward 0.6; Glory-engine openings
  weaken; guard-post usage rises because banking 2 Glory now needs a
  plan.
- Success looks like: guard-post attempts per decisions seat rise
  well above the V0.4.1 rate of 0.006; seal timing choices become
  the hinge of close games; bots show no policy collapse like the
  V0.3 theft result.
- Failure looks like: seats simply arrive at Level 2 Glory-empty and
  stall, as in `tb202`.

## Experiment 3 — Level 1 capped at 16 rounds (`rules_v05_l1max16.json`)

Knob: `level1.max_rounds: 16` (from 24).

- Motivation (V0.4.1 Q9): `ta05` stalled — all four seats at 5 of 6
  items circling the last hidden district for 10 rounds. Level 1
  model confidence was 0.19, so the top pick itself was near noise.
- The median bot game finishes Level 1 in 8–9 rounds, so a 16-round
  cap bounds the stall without touching the median game.
- Prediction: p95 game length falls about 4 rounds; the auto-grant
  share rises slightly; collection stays worthwhile (5-plus items
  per seat) because the cap almost never binds.
- Success looks like: p95 length falls; auto-granted items per seat
  stay under 1.0; the collected-per-player counter stays above 5.
- Failure looks like: auto-grants soar (collection stops mattering)
  or draws appear from Level 1 timeouts.

## Bot baseline results (2026-11-07)

Both baselines ran on 2026-11-07 (1,000 games, seeds 1000–1999).
Comparison against `results/v03_base`:

| Metric | v03_base | peristyle2 | l1max16 |
|---|---:|---:|---:|
| Median rounds | 14 | 14 | 14 |
| p95 rounds | 17 | 18 | 17 |
| Duels per game | 4.57 | **5.61** | 4.57 |
| Attacker win % | 56 | 57 | 56 |
| Aggressive win % | 11 | **7** | 11 |
| Greedy win % | 26 | 28 | 26 |
| Balanced win % | 29 | 30 | 29 |
| Collected per player | 5.62 | 5.62 | 5.62 |
| Auto-granted per player | 0.39 | 0.39 | 0.39 |
| Peristyle purchases | 1,914 | 1,942 | 1,914 |
| Glory wasted per player | 0.24 | 0.25 | 0.24 |
| Draws | 0 | 0 | 0 |

**Level 1 cap 16 is a strict no-op under bots.** Its `games.csv` is
byte-identical to `results/v03_base/games.csv`: no bot game ever
reached 16 Level 1 rounds. This is the strongest possible no-regression
evidence, and it means the AI tournament is the only informative test
of this knob (the `ta05` stall was an AI-driven phenomenon).

**Peristyle cost 2 raises duels by 23 percent.** Verified mechanism:
`_pick_duel` in `policies.py` refuses fights while a seat is at the
Glory cap. Cost 2 drains a buyer from 2 Glory to 0, where cost 1
leaves 1. Seats sit below the cap longer, the duel gate opens more
often, and duels rise from 4.57 to 5.61 per game.

- Direction of concern: this echoes the V0.3 theft pattern — more
  combat, and the combat-first policy falls (aggressive 11% to 7%,
  Wilson intervals 9.0–13.3 versus 5.6–8.7 do not overlap) while the
  pacifist rises (greedy 26% to 28%). The effect is far milder than
  theft (aggressive 0%), and peristyle purchases barely move
  (1,914 to 1,942): bots still buy, they just duel more on the way.
- The AI tournament answers the question the bots cannot: does a
  planning player treat cost 2 as tension (seal versus strike versus
  save) or as a wall (arrive Glory-empty and stall, as in `tb202`)?

## Budget request (pending authorization)

| Experiment | Games | Estimated calls | Estimated cost | Hard cap |
|---|---:|---:|---:|---:|
| 1 lost turn | 32 | 768 | $0.086 | $0.40 |
| 2 Peristyle cost 2 | 32 | 768 | $0.086 | $0.40 |
| 3 Level 1 cap 16 | 32 | 768 | $0.086 | $0.40 |
| **Total** | 96 | 2,304 | **$0.26** | $1.20 |

Estimates use measured V0.4.1 rates (about 1,122 input tokens and
$0.000112 per call). They are not a billing guarantee. Live play
starts only after the user names a cap. No live games have been run
for V0.5 at the time of this note.

## Commands (ready to run)

```bash
# Bot baselines (free)
python3 sim.py batch --rules rules_v05_peristyle2.json --games 1000 \
  --seed-base 1000 --schedule experiment --out results/v05_peristyle2_bots
python3 sim.py batch --rules rules_v05_l1max16.json --games 1000 \
  --seed-base 1000 --schedule experiment --out results/v05_l1max16_bots

# AI tournaments (need --live-decisions plus authorization)
python3 sim.py tournament --config tournaments/v05_exp1_lostturn_ai.json \
  --out results/v05_exp1 --live-decisions
python3 sim.py tournament --config tournaments/v05_exp2_peristyle2_ai.json \
  --out results/v05_exp2 --live-decisions
python3 sim.py tournament --config tournaments/v05_exp3_l1max16_ai.json \
  --out results/v05_exp3 --live-decisions
```

## Open questions

1. Does the lost turn feel harsh for children (V0.3 caution)? The
   simulator cannot answer this; a human playtest must.
2. Should the checkpoint require N-of-6 equipment to keep collection
   meaningful (V0.4.1 Q6)? This needs a new optional knob. Hold until
   experiments 2 and 3 report.
3. Is the residual seat gap (28/21 in bots, pos1 36% in mirror games)
   worth a serpentine-order experiment in V0.5? Defer; measure it
   again on the 96 new games first.
